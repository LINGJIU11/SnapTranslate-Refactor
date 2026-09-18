"""托盘图标适配器：``Shell_NotifyIconW`` + 一个隐藏消息窗口（零新依赖）。

为什么不引入 ``pystray``：本项目已经有 ``win32_clipboard`` / ``win32_hotkeys`` /
``win32_pointer`` / ``win32_window`` 这一族 ctypes 适配器，托盘用同样的手法实现，
既不加依赖、也不引入第二套 GUI 事件模型（pystray 还会额外要求 Pillow 的图像 API）。

结构（经典四件套）：

1. 注册一个窗口类，``WNDPROC`` 处理 ``WM_APP+1``（托盘回调）与 ``WM_COMMAND``（菜单）；
2. 建一个**从不显示**的窗口当消息宿主；
3. ``Shell_NotifyIconW(NIM_ADD)`` 注册图标，``NIM_MODIFY`` 改提示/菜单，``NIM_DELETE`` 移除；
4. 在**自己的线程**里跑 ``GetMessageW`` 循环——Tk 的 mainloop 只泵自己线程的消息。

线程约定：``start`` 之后所有 Win32 调用都发生在托盘线程；``update/notify`` 由主线程
通过队列转发过去（``PostMessage`` 唤醒），因此调用方无需关心线程。
"""

from __future__ import annotations

import ctypes
import queue
import threading
from ctypes import wintypes
from typing import Callable, Sequence

from snaptranslate.domain.ports.tray import TrayMenuItem

# —— Win32 常量 ——
WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_NULL = 0x0000
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_APP = 0x8000
WM_TRAY_CALLBACK = WM_APP + 1

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
LR_DEFAULTSIZE = 0x00000040
IDI_APPLICATION = 32512

MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
MF_CHECKED = 0x00000008
MF_GRAYED = 0x00000001
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100

CS_HREDRAW = 0x0002
CS_VREDRAW = 0x0001
CW_USEDEFAULT = -2147483648

#: 菜单项 id 从 100 起（避开 0 = 取消）
MENU_ID_BASE = 100

#: 64 位安全的整数类型：Win32 的 WPARAM 是 UINT_PTR、LPARAM 是 LONG_PTR，
#: ``ctypes.wintypes`` 里这两个字段在部分 Python 版本仍是 32 位，
#: 直接用它声明回调签名会在收到大数值时抛 OverflowError（本模块实测踩到过）。
WPARAM_T = ctypes.c_size_t
LPARAM_T = ctypes.c_ssize_t
LRESULT_T = ctypes.c_ssize_t


class NOTIFYICONDATAW(ctypes.Structure):
    """``NOTIFYICONDATAW``（Vista+ 完整版；``cbSize`` 用结构体真实大小）。"""

    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HANDLE),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HANDLE),
    ]


class MSGW(ctypes.Structure):
    """``MSG``（自己声明：``wintypes.MSG`` 在 64 位下字段宽度可能不对）。"""

    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", WPARAM_T),
        ("lParam", LPARAM_T),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


