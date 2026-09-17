"""路径解析：数据目录、数据文件、外部程序位置。

收敛原版 4 个脚本顶部各自定义的 ``SCRIPT_DIR / DEFAULT_VOCAB / DEFAULT_KEY_FILE /
DEFAULT_SETTINGS_FILE / BACKUP_DIR / DEFAULT_VOCAB_PATH / DEFAULT_BACKUP_DIR`` 常量。

默认数据目录 = **工程根目录**（等价于原版"脚本与数据同目录"）。
可用环境变量 ``SNAPTRANSLATE_DATA_DIR`` 覆盖——这是本轮唯一新增能力，
不设置时行为与原版完全一致（见 ARCHITECTURE.md §4.6）。
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_DATA_DIR = "SNAPTRANSLATE_DATA_DIR"

# <root>/src/snaptranslate/config/paths.py → parents[3] 即工程根目录
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

VOCAB_FILENAME = "vocab.json"
API_KEY_FILENAME = "api_key.txt"
TRANSLATE_SETTINGS_FILENAME = "main_settings.json"
REVIEW_SETTINGS_FILENAME = "vocab_review_settings.json"
BACKUP_DIRNAME = "backups"

# main.py 中的 OCR 相关常量
OCR_LANG = "eng+chi_sim"
OCR_MAX_PIXELS = 2_400_000
TESSERACT_CANDIDATE_DIRS = (
    r"C:\Program Files\Tesseract-OCR",
    r"C:\Program Files (x86)\Tesseract-OCR",
)
#: 若该路径存在则强制优先使用，避免被 PATH 中旧版本（如 E:\tes）劫持
FORCE_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def project_root() -> Path:
    """工程根目录。"""
    return _PROJECT_ROOT


def data_dir() -> Path:
    """数据目录：默认工程根目录，可用环境变量覆盖。"""
    raw = os.environ.get(ENV_DATA_DIR, "").strip()
    if raw:
        return Path(raw).expanduser()
    return _PROJECT_ROOT


def vocab_path() -> str:
    return str(data_dir() / VOCAB_FILENAME)


def api_key_path() -> str:
    return str(data_dir() / API_KEY_FILENAME)


def translate_settings_path() -> str:
    return str(data_dir() / TRANSLATE_SETTINGS_FILENAME)


def review_settings_path() -> str:
    return str(data_dir() / REVIEW_SETTINGS_FILENAME)


def backup_dir() -> str:
    return str(data_dir() / BACKUP_DIRNAME)
