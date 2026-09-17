"""分层约束测试：架构规则必须可执行，而不是只写在文档里。"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_layering.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_layering", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LayeringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checker = _load_checker()

    def test_no_layer_violations(self) -> None:
        violations = self.checker.scan(ROOT)
        self.assertEqual(violations, [], msg="\n".join(violations))

    def test_detects_forbidden_import(self) -> None:
        """用临时目录构造一个违规样本，确认校验器本身有效。"""
        from tests._tmp import temp_dir

        with temp_dir() as tmp:
            package = Path(tmp) / "src" / "snaptranslate" / "domain"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "bad.py").write_text(
                "import requests\nfrom snaptranslate.infrastructure import x\n", encoding="utf-8"
            )
            violations = self.checker.scan(Path(tmp))
            self.assertEqual(len(violations), 2)
            self.assertTrue(any("infrastructure" in item for item in violations))
            self.assertTrue(any("第三方库 requests" in item for item in violations))


if __name__ == "__main__":
    unittest.main()
