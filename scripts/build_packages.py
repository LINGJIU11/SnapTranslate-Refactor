"""打包脚本：``python scripts/build_packages.py [--web] [--onefile] [--clean]``。

- 默认打**主包**（`dist/SnapTranslate/`）：启动器 + 托盘 + 三个 Tk 应用，**不含 streamlit**；
- ``--web`` 再打**Web 包**（`dist/SnapTranslateWeb/`）：含 streamlit 的网页复习端；
- ``--onefile`` 出单文件 exe（分发省事，代价是启动要解包到临时目录）；
- 打完自动跑一遍 ``SnapTranslate.exe --self-check``（打包验收，见 bootstrap/launcher.py）。

前置：``pip install pyinstaller``（PyInstaller ≥ 6.15 才支持 Python 3.14）。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
WORK = ROOT / ".pyinstaller-build"

SPECS = {
    "main": ROOT / "packaging" / "snaptranslate.spec",
    "web": ROOT / "packaging" / "snaptranslate_web.spec",
}
ONE_FILE_ARGS = ["--onefile"]
DIST_NAMES = {"main": "SnapTranslate", "web": "SnapTranslateWeb"}


def _run(command: list[str]) -> int:
    print(f"\n>>> {' '.join(command)}\n", flush=True)
    return subprocess.call(command, cwd=str(ROOT))


def _purge(*paths: Path) -> None:
    for path in paths:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


def build(target: str, *, onefile: bool, clean: bool) -> int:
    spec = SPECS[target]
    if not spec.is_file():
        print(f"[FAIL] 找不到 spec：{spec}")
        return 2
    if clean:
        _purge(DIST / DIST_NAMES[target], WORK)
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--distpath",
        str(DIST),
        "--workpath",
        str(WORK / target),
        # 注意：**不要**传 --specpath —— spec 里用 SPECPATH 反推工程根目录，
        # 改了它 ROOT 就会算到 work 目录去（踩过一次）
        *(ONE_FILE_ARGS if onefile else []),
        str(spec),
    ]
    return _run(command)


def self_check(target: str, *, onefile: bool) -> int:
    """对打出来的 exe 跑 ``--self-check``（这是打包验收的关键一步）。"""
    name = DIST_NAMES[target]
    exe = DIST / name / f"{name}.exe" if not onefile else DIST / f"{name}.exe"
    if not exe.is_file():
        print(f"[FAIL] 没找到产物：{exe}")
        return 2
    print(f"\n=== 打包产物自检：{exe} ===")
    return _run([str(exe), "--self-check"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="打包 SnapTranslate（onedir 默认，可选 onefile/web）")
    parser.add_argument("--web", action="store_true", help="打包含 streamlit 的 Web 复习端")
    parser.add_argument("--onefile", action="store_true", help="打成单文件 exe")
    parser.add_argument("--clean", action="store_true", help="构建前清掉 dist/work 里的旧产物")
    parser.add_argument("--no-check", action="store_true", help="跳过产物自检")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    targets = ["main", "web"] if args.web else ["main"]
    exit_code = 0
    for target in targets:
        code = build(target, onefile=args.onefile, clean=args.clean)
        if code != 0:
            print(f"[FAIL] {target} 构建失败（exit={code}）")
            exit_code = code
            continue
        if not args.no_check:
            check_code = self_check(target, onefile=args.onefile)
            if check_code != 0:
                print(f"[FAIL] {target} 产物自检未通过（exit={check_code}）")
                exit_code = check_code
        print(f"[OK] {target} 构建完成 → {DIST}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
