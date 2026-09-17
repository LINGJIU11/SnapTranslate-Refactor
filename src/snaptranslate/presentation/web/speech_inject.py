"""浏览器朗读注入（``speechSynthesis``）。

职责：把要朗读的文本注入前端脚本，以及"每张卡片只自动朗读一次"的 token 逻辑——
对应原 ``vocab_review_web.py:322-359`` 的 ``_speak_text_once_lang`` 与
``_auto_speak_once_for_card``。

原版做法逐字保留：``streamlit.components.v1.html(..., height=0)`` 注入
``speechSynthesis`` 脚本，文本与语言都经 ``json.dumps`` 转义，语言固定 ``en-US``。

依赖方向：只允许标准库 / streamlit / ``domain.*`` / ``application.*`` /
``presentation.*``（见 ARCHITECTURE.md §1）。
"""

from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

from snaptranslate.domain.services.review_session import ReviewSession
from snaptranslate.presentation.web.session_state import K_AUTO_SPEAK_TOKEN, read_mode

#: 朗读语言（原版硬编码 ``en-US``）
SPEAK_LANG = "en-US"


def speak_text_once_lang(text: str, lang: str = SPEAK_LANG) -> None:
    """注入 ``speechSynthesis`` 朗读一次（原 ``_speak_text_once_lang``，``322-341``）。"""
    safe = json.dumps(text or "")
    lang_safe = json.dumps(lang or "")
    components.html(
        f"""
        <script>
        const txt = {safe};
        const lang = {lang_safe};
        if (window.speechSynthesis) {{
            window.speechSynthesis.cancel();
            const u = new SpeechSynthesisUtterance(txt);
            if (lang) {{
                u.lang = lang;
            }}
            window.speechSynthesis.speak(u);
        }}
        </script>
        """,
        height=0,
    )


def auto_speak_once_for_card(session: ReviewSession) -> None:
    """卡面自动朗读（原 ``_auto_speak_once_for_card``，``344-358``）。

    token 语义 ``f"{pos + 1}:{mode}"``：同一张卡 + 同一模式只读一次；
    ``word_example`` 模式在这里**只读单词**，例句由 ``pending_speak_example`` 触发。
    """
    mode = read_mode()
    if mode == "none":
        return
    token = f"{session.position + 1}:{mode}"
    if st.session_state.get(K_AUTO_SPEAK_TOKEN, "") == token:
        return
    entry = session.current()
    word = entry.word.strip() if entry is not None else ""
    if word and mode in ("word", "word_example"):
        speak_text_once_lang(word, lang=SPEAK_LANG)
    st.session_state[K_AUTO_SPEAK_TOKEN] = token
