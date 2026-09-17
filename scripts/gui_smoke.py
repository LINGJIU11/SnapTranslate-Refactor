"""GUI 层冒烟自检（默认**不创建真实窗口**）。

用法::

    python scripts/gui_smoke.py            # 只做导入与接口检查（安全，无窗口）
    python scripts/gui_smoke.py --with-tk  # 真正创建 Tk 窗口对象（会短暂出现在桌面上），构造后立即销毁

``--with-tk`` 用于在改动窗口代码后做一次"能不能建出来"的验证；
它不进入 ``mainloop``，因此不会阻塞。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  [OK]   {label}")
    else:
        print(f"  [FAIL] {label} {detail}")
        FAILURES.append(label)


def check_interfaces() -> None:
    print("\n=== 1. 表示层接口检查（不建窗口） ===")
    from snaptranslate.bootstrap.container import Container

    container = Container()

    from snaptranslate.presentation.tk.admin_window import AdminApp
    from snaptranslate.presentation.tk.review_window import ReviewApp
    from snaptranslate.presentation.tk.translate_window import TranslateApp
    from snaptranslate.presentation.web.streamlit_review import render_page

    for name, cls in (("TranslateApp", TranslateApp), ("ReviewApp", ReviewApp), ("AdminApp", AdminApp)):
        check(f"{name} 可导入且可调用", callable(cls))
        check(f"{name}.run 存在", callable(getattr(cls, "run", None)))
    check("render_page 可调用", callable(render_page))

    bundles = {
        "translate_app_deps": container.translate_app_deps(),
        "review_app_deps": container.review_app_deps(),
        "web_review_deps": container.web_review_deps(),
        "admin_app_deps": container.admin_app_deps(),
    }
    for name, bundle in bundles.items():
        check(f"{name} 构建成功", bundle is not None)


class _StubPointer:
    """可编程的鼠标位置（替代真实的 Win32 取点，便于断言）。"""

    def __init__(self, position: tuple[int, int] = (0, 0)) -> None:
        self.position_xy = position

    def position(self) -> tuple[int, int]:
        return self.position_xy


def check_floating_card(app, root) -> None:
    """悬浮卡片的两条新行为（KNOWN_ISSUES.md #23 / #24），用真实 Tk 验证。"""
    card = app._floating  # noqa: SLF001 - 冒烟脚本，白盒检查
    if card is None:
        check("悬浮卡片存在", False)
        return

    stub = _StubPointer((0, 0))
    card._pointer = stub  # noqa: SLF001

    anchor = (600, 400)
    stub.position_xy = (5000, 5000)  # 显示时的真实鼠标位置与锚点无关
    card.show("hello", "你好", anchor=anchor)
    root.update()
    bounds = (anchor[0] + 16, anchor[1] + 16)
    check("卡片按锚点定位（热键时位置，而非显示时鼠标位置）", card.current_anchor() == bounds,
          f"current_anchor={card.current_anchor()} 期望={bounds}")
    check("卡片显示中", card.is_visible())

    # 不再定时自动关闭：等一段时间后仍然可见
    deadline = time.monotonic() + 0.4
    while time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)
    check("卡片不会自动消失（等待 0.4s 仍可见）", card.is_visible())

    # 鼠标在卡片内按下（例如点"收录生词本"）→ 不关闭
    stub.position_xy = (bounds[0] + 10, bounds[1] + 10)
    card._on_any_input()  # noqa: SLF001 - 模拟输入监听线程回调
    root.update()
    check("点在卡片上不关闭", card.is_visible())

    # 鼠标在卡片外按键/点鼠标 → 关闭
    stub.position_xy = (anchor[0] + 900, anchor[1] + 600)
    card._on_any_input()  # noqa: SLF001
    root.update()
    check("卡片外输入后关闭", not card.is_visible())
    check("关闭后输入监听停止", not app.deps.input_watcher.is_running())


def check_proxy_row(app) -> None:
    """代理设置行的端到端检查：界面改完 → 策略即时生效 + 落盘（KNOWN_ISSUES.md #25）。"""
    policy = app.deps.proxy_policy
    original = (policy.mode, policy.url)
    try:
        app.proxy_mode_var.set("custom")
        app.proxy_url_var.set("127.0.0.1:7897")
        app.on_apply_proxy()
        check(
            "界面改代理后策略即时生效",
            policy.mode == "custom" and policy.effective_url() == "http://127.0.0.1:7897",
            f"{policy.mode} {policy.effective_url()}",
        )
        saved = app.deps.settings.load_proxy()
        check("代理设置已落盘", saved == ("custom", "http://127.0.0.1:7897"), f"{saved}")
    finally:
        app.proxy_mode_var.set(original[0])
        app.proxy_url_var.set(original[1])
        app.on_apply_proxy()


