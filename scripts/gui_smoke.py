"""GUI 层冒烟自检（默认**不创建真实窗口**）。

用法::

    python scripts/gui_smoke.py            # 只做导入与接口检查（安全，无窗口）
    python scripts/gui_smoke.py --with-tk  # 真正创建 Tk 窗口对象（会短暂出现在桌面上），构造后立即销毁

``--with-tk`` 用于在改动窗口代码后做一次"能不能建出来"的验证；
它不进入 ``mainloop``，因此不会阻塞。
"""

from __future__ import annotations

import sys
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
