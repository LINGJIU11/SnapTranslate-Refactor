"""表示层：Tk 桌面窗口 + Streamlit 网页 + CLI 启动器。

允许依赖：标准库、第三方 UI 库、``domain.*``、``application.*``、``config.*``；
**禁止** import ``infrastructure`` 与 ``bootstrap``（见 ARCHITECTURE.md §1）。
"""

from __future__ import annotations
