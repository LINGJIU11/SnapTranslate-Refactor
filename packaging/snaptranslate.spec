# 主包：三个 Tk 应用 + 启动器/托盘（**不含 streamlit**，见 packaging/README.md）
# 构建：python scripts/build_packages.py           （或 python -m PyInstaller packaging/snaptranslate.spec）
import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(ROOT / "entrypoints" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[(str(ROOT / "assets" / "snaptranslate.ico"), "assets")],
    hiddenimports=[
        # 延迟导入的窗口在静态分析里不一定被跟到，这里显式列出（保险）
        "snaptranslate.presentation.tk.translate_window",
        "snaptranslate.presentation.tk.review_window",
        "snaptranslate.presentation.tk.admin_window",
        "snaptranslate.presentation.tk.launcher_window",
    ],
    hookspath=[],
    runtime_hooks=[],
    # 主包刻意不带 Web 复习端：streamlit 会连带 pandas/pyarrow/altair/numpy，约 +220MB
    excludes=[
        "streamlit",
        "pandas",
        "pyarrow",
        "altair",
        "numpy",
        "matplotlib",
        "pytest",
        "unittest",
        "doctest",
        "pydoc_data",
        "test",
        "tkinter.test",
        "PyQt5",
        "PySide6",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SnapTranslate",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # 窗口程序：日志走数据目录里的 划词日志.txt
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "snaptranslate.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SnapTranslate",
)
