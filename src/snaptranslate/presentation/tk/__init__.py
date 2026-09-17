"""Tk 桌面端窗口（原版 4 个脚本中 ``main.py`` / ``vocab_review.py`` / ``set.py`` 的对应物）。

本包只 import 标准库、第三方 UI 库与 ``domain`` / ``application`` / ``config`` / ``presentation``，
**不得** import ``infrastructure`` 与 ``bootstrap``（见 ARCHITECTURE.md §1）。
"""

from __future__ import annotations
