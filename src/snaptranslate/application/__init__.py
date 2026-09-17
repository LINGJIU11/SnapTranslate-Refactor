"""application 层：用例编排。

只依赖 ``domain`` 的端口与模型（以及 ``config`` 的只读常量），
**不知道** GUI、不知道 requests/pytesseract（见 ARCHITECTURE.md §1）。
"""

from __future__ import annotations
