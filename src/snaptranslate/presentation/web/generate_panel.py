"""底部批量生成面板（DeepSeek 补英例句 + 中译）。

职责：取生成器（等价原 ``get_client``）与批量循环的界面部分——对应原
``vocab_review_web.py:267-319``。循环本身交给用例：
``deps.examples.pending_items(vocab)`` + ``execute(..., save_each=False, delay=0.2)``
（Web 端"结束才落盘一次、每条间隔 0.2s"的语义由参数表达）。

依赖方向：只允许标准库 / streamlit / ``domain.*`` / ``application.*`` /
``presentation.*``（见 ARCHITECTURE.md §1）。
"""

from __future__ import annotations

import streamlit as st

from snaptranslate.application.deps import WebReviewDeps
from snaptranslate.application.dto import ExampleItemResult, StopKind
from snaptranslate.domain.errors import MissingApiKeyError, MissingDependencyError
from snaptranslate.presentation.texts import WebText
from snaptranslate.presentation.web.session_state import K_KEY_PATH, K_LAST_MSG, K_MANUAL_API_KEY, session

#: 批量生成时每条之间的延时（原版 ``time.sleep(0.2)``）
WEB_GENERATE_DELAY_SEC = 0.2


def create_generator(deps: WebReviewDeps):
    """取例句生成器（原 ``get_client``，``vocab_review_web.py:267-285``）。

    返回 ``(generator, missing_dependency)``：``None, None`` 表示已提示用户后放弃。
    ``ensure_ready()`` 对应原版"批量开始前先建 client 并读 Key"，缺 Key / 缺依赖在
    这里立即暴露，而不是等到逐条生成时才失败。
    """
    key_path = st.session_state[K_KEY_PATH]

    def _build():
        generator = deps.generator_factory(key_path)
        generator.ensure_ready()
        return generator

    try:
        return _build(), False
    except MissingApiKeyError:
        manual_key = str(st.session_state.get(K_MANUAL_API_KEY, "")).strip()
        if not manual_key:
            st.warning(WebText.NO_KEY_WARNING)
            return None, False
        try:
            # 原版写的是"侧边栏填的那个 key 文件路径"（``vocab_review_web.py:278``）
            deps.api_key_store_factory(key_path).write(manual_key)
        except Exception as exc:  # noqa: BLE001 - 与原版一致：写 Key 失败只提示
            st.error(WebText.KEY_SAVE_FAILED.format(error=exc))
            return None, False
        try:
            return _build(), False
        except MissingApiKeyError:
            st.warning(WebText.NO_KEY_WARNING)
            return None, False
        except MissingDependencyError:
            return None, True
    except MissingDependencyError:
        return None, True


def generate_examples(deps: WebReviewDeps) -> None:
    """批量补例句（原 ``generate_examples``，``vocab_review_web.py:288-319``）。

    行为等价：保留原版缺陷（见 KNOWN_ISSUES.md #19）——本函数里的 warning/info
    之后调用方紧接着 ``st.rerun()``，用户几乎看不到这些提示（原版 ``311-312`` 同样如此）。
    """
    vocabulary = session().vocabulary
    pending = deps.examples.pending_items(vocabulary)
    if not pending:
        st.info(WebText.NOTHING_TO_GENERATE)
        return
    generator, missing_dependency = create_generator(deps)
    if missing_dependency:
        st.error(WebText.MISSING_DEPENDENCY)
        return
    if generator is None:
        return

    total = len(pending)
    bar = st.progress(0)
    status = st.empty()

    def on_item_start(order: int, count: int, word: str) -> None:
        status.write(WebText.GENERATING.format(order=order, total=count, word=word))

    def on_item_done(item: ExampleItemResult) -> None:
        if not item.ok:
            status.write(
                WebText.GENERATE_FAILED.format(order=item.order, total=item.total, word=item.word, error=item.error)
            )

    outcome = deps.examples.execute(
        generator,
        vocabulary,
        pending,
        on_item_start=on_item_start,
        on_item_done=on_item_done,
        save_each=False,  # 原版 Web 端结束才落盘一次
        delay=WEB_GENERATE_DELAY_SEC,
    )
    bar.progress(1.0)
    if outcome.stop_kind is StopKind.INSUFFICIENT_BALANCE:
        st.warning(WebText.GENERATE_INSUFFICIENT_BALANCE)
    status.write(WebText.GENERATE_DONE.format(ok=outcome.ok, total=total))
    st.session_state[K_LAST_MSG] = WebText.GENERATE_DONE_MSG.format(ok=outcome.ok, total=total)
