"""侧边栏设置区与卡片/评分区渲染。

职责：侧边栏（词表路径 / 复习顺序 / DeepSeek 可选配置）与主区卡片——对应原
``vocab_review_web.py:367-394``（侧边栏）与 ``403-469``（卡片、显示隐藏按钮、三档自评）。

评分一律走用例 ``deps.review.grade(session, grade)``：幅度、是否推进、是否重排顺序
都在用例/领域服务里，本模块只负责渲染与按钮事件转发。

依赖方向：只允许标准库 / streamlit / ``domain.*`` / ``application.*`` /
``presentation.*``（见 ARCHITECTURE.md §1）。
"""

from __future__ import annotations

import streamlit as st

from snaptranslate.application.deps import WebReviewDeps
from snaptranslate.domain.errors import VocabularyIoError
from snaptranslate.domain.models.review import Grade, GradeResult
from snaptranslate.domain.services.review_session import ReviewSession
from snaptranslate.presentation.texts import WebText
from snaptranslate.presentation.web.session_state import (
    K_AUTO_SPEAK_TOKEN,
    K_KEY_PATH,
    K_LAST_MSG,
    K_MANUAL_API_KEY,
    K_PENDING_SPEAK_EXAMPLE,
    K_READ_MODE_WIDGET,
    K_SORT_MODE,
    K_VOCAB_PATH,
    apply_read_mode,
    apply_sort_mode,
    read_mode,
    reset_for_new_vocab,
    session,
)
from snaptranslate.presentation.web.speech_inject import SPEAK_LANG, auto_speak_once_for_card, speak_text_once_lang

#: 复习顺序取值顺序（原版 selectbox 的 options 顺序）
SORT_MODES: tuple[str, ...] = ("random", "score_asc", "score_desc")
#: 自动朗读模式取值顺序
READ_MODES: tuple[str, ...] = ("none", "word", "word_example")


def render_sidebar(deps: WebReviewDeps) -> None:
    """设置区（原 ``vocab_review_web.py:367-394``）。"""
    with st.sidebar:
        st.subheader(WebText.SETTINGS)
        vocab_path_in = st.text_input(WebText.VOCAB_PATH, value=st.session_state[K_VOCAB_PATH])
        if st.button(WebText.LOAD_VOCAB, use_container_width=True):
            reset_for_new_vocab(deps, vocab_path_in.strip() or deps.vocab_path)
            st.rerun()

        sort_mode = st.selectbox(
            WebText.SORT_LABEL,
            options=list(SORT_MODES),
            format_func=lambda x: WebText.SORT_OPTIONS[x],
            index=SORT_MODES.index(st.session_state[K_SORT_MODE]),
        )
        apply_sort_mode(deps, sort_mode)

        st.divider()
        st.subheader(WebText.DEEPSEEK)
        key_path_in = st.text_input(WebText.KEY_PATH, value=st.session_state[K_KEY_PATH])
        st.session_state[K_KEY_PATH] = key_path_in.strip() or deps.api_key_path
        st.text_input(WebText.MANUAL_KEY, key=K_MANUAL_API_KEY, type="password")


def grade_message(result: GradeResult) -> str:
    return WebText.grade_saved(result.old_score, result.new_score, result.delta)


def apply_grade(deps: WebReviewDeps, grade: Grade) -> None:
    """三档自评（原 ``apply_grade``，``vocab_review_web.py:202-232``）。

    评分幅度、是否推进、是否重排顺序全部由 ``deps.review.grade`` 完成；
    失败时原版弹 ``st.error`` 且**不**推进卡片——用例在保存抛错时同样不推进。
    """
    try:
        result = deps.review.grade(session(), grade)
    except VocabularyIoError as exc:
        st.error(WebText.GRADE_SAVE_FAILED.format(error=exc.render()))
        return
    if result is not None:
        st.session_state[K_LAST_MSG] = grade_message(result)


