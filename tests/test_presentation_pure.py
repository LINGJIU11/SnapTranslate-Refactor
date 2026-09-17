"""表示层纯逻辑测试（不创建任何 Tk 控件）。

覆盖：文案映射表、最近 3 条列表、热键管理器——这三块是"界面行为"里最容易悄悄写错的部分。
"""

from __future__ import annotations

import unittest

from snaptranslate.application.dto import CollectKind, DeleteKind, ErrorKind
from snaptranslate.application.progress import Stage
from snaptranslate.domain.models.hotkey import DEFAULT_HOTKEYS
from snaptranslate.presentation.texts import (
    AdminText,
    CollectText,
    ErrorTitle,
    ReviewText,
    StatusText,
    WindowText,
)
from snaptranslate.presentation.tk.hotkey_controls import HotkeyManager
from snaptranslate.presentation.tk.translate_transcript import RecentList

from snaptranslate.domain.models.review import Grade


class StatusTextTests(unittest.TestCase):
    def test_stage_texts_match_original(self) -> None:
        self.assertEqual(StatusText.texts(Stage.READING_SELECTION), (None, "读取划词内容…", None))
        self.assertEqual(StatusText.texts(Stage.TRANSLATING), (None, "并发翻译中…", None))
        self.assertEqual(StatusText.texts(Stage.DONE), (None, "翻译完成", 1000))
        self.assertEqual(StatusText.texts(Stage.FAILED), (None, "翻译失败", 1500))
        self.assertEqual(StatusText.texts(Stage.NO_TEXT), (None, "未检测到可翻译文本", 1300))
        self.assertEqual(StatusText.texts(Stage.OCR_PREPARING), (None, "OCR 准备中…", None))
        self.assertEqual(StatusText.texts(Stage.OCR_CAPTURING), ("OCR：正在截取屏幕…", "OCR 截图中…", None))
        self.assertEqual(
            StatusText.texts(Stage.OCR_RECOGNIZING),
            ("OCR：正在识别文字（区域越大可能越慢，请稍候）…", "OCR 识别中…", None),
        )
        self.assertEqual(StatusText.texts(Stage.OCR_TRANSLATING), ("OCR：正在翻译…", "并发翻译中…", None))
        self.assertEqual(StatusText.texts(Stage.OCR_UNAVAILABLE), (None, "OCR 不可用", 1500))
        self.assertEqual(
            StatusText.texts(Stage.OCR_BUSY),
            ("OCR 正在进行中，请稍候…", "OCR 正在进行中，请稍候…", 1300),
        )
        self.assertEqual(StatusText.texts(Stage.OCR_FAILED), (None, "OCR 失败", 1500))


class ErrorTitleTests(unittest.TestCase):
    def test_title_by_error_kind(self) -> None:
        self.assertEqual(ErrorTitle.for_kind(ErrorKind.TRANSLATE, "原文"), "原文")
        self.assertEqual(ErrorTitle.for_kind(ErrorKind.OCR_FAILED), "OCR 失败")
        self.assertEqual(ErrorTitle.for_kind(ErrorKind.OCR_UNAVAILABLE), "OCR 不可用")
        self.assertEqual(ErrorTitle.HINT, "提示")


class CollectTextTests(unittest.TestCase):
    def test_collect_messages(self) -> None:
        self.assertEqual(
            CollectText.for_outcome(CollectKind.ADDED, "urban"), ("生词本", "已记录到生词本：urban")
        )
        self.assertEqual(
            CollectText.for_outcome(CollectKind.DUPLICATE, "urban"), ("生词本", "已存在于生词本：urban")
        )
        self.assertEqual(
            CollectText.for_outcome(CollectKind.EMPTY, ""), ("生词本", "暂无可记录内容：请先翻译一次")
        )
        self.assertEqual(
            CollectText.for_outcome(CollectKind.FAILED, "urban"), ("生词本", "记录失败：写入生词本出错")
        )
        self.assertEqual(
            CollectText.for_outcome(CollectKind.NO_LAST, "", "CTRL+L"),
            ("生词本", "暂无可收录内容：请先按 CTRL+L 翻译一次"),
        )

    def test_delete_never_floats(self) -> None:
        """原 ``_delete_saved_word`` 四个分支都不弹悬浮提示。"""
        self.assertEqual(CollectText.for_delete(DeleteKind.DELETED, "a"), ("已删除：a", False))
        self.assertEqual(CollectText.for_delete(DeleteKind.NOT_FOUND, "a"), ("未找到词条：a", False))
        self.assertEqual(CollectText.for_delete(DeleteKind.FAILED, "a"), ("删除失败：a", False))
        self.assertEqual(CollectText.for_delete(DeleteKind.EMPTY, ""), ("该条记录为空", False))


