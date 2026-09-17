"""界面主题常量。

原版在 ``main.py`` 与 ``vocab_review.py`` 各维护了一份（后者多出 4 个颜色），
现收敛为唯一一份，保证两个 Tk 窗口视觉一致。
"""

from __future__ import annotations

# —— 通用 ——
UI_BG = "#eef1f6"
UI_CARD = "#ffffff"
UI_BORDER = "#e2e8f0"
UI_TEXT = "#0f172a"
UI_TEXT_MUTED = "#64748b"
UI_ACCENT = "#4f46e5"
UI_ACCENT_HOVER = "#4338ca"
UI_CHIP = "#e0e7ff"
UI_STATUS_BG = "#f1f5f9"
UI_LOG_BG = "#f8fafc"

# —— 复习窗口专用 ——
UI_EXAMPLE_PANEL = "#f8fafc"
UI_MEANING = "#047857"
UI_KEYWORD = "#4f46e5"
UI_ZH = "#0d9488"

# —— 自评按钮 ——
UI_GRADE_KNOW = "#059669"
UI_GRADE_KNOW_HOVER = "#047857"
UI_GRADE_VAGUE = "#ea580c"
UI_GRADE_VAGUE_HOVER = "#c2410c"
UI_GRADE_UNKNOWN = "#dc2626"
UI_GRADE_UNKNOWN_HOVER = "#b91c1c"

# —— 删除按钮 ——
UI_DANGER_BG = "#fee2e2"
UI_DANGER_FG = "#b91c1c"
UI_DANGER_BG_HOVER = "#fecaca"
UI_DANGER_FG_HOVER = "#991b1b"

# —— 鼠标旁悬浮卡片 / 光标状态条 ——
UI_FLOAT_BG = "#1e293b"
UI_FLOAT_FG = "#f1f5f9"
UI_FLOAT_MUTED = "#94a3b8"
UI_FLOAT_BTN = "#6366f1"
UI_FLOAT_BTN_HOVER = "#4f46e5"
UI_CURSOR_STATUS_BG = "#0f172a"
UI_CURSOR_STATUS_FG = "#e2e8f0"

# —— 截图遮罩 ——
SNIP_OVERLAY_ALPHA = 0.5
SNIP_OVERLAY_CANVAS_BG = "#0f172a"
SNIP_RECT_OUTLINE = "#38bdf8"
SNIP_HINT_FG = "#f8fafc"
SNIP_INFO_FG = "#93c5fd"

FONT_FAMILY = "Microsoft YaHei UI"
FONT_FAMILY_MONO = "Consolas"

#: 日志区配色（原版 log_text 的 orig/trans 标签）
LOG_TAG_ORIG = UI_ACCENT
LOG_TAG_TRANS = "#0d9488"
