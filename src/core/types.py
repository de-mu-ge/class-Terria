"""基础类型：颜色与矩形。

刻意不使用 pygame.Rect / pygame.Color，保证 core、ui 层与渲染引擎无关。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

Color = tuple[int, int, int]


def _clamp(value: float, low: float = 0.0, high: float = 255.0) -> int:
    return int(max(low, min(high, round(value))))


def parse_color(value: str | Sequence[int]) -> Color:
    """支持 "#RRGGBB"、"#RGB"、[r, g, b] 三种写法。"""
    if isinstance(value, (list, tuple)):
        r, g, b = (int(v) for v in value[:3])
        return (_clamp(r), _clamp(g), _clamp(b))
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) not in (6, 8):
        raise ValueError(f"无法解析颜色: {value!r}")
    r = int(text[0:2], 16)
    g = int(text[2:4], 16)
    b = int(text[4:6], 16)
    return (r, g, b)


def parse_color_alpha(value: str) -> tuple[Color, int]:
    """支持 "#RRGGBBAA"。"""
    text = value.strip().lstrip("#")
    if len(text) == 8:
        return parse_color(text[:6]), int(text[6:8], 16)
    return parse_color(text), 255


def mix(a: Color, b: Color, t: float) -> Color:
    t = max(0.0, min(1.0, t))
    return (
        _clamp(a[0] + (b[0] - a[0]) * t),
        _clamp(a[1] + (b[1] - a[1]) * t),
        _clamp(a[2] + (b[2] - a[2]) * t),
    )


def dim(color: Color, factor: float) -> Color:
    return (_clamp(color[0] * factor), _clamp(color[1] * factor), _clamp(color[2] * factor))


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    # --- 派生量 -------------------------------------------------------
    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def centerx(self) -> float:
        return self.x + self.w / 2.0

    @property
    def centery(self) -> float:
        return self.y + self.h / 2.0

    @property
    def center(self) -> tuple[float, float]:
        return (self.centerx, self.centery)

    @property
    def size(self) -> tuple[float, float]:
        return (self.w, self.h)

    # --- 变换 ---------------------------------------------------------
    def move(self, dx: float, dy: float) -> "Rect":
        return Rect(self.x + dx, self.y + dy, self.w, self.h)

    def move_to(self, x: float | None = None, y: float | None = None) -> "Rect":
        return Rect(self.x if x is None else x, self.y if y is None else y, self.w, self.h)

    def resize(self, w: float | None = None, h: float | None = None) -> "Rect":
        return Rect(self.x, self.y, self.w if w is None else w, self.h if h is None else h)

    def inset(self, dx: float, dy: float | None = None) -> "Rect":
        dy = dx if dy is None else dy
        return Rect(self.x + dx, self.y + dy, max(0.0, self.w - dx * 2), max(0.0, self.h - dy * 2))

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px < self.right and self.y <= py < self.bottom

    def intersect(self, other: "Rect") -> "Rect":
        x = max(self.x, other.x)
        y = max(self.y, other.y)
        right = min(self.right, other.right)
        bottom = min(self.bottom, other.bottom)
        return Rect(x, y, max(0.0, right - x), max(0.0, bottom - y))

    def to_list(self) -> list[float]:
        return [self.x, self.y, self.w, self.h]

    def to_int_tuple(self) -> tuple[int, int, int, int]:
        return (int(round(self.x)), int(round(self.y)), int(round(self.w)), int(round(self.h)))

    def to_int_size(self) -> tuple[int, int]:
        return (max(0, int(round(self.w))), max(0, int(round(self.h))))

    # --- 构造 ---------------------------------------------------------
    @staticmethod
    def from_sequence(value: Iterable[float]) -> "Rect":
        seq = list(value)
        if len(seq) == 2:
            return Rect(0, 0, float(seq[0]), float(seq[1]))
        if len(seq) != 4:
            raise ValueError(f"矩形需要 2 或 4 个数值，得到 {seq!r}")
        return Rect(float(seq[0]), float(seq[1]), float(seq[2]), float(seq[3]))

    @staticmethod
    def from_center(cx: float, cy: float, w: float, h: float) -> "Rect":
        return Rect(cx - w / 2.0, cy - h / 2.0, w, h)
