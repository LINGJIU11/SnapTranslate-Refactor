"""Streamlit 进程入口（组合根的一部分）。

``streamlit run`` 需要一个"脚本文件"作为页面；它必须自己构造依赖，因此放在
``bootstrap`` 层（唯一允许 import 全部层的层），页面本身留在 ``presentation.web``。
"""

from __future__ import annotations

import argparse

from snaptranslate.bootstrap.container import Container, DataPaths
from snaptranslate.presentation.web.streamlit_review import render_page


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--data-dir", default=None)
    args, _unknown = parser.parse_known_args()
    return args


def main() -> None:
    args = _parse_args()
    container = Container(DataPaths.under(args.data_dir)) if args.data_dir else Container()
    render_page(container.web_review_deps())


# Streamlit 执行脚本时会把 ``__name__`` 设为 ``"__main__"``（与原版脚本同一约定），
# 加 guard 可避免"仅 import 就渲染页面"的副作用。
if __name__ == "__main__":
    main()
