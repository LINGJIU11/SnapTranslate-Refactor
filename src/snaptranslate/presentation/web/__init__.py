"""Web 表示层（Streamlit）。

本包只放"渲染 + 事件转发"代码：一句话界面文案来自 ``presentation.texts``，
顺序 / 评分 / 推进 / 批量生成全部交给 ``application`` 的用例，
词表与顺序状态由领域服务 ``ReviewSession`` 持有。

**依赖方向**：只允许 import 标准库、streamlit、``domain.*``、``application.*``、
``config.*``、``presentation.*``；禁止 import ``infrastructure.*`` 与 ``bootstrap.*``
（见 ARCHITECTURE.md §1）。

对外只暴露 :func:`snaptranslate.presentation.web.streamlit_review.render_page`；
进程级入口在 ``bootstrap/streamlit_entry.py``（``streamlit run`` 需要脚本式入口）。

模块划分（同级、单向依赖）::

    streamlit_review.py   页面骨架 + render_page（唯一对外入口）
    session_state.py      session_state 键名 / 初始化 / 换词表·切排序·切朗读模式
    card_view.py          侧边栏设置区 + 卡片与三档自评
    speech_inject.py      speechSynthesis 注入 + 自动朗读 token
    generate_panel.py     DeepSeek 批量补例句面板

依赖方向：``streamlit_review`` → ``card_view`` / ``generate_panel`` → ``session_state`` /
``speech_inject``；不出现反向 import。
"""

from __future__ import annotations

__all__: list[str] = []
