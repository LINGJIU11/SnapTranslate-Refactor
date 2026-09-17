"""等价性对拍：把原版脚本与新工程里的实现放在同一批输入上逐函数比对。

这是"纯结构重构"的核心验收手段——**行为等价不是靠读代码声称的，而是跑出来的**。

用法::

    python scripts/parity_check.py                       # 默认原版目录
    python scripts/parity_check.py <原版目录>

若原版目录不存在，脚本会打印 SKIP 并返回 0（新工程可独立使用）。
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DEFAULT_ORIGINAL = Path(r"C:\Translate\SnapTranslate")

RESULTS: list[tuple[bool, str]] = []


def compare(label: str, original, refactored) -> None:
    same = original == refactored
    RESULTS.append((same, label))
    flag = "OK  " if same else "DIFF"
    print(f"  [{flag}] {label}")
    if not same:
        print(f"         原版：{original!r}")
        print(f"         新版：{refactored!r}")


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# —————————————————————————— 各板块对拍 ——————————————————————————


def parity_clean_text(main_mod, ) -> None:
    from snaptranslate.domain.services.text_cleaning import clean_text, is_likely_english

    app_cls = main_mod.TranslatorApp
    samples = ["", "  ", "a\r\nb", "a  b   c", "  前后空格  ", "行1\n行2\r\n行3", "已 经 有空格", "\n\n"]
    for sample in samples:
        compare(f"clean_text({sample!r})", app_cls.clean_text(sample), clean_text(sample))
    for sample in ["", "a", "ab", "你好", "hi 你好", "1 2"]:
        compare(f"is_likely_english({sample!r})", app_cls._is_likely_english(sample), is_likely_english(sample))


def parity_hotkeys(main_mod) -> None:
    from snaptranslate.domain.models import hotkey as hotkey_module
    from snaptranslate.domain.models.hotkey import Hotkey, label_or_placeholder

    app = main_mod.TranslatorApp()
    combos = ["ctrl+l", "CTRL + L", "tab+q", "shift+f1", "alt+1", "tab+space", "ctrl+", "+l", "meta+k",
              "tab+f12", "tab+f13", "ctrl+tab", "  Tab + Q  ", "tab+ä", "ctrl+0"]
    for combo in combos:
        compare(f"normalize_hotkey({combo!r})", app._normalize_hotkey(combo), hotkey_module.normalize(combo))
        original_parsed = app._parse_hotkey(combo)
        ours = Hotkey.parse(combo)
        refactored_parsed = None if ours is None else (ours.modifier, ours.key)
        compare(f"parse_hotkey({combo!r})", original_parsed, refactored_parsed)
        last_token = combo.split("+")[-1]
        compare(
            f"vk_from_key_token({last_token!r})",
            app._vk_from_key_token(last_token),
            __import__(
                "snaptranslate.infrastructure.input.win32_keys", fromlist=["vk_from_key_token"]
            ).vk_from_key_token(last_token),
        )
        compare(f"hotkey_label({combo!r})", _label_of(app, combo), label_or_placeholder(combo))


def _label_of(app, combo: str) -> str:
    app.hotkeys = {"translate": combo, "snip": "tab+q", "save_last": "tab+e"}
    return app._hotkey_label("translate")


def parity_translation(main_mod, *, originals_available: bool = True) -> None:
    import requests

    from snaptranslate.infrastructure.translation.errors import format_translate_failure
    from snaptranslate.infrastructure.translation.google import parse_clients5_payload
    from snaptranslate.infrastructure.translation.mymemory import (
        langpairs_for,
        parse_mymemory_response,
    )

    payloads = [
        [["你好", "en"], ["世界", "en"]],
        [["你好", "en"], None, [], "尾"],
        "纯字符串",
        [["a", "en"]],
        [],
        {"not": "list"},
        [["", "en"], ["b"]],
        [["x", "en"], [123, "en"], ["y", "en"]],
    ]
    for payload in payloads:
        compare(
            f"parse_clients5_payload({payload!r})",
            main_mod._parse_google_clients5_payload(payload),
            parse_clients5_payload(payload),
        )

    for text in ["hello", "你好", "hello 你好", "123", "a"]:
        compare(f"mymemory_langpairs({text!r})", main_mod._mymemory_langpairs(text), langpairs_for(text))

    class _StubResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    mymemory_payloads = [
        {"responseData": {"translatedText": "你好"}},
        {"responseData": {"translatedText": "  "}},
        {"responseData": None},
        {},
        {"responseData": {"translatedText": "MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS"}},
        {"responseData": {"translatedText": "QUOTA EXCEEDED"}},
    ]
    for payload in mymemory_payloads:
        try:
            original_out = main_mod._mymemory_parse(_StubResponse(payload))
            original_marker = ("ok", original_out)
        except RuntimeError as exc:
            original_marker = ("raise", str(exc))
        try:
            refactored_out = parse_mymemory_response(_StubResponse(payload))
            refactored_marker = ("ok", refactored_out)
        except RuntimeError as exc:
            refactored_marker = ("raise", str(exc))
        compare(f"mymemory_parse({payload!r})", original_marker, refactored_marker)

    dns_error = requests.exceptions.ConnectionError("Failed to resolve 'translate.googleapis.com'")
    timeout_error = requests.exceptions.Timeout("读取超时" * 200)
    short_error = requests.exceptions.HTTPError("403 Forbidden")
    generic = ValueError("普通错误" * 200)
    for exc in [dns_error, timeout_error, short_error, generic, ValueError("短错误")]:
        compare(
            f"format_translate_failure({type(exc).__name__})",
            main_mod._format_translate_failure(exc),
            format_translate_failure(exc),
        )


def parity_translate_flow(main_mod) -> None:
    """流程级对拍：文本翻译用例 vs 原 ``_translate_text_job``。

    原版窗口对象在没有 Tk root 时会把 UI 更新全部跳过，但**控制台输出与传给翻译器的文本**
    仍然可观察，正好用来对比"清洗 → 截断 → 交给翻译器 → 展示文本"这条主链路。
    自动朗读被替换为空实现（否则会在本机真的出声）。
    """
    import contextlib
    import io
    import re

    from snaptranslate.application.dto import OutcomeKind
    from snaptranslate.application.progress import ProgressReporter
    from snaptranslate.application.translate_text import TranslateTextUseCase
    from snaptranslate.domain.models.translation import AUTO_TO_CHINESE, Direction, TranslationResult

    class _Translator:
        name = "fake"

        def translate(self, text: str, direction: Direction = AUTO_TO_CHINESE) -> TranslationResult:
            return TranslationResult("你好", "Fake")

    class _Tts:
        def speak(self, *args, **kwargs) -> None:
            pass

        def speak_async(self, *args, **kwargs) -> None:
            pass

    app = main_mod.TranslatorApp()
    app._speak_english_text = lambda *args, **kwargs: None  # 静音，避免真的朗读

    use_case = TranslateTextUseCase(
        lambda source: _Translator(),
        lambda: "google",
        _Tts(),
        lambda exc: f"格式化:{type(exc).__name__}",
        lambda: 100,
    )

    samples = [
        "hello world",
        "  spaced   text  ",
        "x" * 200,
        "你好世界",
        "line1\nline2",
    ]
    for sample in samples:
        seen: dict[str, str] = {}

        def fake_resilient(text: str, _seen=seen):
            _seen["text"] = text
            return "你好", "（Fake 最快返回）"

        app._translate_resilient = fake_resilient
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            app._translate_text_job(sample, no_text_hint="hint")
        printed = buffer.getvalue().strip()
        # 原版：print(f"[{ts}] {text} => {display}")，其中 display 可能含换行
        match = re.match(r"^\[[^\]]+\] (.*?) => (.*)\Z", printed, re.DOTALL)
        original_text = seen.get("text")
        original_display = match.group(2) if match else None

        progress = ProgressReporter()
        outcome = use_case.execute(sample, progress=progress, no_text_hint="hint")
        compare(
            f"流程：传给翻译器的文本（{sample[:16]!r}…）",
            original_text,
            outcome.source_text if outcome.kind is OutcomeKind.OK else None,
        )
        compare(
            f"流程：展示文本（{sample[:16]!r}…）",
            original_display,
            outcome.result.display_text if outcome.result is not None else None,
        )


def parity_collect_flow(main_mod) -> None:
    """流程级对拍：收录生词本的分支判定 vs 原 ``_do_save_vocab_job``。

    原版会写真实 ``vocab.json``，因此这里把读写替换成记录器——只比对**分支与入参**，
    不产生任何落盘副作用。
    """
    from snaptranslate.application.dto import CollectKind
    from snaptranslate.application.vocabulary_collection import VocabularyCollectionUseCase

    class _Repo:
        def __init__(self, items):
            self._items = list(items)
            self.saved = None

        @property
        def path(self):
            return "vocab.json"

        def exists(self):
            return True

        def load_raw(self):
            return list(self._items)

        def load_tolerant(self):
            return [x for x in self._items if isinstance(x, dict)]

        def load_strict(self):
            return self.load_tolerant()

        def save(self, items):
            self.saved = list(items)
            self._items = list(items)

    scenarios = [
        ("urban", "城市的", [{"word": "urban"}]),
        ("theft", "盗窃", []),
        ("", "x", []),
        ("word", "", []),
    ]
    for word, meaning, existing in scenarios:
        app = main_mod.TranslatorApp()
        app._load_vocab = lambda _existing=existing: [dict(item) for item in _existing]
        recorded: dict[str, object] = {}
        app._save_vocab = lambda items, _recorded=recorded: _recorded.setdefault("items", list(items))
        app._ui_vocab_feedback = lambda title, msg, floating=True: recorded.setdefault("feedback", (title, msg))
        app._refresh_recent_saved_ui = lambda: None
        app._do_save_vocab_job(word, meaning)

        repository = _Repo([dict(item) for item in existing])
        outcome = VocabularyCollectionUseCase(repository).collect(word, meaning)

        original_branch = "added" if recorded.get("items") else (
            "empty" if not word or not meaning else "duplicate"
        )
        ours_branch = {
            CollectKind.ADDED: "added",
            CollectKind.DUPLICATE: "duplicate",
            CollectKind.EMPTY: "empty",
            CollectKind.FAILED: "failed",
        }[outcome.kind]
        compare(f"收录分支 word={word!r} meaning={meaning!r}", original_branch, ours_branch)
        if original_branch == "added":
            compare(
                f"收录内容 word={word!r}",
                recorded.get("items"),
                repository.saved,
            )



def parity_review(review_mod, web_mod, set_mod) -> None:
    from snaptranslate.domain.models.vocab_entry import Vocabulary
    from snaptranslate.domain.services.review_session import ReviewSession
    from snaptranslate.domain.services.scoring import GRADE_DELTA, item_score, normalize_scores
    from snaptranslate.infrastructure.llm.deepseek import (
        is_insufficient_balance_error,
        parse_bilingual_response,
    )

    score_cases = [{"score": 50}, {"score": None}, {"score": "abc"}, {"score": -5}, {"score": 120},
                   {"score": 33.33333}, {}, {"score": 0}, {"score": "42.5"}]
    for case in score_cases:
        compare(f"item_score({case!r})", review_mod.item_score(case), item_score(case))

    items_a = [dict(case) for case in score_cases]
    items_b = [dict(case) for case in score_cases]
    review_mod.normalize_vocab_scores(items_a)
    normalize_scores(items_b)
    compare("normalize_vocab_scores", items_a, items_b)

    compare("GRADE_DELTA", review_mod.GRADE_DELTA, dict(GRADE_DELTA))
    compare("web GRADE_DELTA", web_mod.GRADE_DELTA, dict(GRADE_DELTA))

    example_cases = [
        {"word": "a", "example": "x", "example_zh": "y"},
        {"word": "a", "example": "", "example_zh": "y"},
        {"word": "a", "example": "x", "example_zh": ""},
        {"word": "a"},
        {"word": "a", "example": None, "example_zh": None},
        {"word": "a", "example": "  ", "example_zh": "  "},
    ]
    for case in example_cases:
        compare(
            f"needs_bilingual_example({case!r})",
            review_mod.needs_bilingual_example(case),
            Vocabulary([dict(case)]).entries()[0].needs_bilingual_example,
        )
        compare(
            f"with_example_count({case!r})",
            set_mod.count_with_example([dict(case)]),
            Vocabulary([dict(case)]).with_example_count(),
        )
    compare(
        "count_pending_examples",
        review_mod.count_pending_examples([dict(c) for c in example_cases]),
        Vocabulary([dict(c) for c in example_cases]).pending_example_count(),
    )

    raw_cases = [
        '{"example":"Hi","example_zh":"你好"}',
        '```json\n{"example":"Hi","example_zh":"你好"}\n```',
        '前缀 {"example":"Hi","example_zh":"你好"} 后缀',
        '{"example":"Hi"}',
        '{"example":"","example_zh":""}',
        "not json at all",
    ]
    for raw in raw_cases:
        try:
            original_out = ("ok", review_mod.parse_bilingual_response(raw))
        except Exception as exc:  # noqa: BLE001
            original_out = ("raise", type(exc).__name__)
        try:
            refactored_out = ("ok", parse_bilingual_response(raw))
        except Exception as exc:  # noqa: BLE001
            refactored_out = ("raise", type(exc).__name__)
        compare(f"parse_bilingual_response({raw[:24]!r}…)", original_out, refactored_out)

    class _HttpError(Exception):
        def __init__(self, status_code):
            super().__init__("insufficient balance" if status_code == 402 else "boom")
            self.status_code = status_code

    for exc in [_HttpError(402), _HttpError(500), Exception("Insufficient Balance"), Exception("402 balance"),
                Exception("nothing")]:
        compare(
            f"is_insufficient_balance_error({exc!r})",
            review_mod._is_insufficient_balance_error(exc),
            is_insufficient_balance_error(exc),
        )

    order_items = [{"score": 30}, {"score": 80}, {"score": 30}, {"score": 55}]
    for mode in ["score_asc", "score_desc", "random"]:
        original_order = web_mod.rebuild_order([dict(i) for i in order_items], mode)
        session = ReviewSession(Vocabulary([dict(i) for i in order_items]), mode)
        if mode == "random":
            compare(f"rebuild_order(random) 是排列", sorted(original_order), sorted(session.order))
        else:
            compare(f"rebuild_order({mode})", original_order, session.order)


def parity_vocabulary_io(main_mod, review_mod, web_mod, set_mod) -> None:
    from snaptranslate.domain.errors import VocabularyIoError
    from snaptranslate.infrastructure.persistence.json_vocabulary import JsonVocabularyRepository

    app = main_mod.TranslatorApp()
    payloads = {
        "valid": [{"word": "a"}, {"word": "b"}],
        "mixed": [{"word": "a"}, "字符串", 3, None, {"word": "b"}],
        "top_dict": {"word": "a"},
        "empty": [],
    }
    with tempfile.TemporaryDirectory() as tmp:
        for name, payload in payloads.items():
            path = Path(tmp) / f"{name}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            app.vocab_path = str(path)
            repository = JsonVocabularyRepository(str(path))

            compare(f"load_raw(main) {name}", app._load_vocab(), repository.load_raw())
            compare(f"load_tolerant(review) {name}", review_mod.load_vocab(str(path)), repository.load_tolerant())
            compare(f"load_tolerant(web) {name}", web_mod.load_vocab(str(path)), repository.load_tolerant())
            try:
                original_strict: object = ("ok", set_mod.load_vocab(str(path)))
            except Exception as exc:  # noqa: BLE001
                original_strict = ("raise", type(exc).__name__)
            try:
                refactored_strict: object = ("ok", repository.load_strict())
            except VocabularyIoError as exc:
                refactored_strict = ("raise", type(exc).__name__)
            # 异常类型名不同（原版 OSError/ValueError，新版 VocabularyIoError），只比较"是否抛错"与成功时的内容
            compare(
                f"load_strict(set) {name}",
                original_strict[0] if original_strict[0] != "ok" else original_strict,
                refactored_strict[0] if refactored_strict[0] != "ok" else refactored_strict,
            )

        broken = Path(tmp) / "broken.json"
        broken.write_text("{ not json", encoding="utf-8")
        app.vocab_path = str(broken)
        repository = JsonVocabularyRepository(str(broken))
        compare("load_raw(main) 损坏文件", app._load_vocab(), repository.load_raw())
        compare("load_tolerant(review) 损坏文件", review_mod.load_vocab(str(broken)), repository.load_tolerant())

        missing = Path(tmp) / "nope.json"
        app.vocab_path = str(missing)
        repository = JsonVocabularyRepository(str(missing))
        compare("load_raw(main) 文件缺失", app._load_vocab(), repository.load_raw())
        compare("load_tolerant(review) 文件缺失", review_mod.load_vocab(str(missing)), repository.load_tolerant())

        # 写盘格式对拍（键序 / 缩进 / ensure_ascii）
        original_out = Path(tmp) / "original.json"
        refactored_out = Path(tmp) / "refactored.json"
        sample = [{"word": "urban", "meaning": "城市的", "example": "", "example_zh": "", "score": 50.0,
                   "reviews": 0, "extra": "保留"}]
        review_mod.save_vocab(str(original_out), sample)
        JsonVocabularyRepository(str(refactored_out)).save(sample)
        compare("save_vocab 字节级一致", original_out.read_bytes(), refactored_out.read_bytes())


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    original_dir = Path(argv[0]).resolve() if argv else DEFAULT_ORIGINAL
    if not (original_dir / "main.py").is_file():
        print(f"[SKIP] 未找到原版目录 {original_dir}，跳过对拍")
        return 0

    print(f"等价性对拍：原版 {original_dir}")
    main_mod = load_module("orig_main", original_dir / "main.py")
    review_mod = load_module("orig_vocab_review", original_dir / "vocab_review.py")
    web_mod = load_module("orig_vocab_review_web", original_dir / "vocab_review_web.py")
    set_mod = load_module("orig_set", original_dir / "set.py")

    for title, func in (
        ("clean_text / is_likely_english", lambda: parity_clean_text(main_mod)),
        ("hotkey 解析 / VK 映射 / 标签", lambda: parity_hotkeys(main_mod)),
        ("翻译响应解析 / 失败文案", lambda: parity_translation(main_mod)),
        ("评分 / 顺序 / 例句解析 / 402 判定", lambda: parity_review(review_mod, web_mod, set_mod)),
        ("词表 IO 三种语义 / 写盘格式", lambda: parity_vocabulary_io(main_mod, review_mod, web_mod, set_mod)),
        ("流程：文本翻译主链路", lambda: parity_translate_flow(main_mod)),
        ("流程：生词收录分支", lambda: parity_collect_flow(main_mod)),
    ):
        print(f"\n=== {title} ===")
        try:
            func()
        except Exception as exc:  # noqa: BLE001
            RESULTS.append((False, f"{title} 执行异常"))
            print(f"  [FAIL] {title} 执行异常：{type(exc).__name__}: {exc}")
            import traceback

            traceback.print_exc()

    failed = [label for ok, label in RESULTS if not ok]
    print()
    print(f"对拍用例 {len(RESULTS)} 项，差异 {len(failed)} 项")
    if failed:
        for label in failed[:40]:
            print(f"  - {label}")
        return 1
    print("[OK] 与原版逐项一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
