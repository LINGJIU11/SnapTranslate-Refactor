"""Web 复习页的会话状态。

职责：``st.session_state`` 键名常量、首次初始化，以及三个状态迁移入口
（换词表 / 切复习顺序 / 切朗读模式）——对应原 ``vocab_review_web.py:189-264`` 与
``380-388``、``479-482``。

词表、顺序、位置、揭示状态由领域服务 ``ReviewSession`` 持有（原版是 ``vocab`` /
``order`` / ``pos`` 与三个 ``show_*`` 键）；其余键名与初值与原版逐字一致。

依赖方向：只允许标准库 / streamlit / ``domain.*`` / ``application.*`` /
``presentation.*``（见 ARCHITECTURE.md §1）。
"""

from __future__ import annotations

import streamlit as st

from snaptranslate.application.deps import WebReviewDeps
from snaptranslate.domain.models.review import SortMode
from snaptranslate.domain.services.review_session import ReviewSession

# —— st.session_state 键名（与原版逐字一致，只有 vocab/order/pos 改为持有 session）——
K_SESSION = "session"  # 取代原版 vocab / order / pos 三个键
K_VOCAB_PATH = "vocab_path"
K_KEY_PATH = "key_path"
K_SORT_MODE = "sort_mode"
K_LAST_MSG = "last_msg"
K_BOOT_BACKUP_DONE = "boot_backup_done"
K_READ_MODE = "read_mode"
K_AUTO_SPEAK_TOKEN = "last_auto_speak_token"
K_PENDING_SPEAK_EXAMPLE = "pending_speak_example"
K_MANUAL_API_KEY = "manual_api_key"
K_READ_MODE_WIDGET = "read_mode_main"


def session() -> ReviewSession:
    """当前复习会话（词表 + 顺序 + 位置 + 揭示状态）。"""
    return st.session_state[K_SESSION]


def read_mode() -> str:
    return str(st.session_state[K_READ_MODE])


def _reset_reveal() -> None:
    """等价于原版把三个 ``show_*`` 置为 False（现在由 ``RevealState`` 承载）。"""
    session().reveal.reset()


def init_state(deps: WebReviewDeps) -> None:
    """``init_state`` 等价物（原 ``vocab_review_web.py:235-264``）。

    ``vocab`` / ``order`` / ``pos`` 三个键改为一个 ``session`` 对象；其余键同名同初值。
    原版在 ``order`` 之前先建 ``vocab``，这里由 ``ReviewSession.__init__`` 一次性完成
    （加载容错词表 → 评分归一化 → 按模式建顺序），顺序与初值等价。

    另外：原版所有落盘都用 ``st.session_state.vocab_path``（当前生效路径），而
    ``streamlit_entry`` 每次 rerun 都会重建 Container/UseCase（路径回到默认值），
    所以这里每次都要把用例的当前词表路径同步成会话里的那个；只有**首次**才从磁盘加载
    （后续 rerun 保留内存中的词表与顺序，与原版一致）。
    """
    if K_VOCAB_PATH not in st.session_state:
        st.session_state[K_VOCAB_PATH] = deps.vocab_path
    if K_KEY_PATH not in st.session_state:
        st.session_state[K_KEY_PATH] = deps.api_key_path
    if K_SORT_MODE not in st.session_state:
        st.session_state[K_SORT_MODE] = SortMode.RANDOM.value
    deps.review.use_path(st.session_state[K_VOCAB_PATH])
    if K_SESSION not in st.session_state:
        st.session_state[K_SESSION] = deps.review.create_session(
            deps.review.load(), st.session_state[K_SORT_MODE]
        )
    if K_LAST_MSG not in st.session_state:
        st.session_state[K_LAST_MSG] = ""
    if K_BOOT_BACKUP_DONE not in st.session_state:
        st.session_state[K_BOOT_BACKUP_DONE] = False
    if K_READ_MODE not in st.session_state:
        st.session_state[K_READ_MODE] = "none"
    if K_AUTO_SPEAK_TOKEN not in st.session_state:
        st.session_state[K_AUTO_SPEAK_TOKEN] = ""
    if K_PENDING_SPEAK_EXAMPLE not in st.session_state:
        st.session_state[K_PENDING_SPEAK_EXAMPLE] = False


def reset_for_new_vocab(deps: WebReviewDeps, path: str) -> None:
    """换词表（原 ``reset_for_new_vocab``，``vocab_review_web.py:189-199``）。

    原版 ``items = load_vocab(path)`` 用的是**传入的新路径**，因此必须先 ``use_path``
    再 ``load``；随后覆盖 ``vocab`` → ``pos=0`` → 三个 ``show_*`` 置 False → 建 order →
    ``boot_backup_done=False``，这里由新建的会话一次性完成等价动作。
    """
    deps.review.use_path(path)
    vocabulary = deps.review.load()
    st.session_state[K_VOCAB_PATH] = path
    st.session_state[K_SESSION] = deps.review.create_session(vocabulary, st.session_state[K_SORT_MODE])
    st.session_state[K_BOOT_BACKUP_DONE] = False


def apply_sort_mode(deps: WebReviewDeps, mode: str) -> None:
    """切换复习顺序（原 ``vocab_review_web.py:380-388``）。"""
    if mode == st.session_state[K_SORT_MODE]:
        return
    st.session_state[K_SORT_MODE] = mode
    session().set_mode(mode)  # 重建顺序 + 位置归零
    _reset_reveal()
    st.session_state[K_AUTO_SPEAK_TOKEN] = ""
    st.rerun()


def apply_read_mode(mode: str) -> None:
    """切换自动朗读模式（原 ``vocab_review_web.py:479-482``）。"""
    st.session_state[K_READ_MODE] = mode
    st.session_state[K_AUTO_SPEAK_TOKEN] = ""
    st.rerun()
