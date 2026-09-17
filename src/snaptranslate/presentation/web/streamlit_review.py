"""Streamlit 生词复习页（原 ``vocab_review_web.py`` 的表示层等价物）。

职责
----
本模块只保留**页面骨架**：页面配置、标题、初始化、启动备份、底部统计与两个底部按钮。
其余渲染拆到同级模块：

* :mod:`~snaptranslate.presentation.web.session_state` —— ``st.session_state`` 键名、
  初始化与三个状态迁移入口（换词表 / 切排序 / 切朗读模式）；
* :mod:`~snaptranslate.presentation.web.card_view` —— 侧边栏设置区、卡片与三档自评；
* :mod:`~snaptranslate.presentation.web.speech_inject` —— ``speechSynthesis`` 注入与自动朗读 token；
* :mod:`~snaptranslate.presentation.web.generate_panel` —— DeepSeek 批量补例句面板。

逻辑一律走用例：排序 / 评分 / 推进用 ``deps.review.create_session`` +
``session.set_mode`` + ``deps.review.grade``（领域服务 ``ReviewSession`` 持有词表与顺序），
批量生成用 ``deps.examples.pending_items`` + ``execute(..., save_each=False, delay=0.2)``，
启动备份用 ``deps.review.backup_on_startup``（每个会话一次，原 ``boot_backup_done``）。

对外只暴露 :func:`render_page`；本模块**不在 import 时执行任何 Streamlit 调用**，
调用方是 ``bootstrap/streamlit_entry.py``。

对应原版：``vocab_review_web.py`` 全文（510 行）。
"""

from __future__ import annotations

import streamlit as st

from snaptranslate.application.deps import WebReviewDeps
from snaptranslate.presentation.texts import WebText
from snaptranslate.presentation.web.card_view import render_card, render_sidebar
from snaptranslate.presentation.web.generate_panel import generate_examples
from snaptranslate.presentation.web.session_state import (
    K_BOOT_BACKUP_DONE,
    K_LAST_MSG,
    K_VOCAB_PATH,
    init_state,
    reset_for_new_vocab,
    session,
)


def render_page(deps: WebReviewDeps) -> None:
    """渲染整页（原 ``main()``，``vocab_review_web.py:361-506``）。"""
    st.set_page_config(page_title=WebText.PAGE_TITLE, page_icon="📘", layout="centered")
    st.title(WebText.TITLE)

    init_state(deps)
    render_sidebar(deps)

    current = session()
    if not st.session_state[K_BOOT_BACKUP_DONE]:
        result = deps.review.backup_on_startup(current.vocabulary)
        st.session_state[K_BOOT_BACKUP_DONE] = True
        # 原版：成功时前缀"启动备份："+ 备份文件路径，失败/跳过时直接显示原因
        st.session_state[K_LAST_MSG] = (
            WebText.BACKUP_PREFIX.format(detail=result.message) if result.ok else result.message
        )

    total_n = len(current.vocabulary)
    pending_n = deps.examples.pending_count(current.vocabulary)

    if not render_card(deps, current):
        return
    st.divider()
    st.write(WebText.VOCAB_LINE.format(path=st.session_state[K_VOCAB_PATH]))
    st.write(WebText.COUNT_LINE.format(total=total_n, pending=pending_n))
    if st.session_state[K_LAST_MSG]:
        st.info(st.session_state[K_LAST_MSG])

    col_generate, col_refresh = st.columns(2)
    with col_generate:
        if st.button(WebText.GENERATE_BUTTON.format(pending=pending_n), use_container_width=True):
            generate_examples(deps)
            st.rerun()
    with col_refresh:
        if st.button(WebText.REFRESH, use_container_width=True):
            reset_for_new_vocab(deps, st.session_state[K_VOCAB_PATH])
            st.rerun()


__all__ = ["render_page"]
