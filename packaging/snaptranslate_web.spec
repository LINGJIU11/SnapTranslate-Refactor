# Web 复习端单独一包：含 streamlit（体积大，约 +220MB 依赖），入口是 bootstrap/web_launcher.py
# 构建：python scripts/build_packages.py --web
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = Path(SPECPATH).resolve().parent

# streamlit 大量使用运行时动态导入，光靠静态分析会漏（第一次构建就是这样：
# pandas/pyarrow/altair 都进来了，streamlit 本体却没进 PYZ）
hidden = collect_submodules("streamlit") + [
    "streamlit.web.cli",
    "snaptranslate.presentation.web.streamlit_review",
]
datas = collect_data_files("streamlit") + [
    (str(ROOT / "assets" / "snaptranslate.ico"), "assets"),
    # streamlit 需要一个真实存在的脚本路径，把入口脚本一起分发
    (str(ROOT / "src" / "snaptranslate" / "bootstrap" / "streamlit_entry.py"), "assets"),
]

# ``streamlit/version.py`` 会用 importlib.metadata 读**自己的**安装元数据，
# 元数据没打进去就会 PackageNotFoundError（第一次 Web 构建就是这样失败的）。
# 其它库（altair/pandas/numpy…）也可能在读版本号，一并带上，宁可多几 KB。
for _package in (
    "streamlit",
    "altair",
    "pandas",
    "numpy",
    "pyarrow",
    "tornado",
    "click",
    "packaging",
    "protobuf",
    "requests",
    "rich",
    "watchdog",
    "gitpython",
    "jsonschema",
    "pillow",
    "cachetools",
    "tenacity",
    "toml",
    "python-dateutil",
    "pytz",
    "narwhals",
):
    try:
        datas += copy_metadata(_package)
    except Exception:  # 没装的直接跳过
        pass

a = Analysis(
    [str(ROOT / "packaging" / "web_entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "unittest", "doctest", "test", "tkinter.test"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SnapTranslateWeb",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # streamlit 的启动信息/端口提示需要控制台
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
    name="SnapTranslateWeb",
)
