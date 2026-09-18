"""命令行入口（组合根的一部分）。

放在 ``bootstrap`` 而不是 ``presentation`` 的原因：入口需要 import ``bootstrap.wiring``，
而 ``presentation`` 层被禁止 import ``bootstrap``（见 ARCHITECTURE.md §1）。
"""

from __future__ import annotations

import argparse

from snaptranslate.bootstrap.wiring import (
    run_admin_app,
    run_review_app,
    run_review_web,
    run_translate_app,
)


def _data_dir_arg() -> str | None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--data-dir", default=None, help="数据目录（默认：工程根目录）")
    args, _unknown = parser.parse_known_args()
    return args.data_dir


def translate_main() -> None:
    run_translate_app(_data_dir_arg())


def review_main() -> None:
    run_review_app(_data_dir_arg())


def review_web_main() -> None:
    run_review_web(_data_dir_arg())


def admin_main() -> None:
    run_admin_app(_data_dir_arg())


def launcher_main() -> None:
    """控制台 + 托盘常驻（新增功能；打包后的默认入口）。"""
    from snaptranslate.bootstrap.launcher import main

    raise SystemExit(main())

