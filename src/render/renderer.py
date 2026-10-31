"""渲染抽象层。

规则：core / ui / scenes 只依赖本文件里的 Renderer、Texture、Font，不 import pygame。
将来换引擎只需要再写一个 Renderer 实现（如 SdlRenderer / ArcadeRenderer）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence

from ..core.types import Color, Rect


class Texture:
    """后端纹理句柄。"""

    def __init__(self, width: int, height: int, opaque=None, key: str = "") -> None:
        self.width = int(width)
        self.height = int(height)
        self.opaque = opaque
        self.key = key

    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)

    def __repr__(self) -> str:  # pragma: no cover
        return f"Texture({self.width}x{self.height}, key={self.key!r})"


class Font:
    """后端字体句柄。"""

    def __init__(self, path: str, size: int, opaque=None) -> None:
        self.path = path
        self.size = int(size)
        self.opaque = opaque
        self.line_height = int(size * 1.45)
        self.ascent = int(size)

    def __repr__(self) -> str:  # pragma: no cover
        return f"Font({Path(self.path).name}@{self.size})"


class Renderer(ABC):
    """引擎无关渲染接口，逻辑坐标系固定为 960×540。"""

    def __init__(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    # --- 基础 ---------------------------------------------------------
    @property
    def size(self) -> tuple[int, int]:
        return (self._width, self._height)

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @abstractmethod
    def begin_frame(self) -> None:
        """开始一帧（清空裁剪栈、可选清屏）。"""

    @abstractmethod
    def present(self) -> None:
        """把逻辑画布呈现到窗口。"""

    @abstractmethod
    def clear(self, color: Color) -> None:
        ...

    # --- 纹理 ---------------------------------------------------------
    @abstractmethod
    def load_texture(self, path: Path) -> Texture:
        ...

    @abstractmethod
    def create_texture(self, width: int, height: int, rgba: bytes) -> Texture:
        """用 RGBA 字节数组创建纹理（程序化像素美术用）。"""

    @abstractmethod
    def create_solid(self, width: int, height: int, color: Color) -> Texture:
        ...

    @abstractmethod
    def draw_texture(
        self,
        texture: Texture,
        dest: Rect,
        src: Rect | None = None,
        alpha: int = 255,
        smooth: bool = False,
        flip_x: bool = False,
    ) -> None:
        ...

    # --- 图元 ---------------------------------------------------------
    @abstractmethod
    def draw_rect(self, rect: Rect, color: Color, alpha: int = 255) -> None:
        ...

    @abstractmethod
    def draw_frame(self, rect: Rect, color: Color, width: int = 1, alpha: int = 255) -> None:
        ...

    @abstractmethod
    def draw_round_rect(self, rect: Rect, color: Color, radius: int, alpha: int = 255) -> None:
        ...

    @abstractmethod
    def draw_round_frame(self, rect: Rect, color: Color, radius: int, width: int = 1, alpha: int = 255) -> None:
        ...

    @abstractmethod
    def draw_line(self, start: tuple[float, float], end: tuple[float, float], color: Color,
                  width: int = 1, alpha: int = 255) -> None:
        ...

    @abstractmethod
    def draw_polygon(self, points: Sequence[tuple[float, float]], color: Color, alpha: int = 255) -> None:
        ...

    # --- 文字 ---------------------------------------------------------
    @abstractmethod
    def load_font(self, path: str, size: int) -> Font:
        ...

    @abstractmethod
    def measure_text(self, text: str, font: Font) -> tuple[int, int]:
        ...

    @abstractmethod
    def draw_text(
        self,
        text: str,
        position: tuple[float, float],
        font: Font,
        color: Color,
        align: str = "left",
        alpha: int = 255,
    ) -> None:
        ...

    # --- 裁剪 ---------------------------------------------------------
    @abstractmethod
    def push_clip(self, rect: Rect) -> None:
        ...

    @abstractmethod
    def pop_clip(self) -> None:
        ...

    # --- 其它 ---------------------------------------------------------
    @abstractmethod
    def capture(self, path: Path) -> bool:
        """把当前逻辑画布存成 PNG（自动测试用）。"""

    @abstractmethod
    def shutdown(self) -> None:
        ...

    # --- 工具（与后端无关） -------------------------------------------
    def fit_rect(self, src_size: tuple[int, int], dest: Rect) -> Rect:
        """按比例塞进 dest 并居中，返回实际绘制矩形。"""
        sw, sh = src_size
        if sw <= 0 or sh <= 0:
            return dest
        scale = min(dest.w / sw, dest.h / sh)
        w = sw * scale
        h = sh * scale
        return Rect(dest.x + (dest.w - w) / 2, dest.y + (dest.h - h) / 2, w, h)
