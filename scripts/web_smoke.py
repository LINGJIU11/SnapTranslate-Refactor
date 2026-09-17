"""Streamlit 页面的结构对拍与冒烟（用官方 ``AppTest``，无需启动服务、无需浏览器）。

做两件事：

1. **冒烟**：用临时数据目录渲染新页面，确认不抛异常、控件数与预期一致；
2. **结构对拍**：把原版 ``vocab_review_web.py`` 在同样的临时数据目录下渲染一遍，
   逐项比较标题、按钮文案顺序、下拉框标签与选项、以及首屏文案。

用法::

    python scripts/web_smoke.py                          # 冒烟 + 对拍（原版目录存在时）
    python scripts/web_smoke.py <原版目录>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))  # 让 `tests` 包可导入（复用工程内临时目录）

from tests._tmp import temp_dir  # noqa: E402

DEFAULT_ORIGINAL = Path(r"C:\Translate\SnapTranslate")

VOCAB_SAMPLE = [
    {"word": "urban", "meaning": "城市的", "example": "", "example_zh": "", "score": 50.0, "reviews": 0},
    {"word": "theft", "meaning": "盗窃", "example": "The store installed cameras.", "example_zh": "商店装了摄像头。",
     "score": 30.0, "reviews": 2},
]

FAILURES: list[str] = []
DIFFS: list[str] = []


def _write_vocab(directory: Path) -> None:
    (directory / "vocab.json").write_text(json.dumps(VOCAB_SAMPLE, ensure_ascii=False, indent=2), encoding="utf-8")


def _new_page_script(directory: Path) -> Path:
    script = directory / "page_new.py"
    script.write_text(
        "import sys\n"
        f"sys.path.insert(0, r'{ROOT / 'src'}')\n"
        "from snaptranslate.bootstrap.container import Container\n"
        "from snaptranslate.presentation.web.streamlit_review import render_page\n"
        "render_page(Container().web_review_deps())\n",
        encoding="utf-8",
    )
    return script


def _original_page_script(directory: Path, original_dir: Path) -> Path:
    script = directory / "page_original.py"
    script.write_text(
        "import importlib.util, sys\n"
        f"sys.path.insert(0, r'{ROOT / 'src'}')\n"
        f"spec = importlib.util.spec_from_file_location('orig_web', r'{original_dir / 'vocab_review_web.py'}')\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "sys.modules['orig_web'] = mod\n"
        "spec.loader.exec_module(mod)\n"
        f"mod.DEFAULT_VOCAB = r'{directory / 'vocab.json'}'\n"
        f"mod.DEFAULT_KEY_FILE = r'{directory / 'api_key.txt'}'\n"
        f"mod.BACKUP_DIR = r'{directory / 'backups'}'\n"
        "mod.main()\n",
        encoding="utf-8",
    )
    return script


def _run(script: Path, *, data_dir: Path):
    from streamlit.testing.v1 import AppTest

    import os

    os.environ["SNAPTRANSLATE_DATA_DIR"] = str(data_dir)
    app = AppTest.from_file(str(script), default_timeout=60)
    app.run()
    return app


def _snapshot(app) -> dict:
    return {
        "title": [t.value for t in app.title],
        "buttons": [b.label for b in app.button],
        "selectboxes": [(s.label, list(s.options)) for s in app.selectbox],
        "text_inputs": [t.label for t in app.text_input],
        "subheaders": [s.value for s in app.subheader],
        "warnings": [w.value for w in app.warning],
        "infos": [i.value for i in app.info],
    }


def _compare(label: str, original, refactored) -> None:
    if original == refactored:
        print(f"  [OK]   {label}")
        return
    print(f"  [DIFF] {label}")
    print(f"         原版：{original!r}")
    print(f"         新版：{refactored!r}")
    DIFFS.append(label)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    original_dir = Path(argv[0]).resolve() if argv else DEFAULT_ORIGINAL

    print("=== 1. 新页面冒烟（AppTest 渲染） ===")
    with temp_dir() as new_dir:
        _write_vocab(new_dir)
        try:
            new_app = _run(_new_page_script(new_dir), data_dir=new_dir)
        except Exception as exc:  # noqa: BLE001
            print(f"  [FAIL] 渲染异常：{type(exc).__name__}: {exc}")
            FAILURES.append("新页面渲染")
            new_app = None
        if new_app is not None:
            if new_app.exception:
                print(f"  [FAIL] 页面内异常：{new_app.exception}")
                FAILURES.append("新页面渲染")
            else:
                new_snapshot = _snapshot(new_app)
                print(f"  [OK]   渲染无异常：按钮 {len(new_snapshot['buttons'])} 个，下拉框 {len(new_snapshot['selectboxes'])} 个")
                print(f"         标题：{new_snapshot['title']}")
                print(f"         首屏警告：{new_snapshot['warnings']}")

    if not (original_dir / "vocab_review_web.py").is_file():
        print(f"\n[SKIP] 未找到原版目录 {original_dir}，跳过结构对拍")
        return 1 if FAILURES else 0

    print("\n=== 2. 与原版页面结构对拍 ===")
    with temp_dir() as original_tmp, temp_dir() as new_tmp:
        _write_vocab(original_tmp)
        _write_vocab(new_tmp)
        original_app = _run(_original_page_script(original_tmp, original_dir), data_dir=original_tmp)
        new_app = _run(_new_page_script(new_tmp), data_dir=new_tmp)
        original_snapshot = _snapshot(original_app)
        new_snapshot = _snapshot(new_app)
        for key in ("title", "buttons", "selectboxes", "text_inputs", "subheaders"):
            _compare(f"{key}", original_snapshot[key], new_snapshot[key])

    print("\n=== 3. 真实入口渲染（entrypoints/vocab_review_web.py） ===")
    with temp_dir() as entry_dir:
        _write_vocab(entry_dir)
        entry = ROOT / "entrypoints" / "vocab_review_web.py"
        app = _run(entry, data_dir=entry_dir)
        if app.exception:
            print(f"  [FAIL] 入口渲染异常：{app.exception}")
            FAILURES.append("入口渲染")
        else:
            title = [t.value for t in app.title]
            print(f"  [OK]   入口渲染无异常：标题 {title}，按钮 {len(app.button)} 个")
            if title != ["📘 SnapTranslate"]:
                FAILURES.append("入口标题")

    print()
    if FAILURES:
        print(f"[FAIL] 冒烟失败 {len(FAILURES)} 项")
        return 1
    if DIFFS:
        print(f"[DIFF] 结构差异 {len(DIFFS)} 项：{DIFFS}")
        return 1
    print("[OK] 页面渲染无异常，且与原版结构逐项一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