WNDPROC = ctypes.WINFUNCTYPE(LRESULT_T, wintypes.HWND, wintypes.UINT, WPARAM_T, LPARAM_T)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class Win32TrayIcon:
    """实现 :class:`~snaptranslate.domain.ports.tray.TrayIcon`。

    :param on_double_click: 双击托盘图标时选择哪个菜单项（默认 ``"panel"``）
    """

    def __init__(self, *, user32=None, kernel32=None, shell32=None, on_double_click: str = "panel") -> None:
        self._user32 = user32 if user32 is not None else ctypes.windll.user32
        self._kernel32 = kernel32 if kernel32 is not None else ctypes.windll.kernel32
        # ``Shell_NotifyIconW`` 在 shell32.dll 里（不在 user32，实测踩过）
        self._shell32 = shell32 if shell32 is not None else ctypes.windll.shell32
        self._on_double_click = on_double_click
        self._bind_signatures()

        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._registered = False
        self._stopping = False
        self._hwnd = 0
        self._class_name = f"SnapTranslateTray{id(self):x}"
        self._icon = 0
        self._icon_path = ""
        self._tooltip = "SnapTranslate"
        self._items: list[TrayMenuItem] = []
        self._on_select: Callable[[str], None] | None = None
        self._queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._wndproc_ref = WNDPROC(self._wndproc)  # 必须保持引用，否则被 GC 回收
        self._carrier = NOTIFYICONDATAW()  # 复用同一块内存，避免每次构造

    # ———————————————————————————— 端口 ————————————————————————————

    def start(
        self,
        tooltip: str,
        icon_path: str,
        items: Sequence[TrayMenuItem],
        on_select: Callable[[str], None],
    ) -> bool:
        if self._thread is not None:
            return self._registered
        self._tooltip = tooltip
        self._icon_path = icon_path
        self._items = list(items)
        self._on_select = on_select
        self._thread = threading.Thread(target=self._run, daemon=True, name="snaptranslate-tray")
        self._thread.start()
        self._ready.wait(timeout=3.0)
        return self._registered

    def update(self, items: Sequence[TrayMenuItem]) -> None:
        self._items = list(items)
        self._post("update", None)

    def notify(self, title: str, message: str) -> None:
        self._post("notify", (title, message))

    def stop(self) -> None:
        self._stopping = True
        self._post("quit", None)
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=2.0)

    @property
    def registered(self) -> bool:
        return self._registered

    # ———————————————————————————— 内部：线程与消息循环 ————————————————————————————

    def _bind_signatures(self) -> None:
        """显式声明用到的 Win32 函数签名。

        ctypes 的默认推断（``windll`` 下所有参数都按 int 处理）在这几个函数上会出问题：
        ``DefWindowProcW`` 的 lParam 是 64 位、``LoadIconW`` 的资源号要按指针传。
        """
        u, k, s = self._user32, self._kernel32, self._shell32
        try:
            u.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM_T, LPARAM_T]
            u.DefWindowProcW.restype = LRESULT_T
            u.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
            u.RegisterClassW.restype = wintypes.ATOM
            # CreateWindowExW 的 12 个参数必须全声明：默认按 32 位 int 推断，
            # hInstance 这类 64 位句柄会直接抛 OverflowError（实测踩到过）
            u.CreateWindowExW.argtypes = [
                wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                wintypes.HWND, wintypes.HANDLE, wintypes.HINSTANCE, ctypes.c_void_p,
            ]
            u.CreateWindowExW.restype = wintypes.HWND
            u.DestroyWindow.argtypes = [wintypes.HWND]
            u.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
            u.SetForegroundWindow.argtypes = [wintypes.HWND]
            u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM_T, LPARAM_T]
            u.PostQuitMessage.argtypes = [ctypes.c_int]
            u.TranslateMessage.argtypes = [ctypes.POINTER(MSGW)]
            u.DispatchMessageW.argtypes = [ctypes.POINTER(MSGW)]
            u.DispatchMessageW.restype = LRESULT_T
            u.DestroyMenu.argtypes = [wintypes.HANDLE]
            u.CreatePopupMenu.restype = wintypes.HANDLE
            u.AppendMenuW.argtypes = [wintypes.HANDLE, wintypes.UINT, WPARAM_T, wintypes.LPCWSTR]
            u.TrackPopupMenu.argtypes = [
                wintypes.HANDLE, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, wintypes.HWND, ctypes.c_void_p,
            ]
            u.TrackPopupMenu.restype = ctypes.c_int
            u.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
            u.GetMessageW.argtypes = [ctypes.POINTER(MSGW), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            u.GetMessageW.restype = ctypes.c_int
            # LoadImageW 的路径与 LoadIconW 的资源号都要按"指针宽度"传
            u.LoadImageW.argtypes = [
                wintypes.HINSTANCE, ctypes.c_void_p, wintypes.UINT,
                ctypes.c_int, ctypes.c_int, wintypes.UINT,
            ]
            u.LoadImageW.restype = wintypes.HANDLE
            u.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
            u.LoadIconW.restype = wintypes.HANDLE
            s.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
            s.Shell_NotifyIconW.restype = wintypes.BOOL
            k.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            k.GetModuleHandleW.restype = wintypes.HINSTANCE
        except (AttributeError, OSError):  # pragma: no cover - 非 Windows
            pass

    def _post(self, action: str, payload: object) -> None:
        """把请求交给托盘线程（同时用一条 ``WM_NULL`` 唤醒消息循环）。"""
        self._queue.put((action, payload))
        if self._hwnd:
            try:
                self._user32.PostMessageW(self._hwnd, WM_NULL, 0, 0)
            except Exception:
                pass

    def _run(self) -> None:
        user32, kernel32 = self._user32, self._kernel32
        try:
            hinstance = kernel32.GetModuleHandleW(None)
            wc = WNDCLASSW(
                style=CS_HREDRAW | CS_VREDRAW,
                lpfnWndProc=self._wndproc_ref,
                cbClsExtra=0,
                cbWndExtra=0,
                hInstance=hinstance,
                hIcon=0,
                hCursor=0,
                hbrBackground=0,
                lpszMenuName=None,
                lpszClassName=self._class_name,
            )
            user32.RegisterClassW(ctypes.byref(wc))
            self._hwnd = user32.CreateWindowExW(
                0, self._class_name, self._class_name, 0,
                0, 0, 0, 0, None, None, hinstance, None,
            )
            if not self._hwnd:
                return
            self._registered = self._add_icon()
        finally:
            self._ready.set()

        if not self._registered:
            self._cleanup_window()
            return

        message = MSGW()
        while not self._stopping:
            result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
            if result in (0, -1):
                break
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
            self._drain_queue()

        self._delete_icon()
        self._cleanup_window()

    def _drain_queue(self) -> None:
        while True:
            try:
                action, payload = self._queue.get_nowait()
            except queue.Empty:
                return
            if action == "quit":
                return
            if action == "update":
                self._modify_icon()
            elif action == "notify" and isinstance(payload, tuple):
                self._notify(*payload)

    # —— 图标 ——

    def _load_icon(self) -> int:
        user32 = self._user32
        icon = 0
        if self._icon_path:
            try:
                icon = user32.LoadImageW(
                    None, self._icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE
                )
            except Exception:
                icon = 0
        if not icon:
            # 退化到系统默认图标：宁可有图标、也不要没有托盘入口
            icon = user32.LoadIconW(None, IDI_APPLICATION)
        return int(icon or 0)

    def _fill(self, flags: int, *, info: tuple[str, str] | None = None) -> None:
        carrier = self._carrier
        ctypes.memset(ctypes.byref(carrier), 0, ctypes.sizeof(carrier))
        carrier.cbSize = ctypes.sizeof(carrier)
        carrier.hWnd = self._hwnd
        carrier.uID = 1
        carrier.uFlags = flags
        carrier.uCallbackMessage = WM_TRAY_CALLBACK
        carrier.hIcon = self._icon
        carrier.szTip = self._tooltip[:127]
        if info is not None:
            title, message = info
            carrier.szInfoTitle = title[:63]
            carrier.szInfo = message[:255]

    def _add_icon(self) -> bool:
        self._icon = self._load_icon()
        self._fill(NIF_MESSAGE | NIF_ICON | NIF_TIP)
        return bool(self._shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._carrier)))

    def _modify_icon(self) -> None:
        self._fill(NIF_MESSAGE | NIF_ICON | NIF_TIP)
        self._shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._carrier))

    def _notify(self, title: str, message: str) -> None:
        if not self._registered:
            return
        self._fill(NIF_INFO)
        self._shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._carrier))

    def _delete_icon(self) -> None:
        if not self._registered:
            return
        self._fill(0)
        self._shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._carrier))
        self._registered = False

    def _cleanup_window(self) -> None:
        if self._hwnd:
            try:
                self._user32.DestroyWindow(self._hwnd)
                self._user32.UnregisterClassW(self._class_name, self._kernel32.GetModuleHandleW(None))
            except Exception:
                pass
            self._hwnd = 0

    # —— 菜单与回调 ——

    def _wndproc(self, hwnd, msg, wparam, lparam):  # noqa: ANN001 - Win32 回调签名
        try:
            if msg == WM_TRAY_CALLBACK:
                event = lparam & 0xFFFF
                if event in (WM_RBUTTONUP, WM_LBUTTONUP):
                    self._show_menu()
                elif event == WM_LBUTTONDBLCLK and self._on_select is not None:
                    self._dispatch(self._on_double_click)
                return 0
            if msg == WM_COMMAND:
                menu_id = wparam & 0xFFFF
                self._dispatch_id(menu_id)
                return 0
            if msg == WM_DESTROY:
                self._user32.PostQuitMessage(0)
                return 0
        except Exception:
            pass
        return self._user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _show_menu(self) -> None:
        user32 = self._user32
        menu = user32.CreatePopupMenu()
        if not menu:
            return
        id_to_key: dict[int, str] = {}
        try:
            for index, item in enumerate(self._items, start=MENU_ID_BASE):
                flags = MF_STRING
                if item.separator_before:
                    user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
                if item.checked:
                    flags |= MF_CHECKED
                if not item.enabled:
                    flags |= MF_GRAYED
                user32.AppendMenuW(menu, flags, index, item.label)
                id_to_key[index] = item.id

            point = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            # 弹出前先把宿主窗口设成前台，否则点菜单外面菜单不会消失（MSDN 的经典要求）
            user32.SetForegroundWindow(self._hwnd)
            selected = user32.TrackPopupMenu(
                menu,
                TPM_RIGHTBUTTON | TPM_RETURNCMD,
                point.x,
                point.y,
                0,
                self._hwnd,
                None,
            )
            user32.PostMessageW(self._hwnd, WM_NULL, 0, 0)
            if selected:
                key = id_to_key.get(int(selected))
                if key is not None:
                    self._dispatch(key)
        finally:
            user32.DestroyMenu(menu)

    def _dispatch_id(self, menu_id: int) -> None:
        index = menu_id - MENU_ID_BASE
        if 0 <= index < len(self._items):
            self._dispatch(self._items[index].id)

    def _dispatch(self, key: str) -> None:
        callback = self._on_select
        if callback is None:
            return
        try:
            callback(key)
        except Exception:
            # 菜单回调由用户代码提供，异常不能打断托盘线程
            pass


__all__ = ["MENU_ID_BASE", "Win32TrayIcon"]
