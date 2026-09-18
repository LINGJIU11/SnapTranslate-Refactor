"""路径解析：数据目录、数据文件、外部程序位置。

收敛原版 4 个脚本顶部各自定义的 ``SCRIPT_DIR / DEFAULT_VOCAB / DEFAULT_KEY_FILE /
DEFAULT_SETTINGS_FILE / BACKUP_DIR / DEFAULT_VOCAB_PATH / DEFAULT_BACKUP_DIR`` 常量。

默认数据目录：

- **源码运行** = 工程根目录（等价于原版"脚本与数据同目录"）；
- **打包运行**（``sys.frozen``）= **exe 所在目录**（便携：整个文件夹拷走即可迁移）；
- 两种情况都可用环境变量 ``SNAPTRANSLATE_DATA_DIR`` 覆盖。

打包那条分支是必须的：``--onefile`` 下 ``__file__`` 指向临时解包目录，
数据会写进临时目录并在退出时消失（见 KNOWN_ISSUES.md §八 N2）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ENV_DATA_DIR = "SNAPTRANSLATE_DATA_DIR"

# <root>/src/snaptranslate/config/paths.py → parents[3] 即工程根目录
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

VOCAB_FILENAME = "vocab.json"
API_KEY_FILENAME = "api_key.txt"
TRANSLATE_SETTINGS_FILENAME = "main_settings.json"
REVIEW_SETTINGS_FILENAME = "vocab_review_settings.json"
BACKUP_DIRNAME = "backups"
#: 取词/翻译日志（打包后没有控制台，日志必须落文件）
LOG_FILENAME = "划词日志.txt"

# main.py 中的 OCR 相关常量
OCR_LANG = "eng+chi_sim"
OCR_MAX_PIXELS = 2_400_000
TESSERACT_CANDIDATE_DIRS = (
    r"C:\Program Files\Tesseract-OCR",
    r"C:\Program Files (x86)\Tesseract-OCR",
)
#: 若该路径存在则强制优先使用，避免被 PATH 中旧版本（如 E:\tes）劫持
FORCE_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def is_frozen() -> bool:
    """是否运行在打包产物里（PyInstaller 会设置 ``sys.frozen``）。"""
    return bool(getattr(sys, "frozen", False))


def base_dir() -> Path:
    """数据目录的默认落点（不含环境变量覆盖）。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return _PROJECT_ROOT


def project_root() -> Path:
    """程序所在目录（源码运行 = 工程根目录，打包运行 = exe 目录）。"""
    return base_dir()


def data_dir() -> Path:
    """数据目录：默认见 :func:`base_dir`，可用环境变量覆盖。"""
    raw = os.environ.get(ENV_DATA_DIR, "").strip()
    if raw:
        return Path(raw).expanduser()
    return base_dir()


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


def log_path() -> str:
    return str(data_dir() / LOG_FILENAME)


#: 打包时随程序一起分发的静态资源目录名（图标等）
ASSETS_DIRNAME = "assets"
ICON_FILENAME = "snaptranslate.ico"


def asset_dir() -> Path:
    """静态资源目录。

    - 源码运行 = 工程根目录下的 ``assets/``；
    - 打包运行 = PyInstaller 的解包目录（``sys._MEIPASS``，onedir 下就是 ``_internal/``），
      取不到时退回 exe 同级目录。
    """
    if is_frozen():
        base = getattr(sys, "_MEIPASS", None)
        root = Path(base) if base else Path(sys.executable).resolve().parent
        return root / ASSETS_DIRNAME
    return _PROJECT_ROOT / ASSETS_DIRNAME


def icon_path() -> str:
    """托盘 / exe 图标（不存在时托盘适配器会退回系统默认图标）。"""
    return str(asset_dir() / ICON_FILENAME)
