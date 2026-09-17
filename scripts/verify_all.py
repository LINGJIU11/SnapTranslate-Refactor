"""一键跑齐所有约束检查（分层的、行为的、界面的）。

用法::

    python scripts/verify_all.py            # 全部检查
    python scripts/verify_all.py --quick    # 跳过需要真实 Tk / Streamlit 的两项

任何一步非 0 退出，本脚本就以非 0 结束，并打印失败项的最后若干行输出。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 本脚本自己的 stdout 也可能是 cp936（被管道重定向时），打印含中文/emoji 的子进程输出会崩
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: 统一给子进程 UTF-8 输出：Windows 控制台默认 cp936，会把 📘 这类字符变成 UnicodeEncodeError
CHILD_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}

ALL_STEPS: list[tuple[str, list[str]]] = [
    ("分层依赖校验", [sys.executable, "scripts/check_layering.py"]),
    ("单元测试", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."]),
    ("冒烟自检（导入 + 装配 + 纯函数）", [sys.executable, "scripts/smoke_check.py"]),
    ("与原版逐函数/流程对拍", [sys.executable, "scripts/parity_check.py"]),
    ("GUI 冒烟（真实 Tk 构造后销毁）", [sys.executable, "scripts/gui_smoke.py", "--with-tk"]),
    ("Streamlit 页面结构对拍", [sys.executable, "scripts/web_smoke.py"]),
]

QUICK_SKIP = {"GUI 冒烟（真实 Tk 构造后销毁）", "Streamlit 页面结构对拍"}

TAIL_LINES = 6


def run_step(name: str, command: list[str]) -> tuple[str, str]:
    """跑一步，返回 ``("pass" | "fail" | "skip", 末尾若干行输出)``。

    子进程**首行以 ``[SKIP]`` 开头且退出码为 0** 时记为跳过——典型场景是换一台电脑后
    没有原版目录，``parity_check.py`` 会自己打印 ``[SKIP] 未找到原版目录…``。
    跳过不计入失败，但在汇总里如实标出来，免得"绿"得含糊。
    """
    print(f"\n{'=' * 78}\n>>> {name}\n{'=' * 78}")
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=CHILD_ENV,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    print(output.rstrip())
    if completed.returncode != 0:
        status = "fail"
    elif output.lstrip().startswith("[SKIP]"):
        status = "skip"
    else:
        status = "pass"
    tail = "\n".join(output.rstrip().splitlines()[-TAIL_LINES:])
    return status, tail


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    quick = "--quick" in argv
    steps = [item for item in ALL_STEPS if not (quick and item[0] in QUICK_SKIP)]

    results: list[tuple[str, str, str]] = []
    for name, command in steps:
        status, tail = run_step(name, command)
        results.append((name, status, tail))

    print(f"\n{'=' * 78}\n汇总\n{'=' * 78}")
    failed = 0
    skipped_names: list[str] = []
    for name, status, _tail in results:
        print(f"  [{status.upper()}] {name}")
        if status == "fail":
            failed += 1
        elif status == "skip":
            skipped_names.append(name)
    if failed:
        print(f"\n失败 {failed} 项，失败项的最后 {TAIL_LINES} 行输出：")
        for name, status, tail in results:
            if status == "fail":
                print(f"\n--- {name} ---\n{tail}")
        return 1
    notes = []
    quick_skipped = len(ALL_STEPS) - len(steps)
    if quick_skipped:
        notes.append(f"--quick 跳过 {quick_skipped} 项")
    if skipped_names:
        notes.append("跳过：" + "、".join(skipped_names) + "（换机器后缺原版目录属正常，克隆上游即可恢复）")
    suffix = f"（{'；'.join(notes)}）" if notes else ""
    print(f"\n全部 {len(results)} 项通过{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