def check_review_advance() -> None:
    """回归 #28：点「认识」之后，卡片必须画到**下一张**（真实 Tk + 真实用例）。

    这正是单测与对拍都盖不到的"GUI 事件链"：原版 ``_advance_after_grade()`` 末尾的
    ``self._show_card()`` 在阶段一重构时掉了，界面会停在旧卡（词 / 熟练度 / 进度 / 释义全不动），
    而评分已经落到看不见的下一个词上（``scripts/diagnose_review_advance.py`` 可复现）。
    """
    import json
    import shutil

    from snaptranslate.bootstrap.container import Container, DataPaths
    from snaptranslate.presentation.texts import ReviewText
    from snaptranslate.presentation.tk.review_window import ReviewApp

    tmp = ROOT / ".tmp-gui-smoke-review"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    items = [
        {"word": word, "meaning": f"{word} 的释义", "score": 50.0, "reviews": 0}
        for word in ("alpha", "bravo", "charlie", "delta")
    ]
    (tmp / "vocab.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        app = ReviewApp(Container(DataPaths.under(str(tmp))).review_app_deps())
        app.root.withdraw()
        app._sort_mode_var.set("score_asc")
        app._on_sort_mode_change()
        before = app._word_var.get()
        app._toggle_meaning()  # 先揭示释义：重绘应当把它擦掉
        app._apply_grade("know")
        after = app._word_var.get()
        current = app.session.current()
        check(
            "评分后卡片显示的词 = 会话当前词",
            current is not None and after == current.word,
            f"界面={after!r} 会话={getattr(current, 'word', None)!r}",
        )
        check("评分后卡片换到了下一张", after != before, f"{before!r} -> {after!r}")
        check(
            "评分后释义重新隐藏（揭示状态已重置）",
            app._meaning_var.get() == ReviewText.MEANING_PLACEHOLDER,
            f"meaning={app._meaning_var.get()!r}",
        )
        app.root.destroy()
    except Exception as exc:  # noqa: BLE001
        check("评分后卡片前进", False, f"{type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_input_box() -> None:
    """中译英输入框（新增功能）：弹出 / 回车翻译 / 复用 / 关闭的真 Tk 断言。

    这是"GUI 事件链"里最容易回归的一环（#28 的教训）：用例、文案都对，但焦点与
    关闭规则接错了，用户看到的行为就完全不是他要求的那套。
    """
    import tkinter as tk

    from snaptranslate.application.dto import OutcomeKind, TranslationOutcome
    from snaptranslate.domain.models.translation import TranslationResult
    from snaptranslate.presentation.tk.input_box import OverlayInputBox

    class _Pointer:
        def __init__(self) -> None:
            self.point = (400, 400)

        def position(self) -> tuple[int, int]:
            return self.point

    class _Watcher:
        def __init__(self) -> None:
            self.callback = None
            self.running = False

        def start(self, callback) -> None:
            self.callback = callback
            self.running = True

        def stop(self) -> None:
            self.running = False

        def fire(self) -> None:
            if self.callback is not None:
                self.callback()

    class _Activator:
        def __init__(self) -> None:
            self.restored: list[int] = []

        def foreground(self) -> int:
            return 4242

        def force_foreground(self, hwnd: int) -> None:
            self.restored.append(hwnd)

    def _outcome(text: str) -> TranslationOutcome:
        return TranslationOutcome(
            kind=OutcomeKind.OK, source_text=text, result=TranslationResult(text)
        )

    root = tk.Tk()
    root.withdraw()
    pointer, watcher, activator = _Pointer(), _Watcher(), _Activator()
    submitted: list[str] = []

    def on_submit(text: str, done) -> None:
        submitted.append(text)
        done(_outcome("Hello"))

    box = OverlayInputBox(
        root,
        pointer=pointer,
        input_watcher=watcher,
        window_activator=activator,
        marshal=lambda fn: root.after(0, fn),
        on_submit=on_submit,
    )
    try:
        box.show((100, 100))
        root.update()
        check("输入框弹出并可见", box.is_visible())
        check("弹出后处于输入状态（按键算输入，不算关闭）", box.is_accepting_input())

        box._input.insert("1.0", "你好")
        box._submit()
        root.update()
        check("回车把中文交给用例", submitted == ["你好"], f"submitted={submitted}")
        check("英文显示在输出区", box.output_text() == "Hello", f"output={box.output_text()!r}")
        check("中文留在输入框里", box.input_text() == "你好", f"input={box.input_text()!r}")
        check("翻译完成后交出键盘焦点", not box.is_accepting_input())
        # 第一次 force_foreground 是"把自己抢到前台"（得到输入焦点），最后一次是"还回去"
        check(
            "焦点还给原来的前台窗口",
            activator.restored[-1] == 4242,
            f"restored={activator.restored}",
        )

        # 鼠标左键点在框内 → "下一次输入"，而不是关闭
        anchor = box.current_anchor()
        assert anchor is not None
        pointer.point = (anchor[0] + 20, anchor[1] + 20)
        watcher.fire()
        root.update()
        check("点框内不算关闭，而是回到输入状态", box.is_visible() and box.is_accepting_input())

        # 连按两次回车：先回来的旧结果必须被丢掉，只认最后一次
        pending: list = []
        box._on_submit = lambda text, done: (submitted.append(text), pending.append(done))
        box._submit()
        box._submit()
        stale, latest = pending[0], pending[1]
        stale(_outcome("旧结果"))
        root.update()
        check("过期结果被丢弃", box.output_text() != "旧结果", f"output={box.output_text()!r}")
        latest(_outcome("新结果"))
        root.update()
        check("只有最后一次结果生效", box.output_text() == "新结果", f"output={box.output_text()!r}")

        # 框外输入（按键/点击）→ 关闭，并停掉监听
        box._release_focus()
        pointer.point = (5, 5)
        watcher.fire()
        root.update()
        check("框外输入后关闭", not box.is_visible())
        check("关闭后停止输入监听", not watcher.running)
    finally:
        box.shutdown()
        root.destroy()


def check_with_tk() -> None:
    print("\n=== 2. 真实 Tk 构造（--with-tk） ===")
    try:
        import tkinter as tk
    except Exception as exc:  # noqa: BLE001
        check("tkinter 可用", False, str(exc))
        return

    from snaptranslate.bootstrap.container import Container

    container = Container()

    from snaptranslate.presentation.tk.admin_window import AdminApp
    from snaptranslate.presentation.tk.review_window import ReviewApp
    from snaptranslate.presentation.tk.translate_window import TranslateApp

    apps = (
        ("TranslateApp", TranslateApp, container.translate_app_deps()),
        ("ReviewApp", ReviewApp, container.review_app_deps()),
        ("AdminApp", AdminApp, container.admin_app_deps()),
    )
    for name, cls, deps in apps:
        try:
            app = cls(deps)
        except Exception as exc:  # noqa: BLE001
            check(f"{name} 构造", False, f"{type(exc).__name__}: {exc}")
            continue
        check(f"{name} 构造", True)

        # 划词窗口与原版一致：``__init__`` 不建 Tk，界面在 ``_build_ui()`` 里创建（原 main.py:1538）
        root = getattr(app, "_root", None) or getattr(app, "root", None)
        if root is None and hasattr(app, "_build_ui"):
            try:
                app._build_ui()
                check(f"{name} 界面装配", True)
            except Exception as exc:  # noqa: BLE001
                check(f"{name} 界面装配", False, f"{type(exc).__name__}: {exc}")
            root = getattr(app, "_root", None) or getattr(app, "root", None)

        # KNOWN_ISSUES #21 的回归：界面改热键必须立即同步到监听器（原版每轮重新读热键）
        if name == "TranslateApp":
            original_hotkeys = dict(app.hotkeys)  # 自检不该改用户的设置，跑完还原
            try:
                app.hotkey_translate_var.set("alt+z")
                app.hotkey_snip_var.set("tab+q")
                app.hotkey_save_var.set("tab+e")
                # 新增功能：第 4 组（中译英输入框）必须一起应用并同步
                app.hotkey_input_var.set("ctrl+i")
                app.on_apply_hotkeys()
                bindings = getattr(app.deps.hotkey_listener, "_bindings", None)
                synced = bindings is not None and bindings.translate.label == "ALT+Z"
                check("改热键后监听器即时同步（无需重启）", synced, f"bindings={bindings}")
                four = (
                    bindings is not None
                    and bindings.input is not None
                    and bindings.input.label == "CTRL+I"
                )
                check("四组热键（含中译英）一起生效", four, f"bindings={bindings}")
                check(
                    "第 4 组热键出现在标题提示行",
                    "中译英：CTRL+I" in (app.hotkey_hint_var.get() if app.hotkey_hint_var else ""),
                    f"hint={app.hotkey_hint_var.get() if app.hotkey_hint_var else None!r}",
                )
            except Exception as exc:  # noqa: BLE001
                check("改热键后监听器即时同步（无需重启）", False, f"{type(exc).__name__}: {exc}")
            finally:
                try:
                    app.hotkey_translate_var.set(original_hotkeys["translate"])
                    app.hotkey_snip_var.set(original_hotkeys["snip"])
                    app.hotkey_save_var.set(original_hotkeys["save_last"])
                    app.hotkey_input_var.set(original_hotkeys.get("input", "ctrl+i"))
                    app.on_apply_hotkeys()
                except Exception:  # noqa: BLE001
                    pass

            check_floating_card(app, root)
            check_proxy_row(app)

        if isinstance(root, tk.Misc):
            try:
                root.withdraw()
                root.update_idletasks()
                root.destroy()
                check(f"{name} 窗口销毁", True)
            except Exception as exc:  # noqa: BLE001
                check(f"{name} 窗口销毁", False, f"{type(exc).__name__}: {exc}")
        else:
            check(f"{name} 拿到 Tk root", False, f"got {type(root).__name__}")

    check_review_advance()
    check_input_box()


def main() -> int:
    check_interfaces()
    if "--with-tk" in sys.argv[1:]:
        check_with_tk()
    else:
        print("\n（未加 --with-tk，跳过真实窗口构造）")
    print()
    if FAILURES:
        print(f"[FAIL] 共 {len(FAILURES)} 项未通过")
        return 1
    print("[OK] 全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
