"""把打包产物做成"发布用便携包"，并（可选）上传到 GitHub Release。

设计约定：**仓库里只放源码与构建脚本，exe 只作为 Release 资产存在**。
本脚本负责后半段：

    python scripts\\make_release.py --tag v2.1.0                 # 只生成 releases/ 下的 zip
    python scripts\\make_release.py --tag v2.1.0 --upload         # 再建/更新 GitHub Release 并上传
    python scripts\\make_release.py --tag v2.1.0 --upload --build # 先打包再发

``--upload`` 需要 ``GITHUB_TOKEN``（有 ``repo`` 权限即可）；仓库从 ``origin`` 自动识别，
也可以用 ``--repo owner/name`` 指定。上传是**幂等**的：同名资产会先删再传，Release 已存在则更新说明。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_NAME = "SnapTranslate"
RELEASES_DIR = ROOT / "releases"

#: 不该进发布包的运行期数据（本机跑过就会留下）
RUNTIME_FILES = {
    "vocab.json",
    "main_settings.json",
    "vocab_review_settings.json",
    "api_key.txt",
    "划词日志.txt",
    "self-check.txt",
}

#: 便携包根目录里附一份上手指引（下载的人不一定会去翻仓库）
USAGE_FILENAME = "使用说明.txt"
USAGE_TEMPLATE = """SnapTranslate 便携版 {tag}
=====================================

怎么启动
--------
双击 SnapTranslate.exe —— 打开"控制台"（三个入口按钮 + 托盘常驻）。
也可以直接启动某个窗口（做快捷方式时用）：

    SnapTranslate.exe --app=translate   划词翻译
    SnapTranslate.exe --app=review      生词复习
    SnapTranslate.exe --app=admin       词表管理
    SnapTranslate.exe --self-check      自检（结果写 self-check.txt）

默认热键（在划词窗口里可改）
---------------------------
    ctrl+i   中译英输入框（输入中文，回车出英文）
    alt+z    划词翻译
    tab+q    截图 OCR
    tab+e    收录最近一条

窗口切换与退出
--------------
托盘图标（屏幕右下角）右键可切换三个窗口，双击回到控制台。
勾了"关闭窗口时最小化到托盘常驻"时，关窗口只是隐藏——**退出请用托盘菜单或控制台里的"退出"**，
它会一并结束由它启动的子进程。

数据放在哪
----------
就在本目录（便携：整个文件夹拷走即可迁移）：

    vocab.json                 生词本
    main_settings.json         热键 / 音量 / 代理
    vocab_review_settings.json 复习端设置
    backups\\                   词表自动备份
    划词日志.txt                运行日志（没有控制台窗口，日志写这里）
    self-check.txt             自检报告

也可以把数据放到别处：设置环境变量 SNAPTRANSLATE_DATA_DIR=<目录>。

需要自己装的东西
----------------
- **截图 OCR** 需要本机安装 Tesseract-OCR（含 eng + chi_sim 语言包），不装只影响截图 OCR，其它功能正常。
- **用 DeepSeek 批量生成例句** 需要在界面里填一次 API Key。

已知提示
--------
- 本程序**没有代码签名**，首次运行 Windows SmartScreen 会提示"未知发布者"，点"仍要运行"即可。
- 仅支持 Windows（依赖 Win32 的全局热键轮询、剪贴板与托盘）。
- 网页复习端不在此包内（它是单独的 SnapTranslateWeb 包）。

