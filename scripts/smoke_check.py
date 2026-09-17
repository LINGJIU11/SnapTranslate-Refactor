"""冒烟自检：全包导入 + 依赖装配 + 关键纯函数断言。

不联网、不启动任何 GUI；只验证"结构是活的"。

用法::

    python scripts/smoke_check.py
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  [OK]   {label}")
    else:
        print(f"  [FAIL] {label} {detail}")
        FAILURES.append(f"{label} {detail}".strip())


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def import_all_modules() -> None:
    section("1. 全包导入（逐模块）")
    import snaptranslate

    failed = 0
    total = 0
    for module in pkgutil.walk_packages(snaptranslate.__path__, prefix="snaptranslate."):
        total += 1
        try:
            importlib.import_module(module.name)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  [FAIL] {module.name}: {type(exc).__name__}: {exc}")
            traceback.print_exc()
    check(f"导入 {total} 个模块，失败 {failed} 个", failed == 0)


def build_container() -> None:
    section("2. 依赖装配（Container + 四个依赖包）")
    from snaptranslate.bootstrap.container import Container

    container = Container()
    deps = {
        "translate": container.translate_app_deps(),
        "review": container.review_app_deps(),
        "web_review": container.web_review_deps(),
        "admin": container.admin_app_deps(),
    }
    for name, bundle in deps.items():
        check(f"{name} 依赖包构建成功", bundle is not None)
    check("translate deps 含热键监听器", deps["translate"].hotkey_listener is not None)
    check("translate deps 含窗口激活端口", deps["translate"].window_activator is not None)
    check("translate deps 含启动备份用例", callable(deps["translate"].startup_backup))
    check("review deps 含例句生成器工厂", callable(deps["review"].generator_factory))
    check("admin deps 暴露词表路径", bool(deps["admin"].vocab_path))


def pure_logic() -> None:
    section("3. 关键纯函数")
    from snaptranslate.domain.models.hotkey import (
        DEFAULT_HOTKEYS,
        Hotkey,
        feature_hotkeys,
        label_or_placeholder,
    )
    from snaptranslate.domain.models.translation import (
        AUTO_TO_CHINESE,
        CHINESE_TO_ENGLISH,
        TranslationResult,
    )
    from snaptranslate.domain.models.vocab_entry import Vocabulary
    from snaptranslate.domain.services.review_session import ReviewSession
    from snaptranslate.domain.services.scoring import apply_grade, item_score
    from snaptranslate.domain.services.text_cleaning import clean_text, is_likely_english, truncate
    from snaptranslate.infrastructure.llm.deepseek import parse_bilingual_response
    from snaptranslate.infrastructure.translation.cache import TranslationCache
    from snaptranslate.infrastructure.translation.google import parse_clients5_payload

    check("clean_text 折叠空白", clean_text("  a\r\n b  c ") == "a b c")
    check("is_likely_english 命中", is_likely_english("hello") and not is_likely_english("你好"))
    check("truncate 截断加省略号", truncate("x" * 200).endswith("...") and len(truncate("x" * 200)) == 123)
    check("item_score 夹取", item_score({"score": 999}) == 100.0 and item_score({}) == 50.0)
    grade = apply_grade({"score": 50.0, "reviews": 0}, "know", False)
    check("apply_grade = +10", grade == (50.0, 60.0, 10.0, 1))
    check("Hotkey 解析合法", Hotkey.parse("ctrl+l") is not None and Hotkey.parse("tab+q") is not None)
    check("Hotkey 解析非法", Hotkey.parse("ctrl+") is None and Hotkey.parse("meta+k") is None)
    check("热键标签占位", label_or_placeholder("") == "（未设置）" and Hotkey.parse("ctrl+l").label == "CTRL+L")
    check("默认热键三组", set(DEFAULT_HOTKEYS) == {"translate", "snip", "save_last"})
    check(
        "默认热键四组（含新增的中译英输入框）",
        set(feature_hotkeys()) == {"translate", "snip", "save_last", "input"}
        and feature_hotkeys()["input"] == "ctrl+i",
    )
    check(
        "翻译方向：默认自动→中，新增中→英",
        AUTO_TO_CHINESE.variant == "" and CHINESE_TO_ENGLISH.langpair == "zh-CN|en",
    )
    check(
        "TranslationResult.display_text 带标签",
        TranslationResult("你好", "Google").display_text == "你好\n（Google 最快返回）",
    )
    check("TranslationResult.display_text 无标签", TranslationResult("你好").display_text == "你好")
    check(
        "clients5 载荷解析",
        parse_clients5_payload([["你好", "en"], ["世界", "en"]]) == "你好世界",
    )
    check(
        "双语 JSON 解析（含围栏）",
        parse_bilingual_response('```json\n{"example":"Hi","example_zh":"你好"}\n```') == ("Hi", "你好"),
    )
    cache = TranslationCache(max_size=2)
    cache.put("google", "a", "(无翻译结果)")
    check("缓存不存空结果", cache.get("google", "a") is None)
    cache.put("google", "a", "甲")
    cache.put("google", "b", "乙")
    cache.put("google", "c", "丙")
    check("缓存 LRU 淘汰", cache.get("google", "a") is None and cache.get("google", "c") == "丙")

    vocabulary = Vocabulary(
        [
            {"word": "urban", "meaning": "城市的", "score": 30, "example": "", "example_zh": ""},
            {"word": "theft", "meaning": "盗窃", "score": 80, "example": "x", "example_zh": "y"},
        ]
    )
    session = ReviewSession(vocabulary, "score_asc")
    check("顺序：低分优先", session.order == [0, 1])
    session.set_mode("score_desc")
    check("顺序：高分优先", session.order == [1, 0])
    check("待补例句计数", vocabulary.pending_example_count() == 1)
    check("有例句计数", vocabulary.with_example_count() == 1)
    check("最近词条反转去重", vocabulary.recent_words(5) == ["theft", "urban"])


def main() -> int:
    print(f"SnapTranslate 冒烟自检（工程根目录：{ROOT}）")
    import_all_modules()
    build_container()
    pure_logic()
    print()
    if FAILURES:
        print(f"[FAIL] 共 {len(FAILURES)} 项未通过")
        return 1
    print("[OK] 全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
