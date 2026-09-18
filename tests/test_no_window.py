"""回归：**所有子进程都必须走"不弹窗"参数**（KNOWN_ISSUES.md §八 N3）。

第一版打包的实际体验问题是"划词翻译时闪一个 PowerShell 窗口"：打包成窗口程序后父进程
没有控制台，直接 ``subprocess.run(["powershell", ...])`` 会让 Windows 给子进程新分配一个
控制台窗口。源码运行看不出来（父进程有控制台，子进程直接继承）。

这里放两道闸：

1. 机制测试：``hidden_kwargs()`` 确实带上 ``CREATE_NO_WINDOW`` 与 ``SW_HIDE``，
   且 ``run_hidden`` / ``popen_hidden`` 把它们传给了 ``subprocess``；
2. **静态检查**：``src/snaptranslate`` 里除了 ``process/no_window.py`` 自己，
   不允许出现裸的 ``subprocess.run/Popen/call/check_output``。
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest import mock

from snaptranslate.infrastructure.process import no_window

SRC = Path(__file__).resolve().parents[1] / "src" / "snaptranslate"
HELPER = SRC / "infrastructure" / "process" / "no_window.py"

#: 不允许裸调用的 subprocess 入口
RAW_FUNCTIONS = {"run", "Popen", "call", "check_call", "check_output"}


def _raw_subprocess_calls(text: str) -> list[int]:
    """用 AST 找真正的 ``subprocess.xxx(...)`` 调用（**不匹配字符串/注释里出现的字样**）。"""
    tree = ast.parse(text)
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "subprocess"
            and func.attr in RAW_FUNCTIONS
        ):
            lines.append(node.lineno)
    return lines


class HiddenProcessTests(unittest.TestCase):
    def test_hidden_kwargs_have_both_safeguards(self) -> None:
        kwargs = no_window.hidden_kwargs()
        if not kwargs:  # 非 Windows：空字典是预期行为
            self.skipTest("非 Windows 平台")
        self.assertEqual(kwargs["creationflags"], no_window.CREATE_NO_WINDOW)
        startupinfo = kwargs["startupinfo"]
        self.assertTrue(startupinfo.dwFlags & no_window.STARTF_USESHOWWINDOW)
        self.assertEqual(startupinfo.wShowWindow, no_window.SW_HIDE)

    def test_run_hidden_forwards_kwargs(self) -> None:
        with mock.patch.object(no_window.subprocess, "run", return_value="done") as fake:
            result = no_window.run_hidden(["cmd", "/c", "echo"], stdout="devnull")

        self.assertEqual(result, "done")
        command, = fake.call_args.args
        kwargs = fake.call_args.kwargs
        self.assertEqual(command, ["cmd", "/c", "echo"])
        # 调用方参数保留，同时自动带上"不弹窗"参数
        self.assertEqual(kwargs["stdout"], "devnull")
        self._assert_hidden(kwargs)

    def test_popen_hidden_forwards_kwargs(self) -> None:
        with mock.patch.object(no_window.subprocess, "Popen", return_value="handle") as fake:
            handle = no_window.popen_hidden(["app", "--flag"], close_fds=True)

        self.assertEqual(handle, "handle")
        command, = fake.call_args.args
        kwargs = fake.call_args.kwargs
        self.assertEqual(command, ["app", "--flag"])
        self.assertTrue(kwargs["close_fds"])
        self._assert_hidden(kwargs)

    def _assert_hidden(self, kwargs: dict) -> None:
        """断言"不弹窗"两道保险都在（STARTUPINFO 每次都是新对象，按字段比）。"""
        if not no_window.hidden_kwargs():  # 非 Windows
            self.assertNotIn("creationflags", kwargs)
            return
        self.assertEqual(kwargs["creationflags"], no_window.CREATE_NO_WINDOW)
        startupinfo = kwargs["startupinfo"]
        self.assertTrue(startupinfo.dwFlags & no_window.STARTF_USESHOWWINDOW)
        self.assertEqual(startupinfo.wShowWindow, no_window.SW_HIDE)


class NoRawSubprocessTests(unittest.TestCase):
    """静态检查：源码里不允许绕过 ``no_window`` 直接起子进程。"""

    def test_only_helper_touches_subprocess_directly(self) -> None:
        offenders: list[str] = []
        for path in sorted(SRC.rglob("*.py")):
            if path == HELPER:
                continue
            text = path.read_text(encoding="utf-8")
            for line in _raw_subprocess_calls(text):
                offenders.append(f"{path.relative_to(SRC)}:{line}")
        self.assertEqual(
            offenders,
            [],
            "以下位置直接调用了 subprocess（打包后会让子进程弹出控制台窗口），"
            "请改用 infrastructure/process/no_window.py 的 run_hidden / popen_hidden：\n  "
            + "\n  ".join(offenders),
        )

    def test_caller_uses_helper(self) -> None:
        """``windows_sapi`` 必须 import 助手，而不是自己拼 creationflags。"""
        sapi = (SRC / "infrastructure" / "tts" / "windows_sapi.py").read_text(encoding="utf-8")
        self.assertIn("run_hidden", sapi)
        self.assertEqual(_raw_subprocess_calls(sapi), [])

    def test_detector_actually_detects(self) -> None:
        """自测：检查器本身要能抓到裸调用（否则这条门禁是假的）。"""
        sample = "import subprocess\n\ndef f():\n    return subprocess.run(['a'])\n"
        self.assertEqual(_raw_subprocess_calls(sample), [4])
        # 字符串/注释里出现不算
        harmless = "DOC = 'subprocess.run(['\n# subprocess.Popen(x)\n"
        self.assertEqual(_raw_subprocess_calls(harmless), [])


if __name__ == "__main__":
    unittest.main()