源码与问题反馈
--------------
https://github.com/{repo}
"""


def _log(message: str) -> None:
    print(message, flush=True)


# ———————————————————————————— 打包 ————————————————————————————


def build_packages(*, web: bool = False) -> int:
    command = [sys.executable, str(ROOT / "scripts" / "build_packages.py"), "--clean"]
    if web:
        command.append("--web")
    _log(f">>> {' '.join(command)}")
    return subprocess.call(command, cwd=str(ROOT))


def _clean_runtime_files(directory: Path) -> list[str]:
    """删掉本机测试留下的运行期数据，保证发布包是"干净首启"状态。"""
    removed: list[str] = []
    for path in directory.iterdir():
        if path.name in RUNTIME_FILES and path.is_file():
            path.unlink()
            removed.append(path.name)
        elif path.name == "backups" and path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            removed.append("backups/")
    return removed


def make_bundle(tag: str, *, repo: str, dist_name: str = DIST_NAME) -> Path:
    """把 ``dist/<dist_name>`` 打成便携 zip（内含同名顶层目录），返回 zip 路径。"""
    source = ROOT / "dist" / dist_name
    if not source.is_dir():
        raise SystemExit(f"[FAIL] 找不到产物目录：{source}（先跑 scripts/build_packages.py）")

    removed = _clean_runtime_files(source)
    if removed:
        _log(f"  已清掉运行期数据：{', '.join(removed)}")

    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    archive = RELEASES_DIR / f"{dist_name}-{tag}-win64-portable.zip"
    root_name = f"{dist_name}-{tag}"
    usage = USAGE_TEMPLATE.format(tag=tag, repo=repo)

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr(f"{root_name}/{USAGE_FILENAME}", usage)
        for path in sorted(source.rglob("*")):
            if path.is_file():
                zf.write(path, f"{root_name}/{path.relative_to(source).as_posix()}")
    size_mb = archive.stat().st_size / 1048576
    _log(f"[OK] 便携包：{archive}  ({size_mb:.1f} MB)")
    return archive


# ———————————————————————————— 上传 Release ————————————————————————————


def _api(url: str, token: str, *, method: str = "GET", payload: dict | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"token {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("User-Agent", "SnapTranslate-release")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - 固定 api.github.com
        body = response.read()
    return json.loads(body) if body else {}


def upload_release(tag: str, archive: Path, *, repo: str, token: str, notes: str) -> None:
    """建/更新 Release 并上传资产（同名资产先删后传，可重复执行）。"""
    api = f"https://api.github.com/repos/{repo}"
    try:
        release = _api(f"{api}/releases/tags/{tag}", token)
        _log(f"  Release 已存在（id={release['id']}），更新说明")
        release = _api(f"{api}/releases/{release['id']}", token, method="PATCH", payload={"body": notes})
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        _log("  新建 Release")
        release = _api(
            f"{api}/releases",
            token,
            method="POST",
            payload={"tag_name": tag, "name": tag, "body": notes, "draft": False, "prerelease": False},
        )

    for asset in release.get("assets", []):
        if asset["name"] == archive.name:
            _log(f"  同名资产已存在，先删除：{asset['name']}")
            _api(f"{api}/releases/assets/{asset['id']}", token, method="DELETE")

    upload_url = (
        f"https://uploads.github.com/repos/{repo}/releases/{release['id']}/assets"
        f"?name={urllib.parse.quote(archive.name)}"
    )
    request = urllib.request.Request(upload_url, data=archive.read_bytes(), method="POST")
    request.add_header("Authorization", f"token {token}")
    request.add_header("Content-Type", "application/zip")
    request.add_header("User-Agent", "SnapTranslate-release")
    with urllib.request.urlopen(request, timeout=600) as response:  # noqa: S310
        info = json.loads(response.read())
    _log(f"[OK] 已上传资产：{info['name']}  ({info['size'] / 1048576:.1f} MB)")
    _log(f"     {info['browser_download_url']}")


# ———————————————————————————— 辅助 ————————————————————————————


def detect_repo() -> str:
    """从 origin 推断 owner/name（支持 https 与 ssh 两种写法）。"""
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], cwd=str(ROOT), text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise SystemExit("[FAIL] 取不到 origin，请用 --repo owner/name 指定")
    match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<name>[^/]+?)(?:\.git)?$", url)
    if not match:
        raise SystemExit(f"[FAIL] 无法从 origin 解析仓库：{url}")
    return f"{match.group('owner')}/{match.group('name')}"


def default_notes(tag: str, repo: str) -> str:
    return (
        f"## SnapTranslate 分层重构版 {tag}（Windows 便携包）\n\n"
        "下载 `*-portable.zip` 解压即用（内含 `使用说明.txt`）：双击 `SnapTranslate.exe` 打开控制台，"
        "或用 `--app=translate|review|admin` 直接启动某个窗口。\n\n"
        "**数据跟着 exe**：`vocab.json` / 设置 / `backups/` / `划词日志.txt` 都在解压目录里，"
        "整个文件夹拷走即可迁移。\n\n"
        "包含：划词翻译（含中译英输入框 `ctrl+i`）、截图 OCR、生词本复习、词表管理、"
        "控制台 + 托盘常驻（一个 exe 管四个窗口）、单实例保护。\n\n"
        "注意：未做代码签名，首次运行会有 SmartScreen 提示；截图 OCR 需自装 Tesseract；仅支持 Windows。\n"
        "网页复习端不在本包内。\n\n"
        f"源码（可自由修改）：https://github.com/{repo}\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成/上传 SnapTranslate 便携发布包")
    parser.add_argument("--tag", required=True, help="版本标签，如 v2.1.0（上传时作为 Release 标签）")
    parser.add_argument("--repo", default=None, help="owner/name（默认从 origin 推断）")
    parser.add_argument("--upload", action="store_true", help="上传到 GitHub Release（需要 GITHUB_TOKEN）")
    parser.add_argument("--build", action="store_true", help="先跑一遍 scripts/build_packages.py")
    parser.add_argument("--notes", default=None, help="Release 说明（Markdown 文件路径）")
    parser.add_argument("--dist-name", default=DIST_NAME, help="dist 下的产物目录名")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    repo = args.repo or detect_repo()
    if args.build and build_packages() != 0:
        return 1

    archive = make_bundle(args.tag, repo=repo, dist_name=args.dist_name)
    if not args.upload:
        _log("（未加 --upload，仅生成 zip）")
        return 0

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        _log("[FAIL] --upload 需要环境变量 GITHUB_TOKEN（repo 权限）")
        return 2
    notes = Path(args.notes).read_text(encoding="utf-8") if args.notes else default_notes(args.tag, repo)
    upload_release(args.tag, archive, repo=repo, token=token, notes=notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