def render_card(deps: WebReviewDeps, session: ReviewSession) -> bool:
    """当前卡片（原 ``vocab_review_web.py:403-469``）；空词表时返回 ``False``。"""
    entry = session.current()
    if entry is None:
        st.warning(WebText.EMPTY_VOCAB)
        return False
    word_text = entry.word.strip()
    # 行为等价：保留原版缺陷（见 KNOWN_ISSUES.md #18）：word 不做 HTML 转义直接拼进 <h1>
    st.markdown(f"<h1 style='margin-bottom:0.2rem;'>{word_text}</h1>", unsafe_allow_html=True)
    st.write(WebText.SCORE.format(score=entry.score))
    auto_speak_once_for_card(session)

    ex_text = entry.example.strip()
    if st.session_state[K_PENDING_SPEAK_EXAMPLE]:
        if ex_text:
            speak_text_once_lang(ex_text, lang=SPEAK_LANG)
        st.session_state[K_PENDING_SPEAK_EXAMPLE] = False

    col_meaning, col_example = st.columns(2)
    with col_meaning:
        if st.button(WebText.SHOW_MEANING, use_container_width=True):
            session.reveal.toggle_meaning()
            st.rerun()
    with col_example:
        if st.button(WebText.SHOW_EXAMPLE, use_container_width=True):
            turning_on = not session.reveal.show_example
            session.reveal.toggle_example()
            if not session.reveal.show_example:
                st.session_state[K_PENDING_SPEAK_EXAMPLE] = False
            elif turning_on and read_mode() == "word_example":
                st.session_state[K_PENDING_SPEAK_EXAMPLE] = True
            st.rerun()

    if session.reveal.show_example:
        if st.button(WebText.SHOW_EXAMPLE_ZH, use_container_width=True):
            session.reveal.toggle_example_zh()
            st.rerun()

    if session.reveal.show_meaning:
        st.success(WebText.MEANING.format(meaning=entry.meaning))
    if session.reveal.show_example:
        st.write(WebText.EXAMPLE_EN)
        st.write(ex_text if ex_text else WebText.EXAMPLE_MISSING)
        if session.reveal.show_example_zh:
            ex_zh = entry.example_zh.strip()
            st.write(WebText.EXAMPLE_ZH)
            st.write(ex_zh if ex_zh else WebText.EXAMPLE_MISSING)

    if not session.reveal.any_revealed:
        st.caption(WebText.REVEAL_HINT)

    st.divider()
    col_know, col_vague, col_unknown = st.columns(3)
    with col_know:
        if st.button(WebText.GRADE_LABELS[Grade.KNOW], use_container_width=True):
            apply_grade(deps, Grade.KNOW)
            st.rerun()
    with col_vague:
        if st.button(WebText.GRADE_LABELS[Grade.VAGUE], use_container_width=True):
            apply_grade(deps, Grade.VAGUE)
            st.rerun()
    with col_unknown:
        if st.button(WebText.GRADE_LABELS[Grade.UNKNOWN], use_container_width=True):
            apply_grade(deps, Grade.UNKNOWN)
            st.rerun()

    st.divider()
    read_mode_main = st.selectbox(
        WebText.READ_LABEL,
        options=list(READ_MODES),
        format_func=lambda x: WebText.READ_OPTIONS[x],
        index=READ_MODES.index(read_mode()),
        key=K_READ_MODE_WIDGET,
    )
    if read_mode_main != read_mode():
        apply_read_mode(read_mode_main)

    col_word, col_sentence = st.columns(2)
    with col_word:
        if st.button(WebText.SPEAK_WORD, use_container_width=True):
            speak_text_once_lang(word_text, lang=SPEAK_LANG)
    with col_sentence:
        if st.button(WebText.SPEAK_EXAMPLE, use_container_width=True, disabled=not bool(ex_text)):
            speak_text_once_lang(ex_text, lang=SPEAK_LANG)
    return True