class WindowTextTests(unittest.TestCase):
    def test_status_and_hint_texts(self) -> None:
        hotkeys = dict(DEFAULT_HOTKEYS)
        self.assertEqual(
            WindowText.status_enabled(hotkeys),
            "已开启 — CTRL+L 划词翻译，TAB+Q 截图 OCR，TAB+E 收录最近一条",
        )
        self.assertEqual(
            WindowText.status_disabled(hotkeys),
            "已关闭 — 不会响应 CTRL+L / TAB+Q / TAB+E",
        )
        self.assertEqual(
            WindowText.hotkey_hint(hotkeys),
            "划词翻译：CTRL+L  |  截图 OCR：TAB+Q  |  收录：TAB+E",
        )

    def test_no_selection_hint(self) -> None:
        self.assertEqual(WindowText.no_selection_hint("CTRL+L"), "未检测到选中文本，请先划词再按 CTRL+L")

    def test_hotkey_error_templates(self) -> None:
        self.assertEqual(
            WindowText.HOTKEY_ERROR_FORMAT.format(name="snip", value="bad"),
            "快捷键格式错误：snip=bad（示例：ctrl+l / tab+q）",
        )
        self.assertEqual(WindowText.HOTKEY_DUPLICATE, "快捷键不能重复，请设置 3 组不同组合")
        self.assertEqual(WindowText.FLOATING_COLLECT_BUTTON, "收录生词本")


class ReviewTextTests(unittest.TestCase):
    def test_grade_log_format(self) -> None:
        self.assertEqual(
            ReviewText.grade_log("urban", Grade.KNOW, False, 50.0, 60.0, 10.0),
            "评分「urban」认识（未看释义/例句）50.0 → 60.0（Δ+10.0）",
        )
        self.assertEqual(
            ReviewText.grade_log("urban", Grade.UNKNOWN, True, 50.0, 38.0, -12.0),
            "评分「urban」不认识（已看释义/例句）50.0 → 38.0（Δ-12.0）",
        )

    def test_progress_score_and_item_logs(self) -> None:
        self.assertEqual(ReviewText.progress(0, 5), "1 / 5")
        self.assertEqual(ReviewText.score(50.0, 3, 100.0), "熟练度 50.0 / 100（已评 3 次）")
        self.assertEqual(ReviewText.item_log(2, 10, "urban"), "[2/10] OK：urban")
        self.assertEqual(ReviewText.item_fail_log(2, 10, "urban", "boom"), "[2/10] 失败：urban — boom")

    def test_generation_button_and_logs(self) -> None:
        self.assertEqual(
            ReviewText.GEN_BUTTON.format(pending=4), "用 DeepSeek 生成英例句 + 中译（约 4 条待补全）"
        )
        self.assertEqual(ReviewText.backup_log(True, "backups/x.json"), "启动备份已创建：backups/x.json")
        self.assertEqual(ReviewText.backup_log(False, "未找到 vocab.json，跳过备份"), "未找到 vocab.json，跳过备份")
        self.assertEqual(
            ReviewText.loaded_log("vocab.json", 4, 2),
            "已加载 vocab.json，共 4 条；待生成/待补全（英或中译）约 2 条。",
        )

    def test_read_and_sort_modes_match_original(self) -> None:
        self.assertEqual(ReviewText.SORT_MODES, (("随机", "random"), ("得分低→高", "score_asc"), ("得分高→低", "score_desc")))
        self.assertEqual(
            ReviewText.READ_MODES,
            (("不朗读", "none"), ("单词", "word"), ("单词+例句", "word_example")),
        )

    def test_generate_aborted_body_template(self) -> None:
        """402 中止弹窗正文与原版 f-string 一致。"""
        self.assertEqual(
            ReviewText.GENERATE_ABORTED_BODY.format(reason="原因", ok=1, total=3),
            "原因\n\n已成功写入：1 / 本次计划：3",
        )

    def test_collect_title_is_centralised(self) -> None:
        self.assertEqual(CollectText.TITLE, "生词本")
        self.assertEqual(CollectText.for_outcome(CollectKind.ADDED, "x")[0], CollectText.TITLE)


