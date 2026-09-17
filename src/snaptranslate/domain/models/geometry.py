"""几何值对象：截图矩形区域。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BBox:
    """屏幕坐标矩形（左上角 + 右下角），对应原版的 ``(left, top, right, bottom)`` 元组。"""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def as_tuple(self) -> tuple[int, int, int, int]:
        """传给 ``ImageGrab.grab(bbox=...)`` 的四元组。"""
        return (self.left, self.top, self.right, self.bottom)

    def is_valid_snip(self, min_side: int = 6) -> bool:
        """原版判定：宽或高小于 6 像素即视为误触，取消。"""
        return self.width >= min_side and self.height >= min_side
