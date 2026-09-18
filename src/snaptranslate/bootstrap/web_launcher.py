"""Web 复习端的"冻结版"入口（供单独打包的 web 包使用）。

源码运行走 ``bootstrap/wiring.run_review_web``（``python -m streamlit run …``）；
打包之后没有 Python 解释器可调，改用 Streamlit 自己的 CLI 入口：

.. code-block:: python

    from streamlit.web import cli as stcli
    sys.argv = ["streamlit", "run", "<打包进来的脚本>", …]
    stcli.main()

被运行的脚本是打包时一起放进去的 ``streamlit_entry.py``（PyInstaller 把它放进
``assets/``，见 ``packaging/snaptranslate_web.spec``）。
"""

from __future__ import annotations

import sys
from pathlib import Path

from snaptranslate.config import paths as config_paths

#: Web 端端口（"横幅报一个端口、实际监听另一个"这种错位就是没显式指定端口造成的）
WEB_PORT = 8501


def _web_script() -> Path:
    """被 streamlit 执行的页面脚本：优先用随包附带的那份。"""
    bundled = config_paths.asset_dir() / "streamlit_entry.py"
    if bundled.is_file():
        return bundled
    return Path(config_paths.project_root()) / "src" / "snaptranslate" / "bootstrap" / "streamlit_entry.py"


def main(data_dir: str | None = None) -> int:
    try:
        from streamlit.web import bootstrap as st_bootstrap
    except Exception as exc:  # noqa: BLE001 - 主包（不含 streamlit）会走到这里
        # 把真实原因打出来：只看到"未安装"会让人查错方向
        print(f"无法加载 streamlit：{type(exc).__name__}: {exc}")
        print("主包不含 Web 复习端；请使用单独打包的 SnapTranslateWeb，或源码运行：")
        print("  python -m streamlit run entrypoints/vocab_review_web.py")
        import traceback

        traceback.print_exc()
        return 2

    script = _web_script()
    directory = data_dir or str(config_paths.data_dir())
    # 用**程序化入口**而不是 CLI：打包后 argv 很容易和 streamlit 的 click 解析打架，
    # 而且这里能显式指定端口（CLI 路径在冻结环境下曾出现"横幅报 3000、实际 8501"的错位）。
    flag_options = {
        "server.port": WEB_PORT,
        "server.headless": True,
        "browser.gatherUsageStats": False,
        "global.developmentMode": False,
    }
    try:
        st_bootstrap.run(
            str(script),
            is_hello=False,
            args=["--data-dir", directory],
            flag_options=flag_options,
        )
    except TypeError:  # pragma: no cover - 老版本 streamlit 没有 flag_options
        from streamlit.web import cli as stcli

        sys.argv = ["streamlit", "run", str(script), f"--server.port={WEB_PORT}", "--", "--data-dir", directory]
        return int(stcli.main() or 0)
    return 0


if __name__ == "__main__":  # pragma: no cover - 打包入口
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))
