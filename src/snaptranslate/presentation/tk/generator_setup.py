"""批量生成例句的「客户端准备 + 后台任务」两段胶水（原 ``vocab_review.py:895-984``）。

从复习窗口里拆出来，是因为这两段既不是布局也不是卡片状态：

- :func:`prepare_generator` —— 原 ``_get_client`` / ``_prompt_and_save_api_key``：
  构造生成器，缺 Key 时弹窗并保存重试，缺 ``openai`` 依赖时报错；两种失败都返回 ``None``。
- :func:`start_generate_task` —— 原 ``worker`` 线程：调用例执行、把结果丢回主线程。

用例本身（``deps.examples.execute``）不做任何改动，这里沿用它规定的
``should_stop`` / ``save_each`` / ``delay`` 参数，保持桌面端语义（逐条落盘 + 0.35s）。
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import Callable

from snaptranslate.application.deps import ReviewAppDeps
from snaptranslate.application.dto import ExampleItemResult, GenerateOutcome
from snaptranslate.domain.errors import MissingApiKeyError, MissingDependencyError
from snaptranslate.domain.models.vocab_entry import Vocabulary
from snaptranslate.presentation.texts import ReviewText

#: 用例执行完的回报（成功数 / 计划数 / 终止原因都在 :class:`GenerateOutcome` 里）
OnFinished = Callable[[GenerateOutcome], None]


def prepare_generator(deps: ReviewAppDeps, parent: tk.Misc):
    """按原版顺序准备生成器；任何一步失败都返回 ``None``（调用方据此静默返回）。

    两个容易漏掉的等价点：
    ① 原 ``_get_client`` 在**批量开始前**就校验凭据，所以这里必须调用 ``ensure_ready()``
       （只构造对象不会读 Key，缺 Key 会变成"每条都失败"而不是弹窗索取）；
    ② 弹窗写入的是 ``deps.api_key_store``（对应用户固定的 ``api_key.txt``）。
    """

    def _build():
        generator = deps.generator_factory(None)
        generator.ensure_ready()
        return generator

    try:
        return _build()
    except MissingApiKeyError:
        key = simpledialog.askstring(
            ReviewText.API_KEY_PROMPT_TITLE,
            ReviewText.API_KEY_PROMPT_BODY,
            parent=parent,
            show="*",
        )
        if key is None:  # 取消 → 原版直接返回，不弹警告
            return None
        key = key.strip()
        if not key:  # 空串 → 原版警告后返回
            messagebox.showwarning(ReviewText.NOTHING_TO_GENERATE_TITLE, ReviewText.API_KEY_EMPTY)
            return None
        try:
            deps.api_key_store.write(key)
        except Exception as exc:  # noqa: BLE001 - 原版 write_api_key_file 的 except Exception
            messagebox.showerror(ReviewText.API_KEY_SAVE_FAILED, str(exc))
            return None
        try:
            return _build()
        except MissingApiKeyError:
            return None
    except MissingDependencyError:
        messagebox.showerror(ReviewText.MISSING_DEPENDENCY_TITLE, ReviewText.MISSING_DEPENDENCY_BODY)
        return None


def start_generate_task(
    parent: tk.Misc,
    deps: ReviewAppDeps,
    generator,
    vocabulary: Vocabulary,
    pending: list[VocabEntry],
    *,
    on_item_done: Callable[[ExampleItemResult], None],
    on_finished: OnFinished,
    delay: float,
) -> None:
    """原 ``worker``：后台逐条执行，窗口关闭即停；结束后把结果 ``after`` 回主线程。"""

    def worker() -> None:
        outcome = deps.examples.execute(
            generator,
            vocabulary,
            pending,
            on_item_done=on_item_done,
            should_stop=lambda: not parent.winfo_exists(),
            save_each=True,
            delay=delay,
        )
        parent.after(0, lambda: on_finished(outcome))

    threading.Thread(target=worker, daemon=True).start()


__all__ = ["OnFinished", "prepare_generator", "start_generate_task"]
