"""生词复习窗口（对应原版 ``vocab_review.py`` 全文，1026 行）。

职责：把 ``VocabReviewApp`` 的装配、事件绑定、日志与后台线程调度原样搬过来；
顺序 / 评分 / 推进 / 朗读一律走 ``deps.review``，批量生成走 ``deps.examples``，
本文件不重写任何用例逻辑。卡片渲染与揭示在 :mod:`.card_controller`，
控件树在 :mod:`.settings_form` / :mod:`.card_form` / :mod:`.log_panel`，
例句面板在 :mod:`.example_panel`，生成器准备与 worker 在 :mod:`.generator_setup`。

原版行号对照：
- 常量与配色 ``1-56``（配色已收敛到 :mod:`snaptranslate.config.theme`）
- ``__init__`` ``160-196`` ｜ ``_build_ui`` ``198-548`` ｜ ``_log`` ``550-554``
- 选文件 ``556-574`` ｜ 音量 ``576-605`` ｜ 顺序切换 ``606-612``
- 朗读 ``661-692`` ｜ 评分 ``694-716`` ｜ 卡片与揭示 ``734-855``
- 生成按钮标签 ``857-859`` ｜ API Key ``861-879`` ｜ 批量生成 ``937-1004``
- ``run`` ``1006-1017``

行为等价说明：原版用 ``self.order`` / ``self.pos`` / ``self.show_*`` 三个并行状态，
重构后由 ``ReviewSession``（``domain/services/review_session.py``）统一持有。"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox

from snaptranslate.application.deps import ReviewAppDeps
from snaptranslate.application.dto import ExampleItemResult, GenerateOutcome, StopKind
from snaptranslate.application.review import ReviewUseCase
from snaptranslate.config import theme
from snaptranslate.domain.errors import VocabularyIoError
from snaptranslate.domain.models.review import Grade, GradeResult, SortMode
from snaptranslate.presentation.texts import ReviewText
from snaptranslate.presentation.tk import generator_setup, log_panel
from snaptranslate.presentation.tk.card_controller import CardController
from snaptranslate.presentation.tk.card_form import CardForm
from snaptranslate.presentation.tk.log_panel import LogPanel, build_header
from snaptranslate.presentation.tk.settings_form import SettingsForm
from snaptranslate.presentation.tk.speech import SpeakScheduler

#: 原 ``vocab_review.py:978`` 的每条间隔（用例默认值同为 0.35s，这里显式传入）
GEN_DELAY_SEC = 0.35


class ReviewApp:
    """生词复习界面（原 ``vocab_review.py:VocabReviewApp``）。"""

    def __init__(self, deps: ReviewAppDeps) -> None:
        self._deps = deps
        self._gen_running = False

        # 原 ``load_vocab`` + ``normalize_vocab_scores``（用例内做容错加载与评分归一化）
        vocabulary = deps.review.load()

        self.root = tk.Tk()
        self.root.title(ReviewText.TITLE)
        self.root.geometry("680x700")
        self.root.minsize(560, 520)
        self.root.configure(bg=theme.UI_BG)

        # Tk 变量必须在 root 创建之后绑定，否则会 RuntimeError: Too early to create variable
        # 顺序：random | score_asc | score_desc
        self._sort_mode_var = tk.StringVar(master=self.root, value=SortMode.RANDOM.value)
        self._status_var = tk.StringVar(master=self.root, value=ReviewText.READY)
        self._word_var = tk.StringVar(master=self.root, value="")
        self._meaning_var = tk.StringVar(master=self.root, value=ReviewText.MEANING_PLACEHOLDER)
        self._progress_var = tk.StringVar(master=self.root, value="0 / 0")
        self._score_var = tk.StringVar(master=self.root, value=ReviewText.SCORE_PLACEHOLDER)
        # 朗读：none | word | word_example
        self._read_mode_var = tk.StringVar(master=self.root, value="none")
        self._tts_volume_var = tk.IntVar(master=self.root, value=self._deps.settings.load_tts_volume())
        self._tts_volume_var.trace_add("write", self._on_tts_volume_change)

        self._build_ui()

        self.session = deps.review.create_session(vocabulary, self._sort_mode_var.get())
        self.vocabulary = vocabulary
        self._speak = SpeakScheduler(deps.review.speak_for_card, deps.review.speak_example)
        self._card = CardController(
            self,
            self._card_form,
            self._speak,
            progress_var=self._progress_var,
            score_var=self._score_var,
            word_var=self._word_var,
            meaning_var=self._meaning_var,
            grade_use_case=deps.review,
            on_grade_logged=self._log_grade,
            on_save_failed=lambda exc: messagebox.showerror(ReviewText.SAVE_FAILED_TITLE, str(exc)),
            score_max=ReviewUseCase.score_max(),
        )
        self._show_card()

    # —————————————————————————— 界面 ——————————————————————————

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=theme.UI_BG, padx=18, pady=14)
        outer.pack(fill="both", expand=True)

        build_header(outer)

        self._settings_form = SettingsForm(
            outer,
            vocab_path=self._deps.review.vocab_path,
            sort_mode_var=self._sort_mode_var,
            read_mode_var=self._read_mode_var,
            volume_var=self._tts_volume_var,
            on_sort_change=self._on_sort_mode_change,
            on_browse=self._pick_vocab_file,
            on_repeat=self._manual_speak_current,
        )

        self._card_form = CardForm(
            outer,
            progress_var=self._progress_var,
            score_var=self._score_var,
            word_var=self._word_var,
            meaning_var=self._meaning_var,
            on_toggle_meaning=self._toggle_meaning,
            on_toggle_example=self._toggle_example,
            on_toggle_example_zh=self._toggle_example_zh,
            on_grade=self._apply_grade,
        )

        self._log_panel = LogPanel(
            outer,
            status_var=self._status_var,
            gen_label=ReviewText.GEN_BUTTON.format(pending=0),
            on_generate=self._start_generate_examples,
        )

    # —————————————————————————— 日志 / 设置 ——————————————————————————

    def _log(self, line: str) -> None:
        self._log_panel.write(line)

    def _log_grade(self, result: GradeResult, grade: Grade, word: str, revealed: bool) -> None:
        """原 ``715`` 的评分日志。

        行为等价：保留原版缺陷（见 KNOWN_ISSUES.md #12 —— ``reviews`` 非数字时
        ``apply_grade`` 会抛 ``ValueError``，这里**不**额外兜底）。
        """
        self._log(ReviewText.grade_log(word, grade, revealed, result.old_score, result.new_score, result.delta))

    def _pick_vocab_file(self) -> None:
        """原 ``556-574``：换词表 → 重载 → 重建会话 → 重置揭示 → 刷新按钮标签 → 重绘卡片。"""
        path = filedialog.askopenfilename(
            title=ReviewText.PICK_TITLE,
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
            initialdir=os.path.dirname(self._deps.review.vocab_path),
        )
        if not path:
            return
        self._deps.review.use_path(path)
        self._settings_form.path_label.configure(text=path)
        vocabulary = self._deps.review.load()
        self.vocabulary = vocabulary
        self.session = self._deps.review.create_session(vocabulary, self._sort_mode_var.get())
        self.session.position = 0
        self.session.reset_reveal()
        self._refresh_gen_button_label()
        self._show_card()

    def _on_tts_volume_change(self, *_: object) -> None:
        """原 ``600-604``：滑块拖动即落盘；取值失败（TclError/类型）静默返回。"""
        try:
            volume = int(self._tts_volume_var.get())
        except (tk.TclError, TypeError, ValueError):
            return
        # replace() 写失败在适配器内部已静默（等价于原 _save_tts_volume 的 try/except）
        self._deps.settings.save_tts_volume(volume)

    def _on_sort_mode_change(self) -> None:
        self.session.set_mode(self._sort_mode_var.get())
        self._show_card()

    # —————————————————————————— 朗读 / 卡片事件 ——————————————————————————

    def _manual_speak_current(self) -> None:
        """原 ``688-692``：等价于按当前模式朗读当前卡。"""
        entry = self._card.current_entry()
        if entry is None:
            return
        self._speak.speak_for_card(entry, self._read_mode_var.get(), self._volume())

    def _show_card(self) -> None:
        self._card.show(self._read_mode_var.get(), self._volume())

    def _toggle_meaning(self) -> None:
        self._card.toggle_meaning()

    def _toggle_example(self) -> None:
        self._card.toggle_example(self._read_mode_var.get(), self._volume())

    def _toggle_example_zh(self) -> None:
        self._card.toggle_example_zh()

    def _apply_grade(self, grade: Grade) -> None:
        """原 ``_apply_grade``：评分成功后由控制器重绘到下一张卡（见 ``CardController.apply_grade``）。"""
        self._card.apply_grade(grade, self._read_mode_var.get(), self._volume())

    def _volume(self) -> int:
        """原版到处写 ``int(self.tts_volume_var.get()) if hasattr(...) else 100``。"""
        try:
            return int(self._tts_volume_var.get())
        except (tk.TclError, TypeError, ValueError):
            return 100

    # —————————————————————————— 批量生成 ——————————————————————————

    def _refresh_gen_button_label(self) -> None:
        """生成按钮标签；待补全口径与原 ``count_pending_examples`` 一致。

        行为等价：保留原版缺陷（见 KNOWN_ISSUES.md #11 —— 复习端"英或中译任一为空"，
        后台管理端"两者都齐全"，同一份词表两处数字可能不同，不做合并）。
        """
        pending = self._deps.examples.pending_count(self.vocabulary)
        self._log_panel.set_gen_label(ReviewText.GEN_BUTTON.format(pending=pending))

    def _start_generate_examples(self) -> None:
        """原 ``937-984``：工厂 → 待补全清单 → 置忙 → 后台执行（顺序不可调换）。"""
        if self._gen_running:
            return
        generator = generator_setup.prepare_generator(self._deps, self.root)
        if generator is None:
            return
        pending = self._deps.examples.pending_items(self.vocabulary)
        if not pending:
            messagebox.showinfo(ReviewText.NOTHING_TO_GENERATE_TITLE, ReviewText.NOTHING_TO_GENERATE_BODY)
            return
        self._gen_running = True
        self._log_panel.gen_button.configure(state="disabled")
        self._status_var.set(ReviewText.GENERATING)
        generator_setup.start_generate_task(
            self.root,
            self._deps,
            generator,
            self.vocabulary,
            pending,
            on_item_done=self._on_item_done,
            on_finished=self._on_generate_finished,
            delay=GEN_DELAY_SEC,
        )

    def _on_item_done(self, item: ExampleItemResult) -> None:
        """逐条日志（在后台线程被调用，按原版做法丢回主线程）。

        成功行等价原 ``966``；失败行等价原 ``986-987`` 的 ``_log_fail``。
        """
        if item.ok:
            line = ReviewText.item_log(item.order, item.total, item.word)
        else:
            line = ReviewText.item_fail_log(item.order, item.total, item.word, item.error)
        self._log_panel.post_from_worker(self.root, line)

    def _on_generate_finished(self, outcome: GenerateOutcome) -> None:
        """原 ``979-982`` 的 ``after(0, ...)`` 落点。"""
        self._gen_finished(outcome.ok, outcome.total, outcome.stop_kind)

    def _gen_finished(self, ok: int, total: int, stop_kind: StopKind) -> None:
        """原 ``989-1004``。"""
        if stop_kind is StopKind.INSUFFICIENT_BALANCE:
            # 原版在 worker 命中 402 时就写了这一行；这里提前到状态栏之前，顺序保持不变
            self._log(ReviewText.GENERATE_ABORTED_HINT)
        self._gen_running = False
        self._log_panel.gen_button.configure(state="normal")
        self._refresh_gen_button_label()
        self._status_var.set(ReviewText.GENERATE_FINISHED_STATUS.format(ok=ok, total=total))
        self._show_card()
        if stop_kind is StopKind.INSUFFICIENT_BALANCE:
            messagebox.showwarning(
                ReviewText.GENERATE_ABORTED_TITLE,
                ReviewText.GENERATE_ABORTED_BODY.format(
                    reason=ReviewText.GENERATE_INSUFFICIENT_BALANCE, ok=ok, total=total
                ),
            )
        else:
            messagebox.showinfo(
                ReviewText.GENERATE_DONE_TITLE,
                ReviewText.GENERATE_DONE_BODY.format(ok=ok, total=total),
            )

    # —————————————————————————— 启动 ——————————————————————————

    def run(self) -> None:
        """原 ``1006-1017``：启动备份 → 刷新按钮标签 → 写两行日志 → mainloop。

        日志行逐字等价原版（``n / count_pending_examples`` 都是整数）。
        """
        backup = self._deps.review.backup_on_startup(self.vocabulary)
        self._refresh_gen_button_label()
        self._log(ReviewText.backup_log(backup.ok, backup.message))
        self._log(
            ReviewText.loaded_log(
                self._deps.review.vocab_path,
                len(self.vocabulary),
                self._deps.examples.pending_count(self.vocabulary),
            )
        )
        self.root.mainloop()


__all__ = ["GEN_DELAY_SEC", "ReviewApp"]
