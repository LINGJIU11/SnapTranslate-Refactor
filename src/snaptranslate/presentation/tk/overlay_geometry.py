"""浮层几何：屏幕矩形、命中判定、靠锚点摆放。

**为什么单独一个模块**：悬浮卡片（``floating_card``）与中译英输入框（``input_box``）
都要做同一件事——"以某个坐标为锚点、+16 偏移、并夹在屏幕内"，还要判断
"鼠标是不是落在浮层里（落在里面不算关闭信号）"。这两块逻辑只写一份，
浮层组件只管自己的内容与生命周期。
"""

from __future__ import annotations

#: 锚点到浮层左上角的偏移（原 ``main.py:733``）
OFFSET = 16
#: 与屏幕边缘的最小间距
MARGIN = 10

#: ``(left, top, right, bottom)``，右下开区间
Bounds = tuple[int, int, int, int]


def is_inside(bounds: Bounds, point: tuple[int, int]) -> bool:
    """点是否落在矩形内（纯函数，便于单测）。"""
    left, top, right, bottom = bounds
    x, y = point
    return left <= x < right and top <= y < bottom


def place_near(
    point: tuple[int, int],
    size: tuple[int, int],
    screen: tuple[int, int],
    *,
    offset: int = OFFSET,
    margin: int = MARGIN,
) -> tuple[int, int, Bounds]:
    """按锚点算出浮层左上角，返回 ``(x, y, bounds)``。

    :param point: 锚点（一般是**热键按下瞬间**的鼠标位置，见 KNOWN_ISSUES.md #23）
    :param size: 浮层尺寸 ``(宽, 高)``
    :param screen: 屏幕尺寸 ``(宽, 高)``
    """
    width, height = size
    screen_w, screen_h = screen
    cursor_x, cursor_y = point
    x = min(max(margin, cursor_x + offset), max(margin, screen_w - width - margin))
    y = min(max(margin, cursor_y + offset), max(margin, screen_h - height - margin))
    return x, y, (x, y, x + width, y + height)


__all__ = ["Bounds", "MARGIN", "OFFSET", "is_inside", "place_near"]
