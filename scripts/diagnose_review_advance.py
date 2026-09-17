"""诊断：点「认识 / 模糊 / 不认识」之后，卡片上的英文会不会切到下一个。

原版（``C:\\Translate\\SnapTranslate\\vocab_review.py``）与重构版各自在临时目录里
放一份 5 条的假词表，**构造真实 Tk 窗口**（``withdraw``，不显示），在 ``score_asc``
模式下评一次「认识」，然后比较两件事：

* 界面上显示的词（``word_var``）
* 会话真正指向的词（``session.current()`` / ``_current_item()``）

两者不一致 = "**状态推进了，但界面没重绘**"。

用法::

    python scripts/diagnose_review_advance.py          # 两侧都跑，打印对照表
    python scripts/diagnose_review_advance.py new      # 只跑重构版（子进程用）
    python scripts/diagnose_review_advance.py orig     # 只跑原版（子进程用）
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGINAL = r"C:\Translate\SnapTranslate\vocab_review.py"

FAKE_VOCAB = [
    {"word": "alpha", "meaning": "第一个", "example": "alpha example", "example_zh": "例句一", "score": 50.0, "reviews": 0},
    {"word": "bravo", "meaning": "第二个", "example": "bravo example", "example_zh": "例句二", "score": 50.0, "reviews": 0},
    {"word": "charlie", "meaning": "第三个", "example": "charlie example", "example_zh": "例句三", "score": 50.0, "reviews": 0},
    {"word": "delta", "meaning": "第四个", "example": "delta example", "example_zh": "例句四", "score": 50.0, "reviews": 0},
    {"word": "echo", "meaning": "第五个", "example": "echo example", "example_zh": "例句五", "score": 50.0, "reviews": 0},
]


def _prepare(tmp: str) -> str:
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    with open(os.path.join(tmp, "vocab.json"), "w", encoding="utf-8") as fh:
        json.dump(FAKE_VOCAB, fh, ensure_ascii=False, indent=2)
    return tmp


def _report(side: str, before: dict, after: dict) -> dict:
    result = {"side": side, "before": before, "after": after}
    result["label_changed"] = before["shown_word"] != after["shown_word"]
    result["state_changed"] = before["state_word"] != after["state_word"]
    result["label_matches_state"] = after["shown_word"] == after["state_word"]
    print(f"--- {side} ---")
    for key, value in before.items():
        print(f"  评分前 {key:<12}= {value!r}")
    for key, value in after.items():
        print(f"  评分后 {key:<12}= {value!r}")
    print(f"  界面显示的词是否变化 = {result['label_changed']}")
    print(f"  会话指向的词是否变化 = {result['state_changed']}")
    print(f"  界面与会话是否一致   = {result['label_matches_state']}")
    return result


def check_new() -> dict:
    """重构版：真窗口 + 真用例。"""
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from snaptranslate.bootstrap.container import Container, DataPaths
    from snaptranslate.presentation.tk.review_window import ReviewApp

    tmp = _prepare(os.path.join(ROOT, ".tmp-diag-review-new"))
    app = ReviewApp(Container(DataPaths.under(tmp)).review_app_deps())
    app.root.withdraw()
    app._sort_mode_var.set("score_asc")
    app._on_sort_mode_change()

    def snapshot() -> dict:
        entry = app.session.current()
        return {
            "shown_word": app._word_var.get(),
            "progress": app._progress_var.get(),
            "score": app._score_var.get(),
            "state_word": entry.word if entry else None,
            "position": app.session.position,
        }

    before = snapshot()
    app._apply_grade("know")
    after = snapshot()
    app.root.destroy()
    shutil.rmtree(tmp, ignore_errors=True)
    return _report("重构版 ReviewApp", before, after)


def check_orig() -> dict:
    """原版：把脚本复制到临时目录（连同假词表），避免动用户数据。"""
    import importlib.util

    if not os.path.isfile(ORIGINAL):
        print(f"[跳过] 找不到原版脚本：{ORIGINAL}")
        return {"side": "原版", "skipped": True}

    tmp = _prepare(os.path.join(ROOT, ".tmp-diag-review-orig"))
    script = os.path.join(tmp, "vocab_review.py")
    shutil.copy2(ORIGINAL, script)

    spec = importlib.util.spec_from_file_location("vocab_review_orig", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    app = mod.VocabReviewApp()
    app.root.withdraw()
    app.sort_mode_var.set("score_asc")
    app._on_sort_mode_change()

    def snapshot() -> dict:
        item = app._current_item()
        return {
            "shown_word": app.word_var.get(),
            "progress": app.progress_var.get(),
            "score": app.score_var.get(),
            "state_word": item.get("word") if item else None,
            "position": app.pos,
        }

    before = snapshot()
    app._apply_grade("know")
    after = snapshot()
    app.root.destroy()
    shutil.rmtree(tmp, ignore_errors=True)
    return _report("原版 VocabReviewApp", before, after)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in {"new", "orig"}:
        check_new() if sys.argv[1] == "new" else check_orig()
        return 0

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    results = []
    for side in ("new", "orig"):
        completed = subprocess.run(
            [sys.executable, os.path.abspath(__file__), side],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        print((completed.stdout or "").rstrip())
        if completed.stderr:
            print((completed.stderr or "").rstrip(), file=sys.stderr)
        results.append(completed.returncode)

    print()
    print("结论：")
    print("  原版      —— 评分后界面显示的词应随会话一起前进（_advance_after_grade 末尾有 _show_card()）")
    print("  重构版    —— 若“界面显示的词是否变化 = False、会话指向的词是否变化 = True”，")
    print("               说明用例推进了会话，但表示层没有再渲染这张卡（回归）。")
    return 0 if all(code == 0 for code in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
