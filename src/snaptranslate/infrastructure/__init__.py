"""infrastructure 层：端口的具体实现（适配器）。

允许依赖：标准库、第三方库、``domain.*``、``config.*``；
**禁止** import ``application`` / ``presentation`` / ``bootstrap``（见 ARCHITECTURE.md §1）。
"""

from __future__ import annotations
