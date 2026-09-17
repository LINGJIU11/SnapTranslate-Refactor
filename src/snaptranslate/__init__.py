"""SnapTranslate —— Windows 划词翻译 + 截图 OCR + 生词本复习。

分层结构（详见 ARCHITECTURE.md）::

    presentation  →  application  →  domain
         ↓                ↓            ↑
         └────────►  infrastructure  ──┘
                          ↓
                        config

依赖方向严格单向向下，由 ``scripts/check_layering.py`` 静态校验。
"""

from __future__ import annotations

from snaptranslate.config.app import APP_NAME, APP_VERSION

__all__ = ["APP_NAME", "APP_VERSION"]