class AdminTextTests(unittest.TestCase):
    def test_status_lines(self) -> None:
        self.assertEqual(AdminText.TOTAL.format(value=117), "词表总数：117")
        self.assertEqual(AdminText.WITH_EXAMPLE.format(value=20), "有例句+翻译：20")
        self.assertEqual(AdminText.PENDING.format(value=97), "待补全例句：97")
        self.assertEqual(AdminText.BACKUP_COUNT.format(value=2), "备份文件数：2")
        self.assertEqual(AdminText.LATEST_BACKUP.format(value="x.json"), "最新备份：x.json")
        self.assertEqual(AdminText.READ_FAILED, "读取失败")
        self.assertEqual(AdminText.RESET_DONE.format(count=117), "已重置 117 条：score=50，reviews=0")
        self.assertEqual(AdminText.VOCAB_MISSING.format(path="a.json"), "找不到词表文件：a.json")


class RecentListTests(unittest.TestCase):
    def test_push_keeps_latest_three(self) -> None:
        recent = RecentList()
        for index in range(4):
            recent.push(f"w{index}", f"m{index}")
        self.assertEqual(len(recent), 3)
        self.assertEqual(recent.items[0], ("w3", "m3"))
        self.assertEqual(recent.items[-1], ("w1", "m1"))

    def test_push_rejects_empty_sides(self) -> None:
        recent = RecentList()
        self.assertFalse(recent.push("", "m"))
        self.assertFalse(recent.push("w", "   "))
        self.assertEqual(len(recent), 0)

    def test_labels_pad_with_placeholder(self) -> None:
        recent = RecentList()
        recent.push("urban", "城市的")
        self.assertEqual(recent.labels(), ["urban => 城市的", "（暂无）", "（暂无）"])

    def test_get_bounds(self) -> None:
        recent = RecentList()
        recent.push("a", "甲")
        self.assertIsNone(recent.get(-1))
        self.assertIsNone(recent.get(1))
        self.assertEqual(recent.get(0), ("a", "甲"))


class HotkeyManagerTests(unittest.TestCase):
    def test_label_and_texts(self) -> None:
        manager = HotkeyManager()
        self.assertEqual(manager.label("translate"), "CTRL+L")
        self.assertEqual(manager.hint(), WindowText.hotkey_hint(DEFAULT_HOTKEYS))
        self.assertEqual(manager.status_enabled(), WindowText.status_enabled(DEFAULT_HOTKEYS))
        self.assertEqual(manager.status_disabled(), WindowText.status_disabled(DEFAULT_HOTKEYS))

    def test_label_placeholder_for_unknown_action(self) -> None:
        self.assertEqual(HotkeyManager().label("nope"), "（未设置）")

    def test_normalize(self) -> None:
        self.assertEqual(HotkeyManager.normalize("  CTRL + L "), "ctrl+l")

    def test_validate_reports_format_error_first(self) -> None:
        message = HotkeyManager().validate({"translate": "ctrl+l", "snip": "bad", "save_last": "tab+e"})
        self.assertEqual(message, "快捷键格式错误：snip=bad（示例：ctrl+l / tab+q）")

    def test_validate_reports_duplicate(self) -> None:
        message = HotkeyManager().validate({"translate": "ctrl+l", "snip": "ctrl+l", "save_last": "tab+e"})
        self.assertEqual(message, WindowText.HOTKEY_DUPLICATE)

    def test_validate_passes(self) -> None:
        self.assertIsNone(HotkeyManager().validate(dict(DEFAULT_HOTKEYS)))

    def test_bindings_parse(self) -> None:
        bindings = HotkeyManager(dict(DEFAULT_HOTKEYS)).bindings()
        self.assertEqual(bindings["translate"].label, "CTRL+L")
        self.assertEqual(bindings["snip"].modifier, "tab")
        self.assertEqual(bindings["save_last"].key, "e")


if __name__ == "__main__":
    unittest.main()
