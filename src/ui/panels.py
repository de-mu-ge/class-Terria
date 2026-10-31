"""通用面板绘制（对话框、字幕条、任务卡、菜单都复用）。

依据 整体风格与UI/SKILL.md 第 5 节：
- 面板底色 #0B1219 @ 82%
- 外框 2px 暖金 #C9A227，内 1px 半透明暗边，直角
"""

from __future__ import annotations

from ..core.types import Color, Rect, dim
from ..render.renderer import Renderer, Texture


def draw_panel(
    renderer: Renderer,
    rect: Rect,
    background: Color,
    background_alpha: int,
    border: Color,
    outer_width: int = 2,
    inner_dark: bool = True,
    inner_color: Color | None = None,
) -> None:
    renderer.draw_rect(rect, background, alpha=background_alpha)
    inset = outer_width
    if inner_dark:
        renderer.draw_frame(rect.inset(inset * 0.5), inner_color or dim(border, 0.35), width=1, alpha=210)
    renderer.draw_frame(rect, border, width=outer_width, alpha=255)


def draw_plain_panel(
    renderer: Renderer,
    rect: Rect,
    background: Color,
    alpha: int,
    border: Color | None = None,
    border_width: int = 1,
    radius: int = 0,
) -> None:
    if radius > 0:
        renderer.draw_round_rect(rect, background, radius, alpha=alpha)
        if border is not None:
            renderer.draw_round_frame(rect, border, radius, width=border_width, alpha=255)
    else:
        renderer.draw_rect(rect, background, alpha=alpha)
        if border is not None:
            renderer.draw_frame(rect, border, width=border_width, alpha=255)


def build_vertical_gradient(
    renderer: Renderer,
    top: Color,
    bottom: Color,
    top_alpha: int,
    bottom_alpha: int,
    height: int = 540,
) -> Texture:
    """生成 1×height 的竖直渐变纹理（用于天气遮罩/暗角）。"""
    data = bytearray()
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        a = int(top_alpha + (bottom_alpha - top_alpha) * t)
        data += bytes((max(0, min(255, r)), max(0, min(255, g)),
                       max(0, min(255, b)), max(0, min(255, a))))
    return renderer.create_texture(1, height, bytes(data))


def build_horizontal_gradient(
    renderer: Renderer,
    left: Color,
    right: Color,
    left_alpha: int,
    right_alpha: int,
    width: int = 960,
) -> Texture:
    """生成 width×1 的水平渐变纹理（用于两侧暗角）。"""
    data = bytearray()
    for x in range(width):
        t = x / max(1, width - 1)
        r = int(left[0] + (right[0] - left[0]) * t)
        g = int(left[1] + (right[1] - left[1]) * t)
        b = int(left[2] + (right[2] - left[2]) * t)
        a = int(left_alpha + (right_alpha - left_alpha) * t)
        data += bytes((max(0, min(255, r)), max(0, min(255, g)),
                       max(0, min(255, b)), max(0, min(255, a))))
    return renderer.create_texture(width, 1, bytes(data))


def draw_texture_stretched(renderer: Renderer, texture: Texture, rect: Rect, alpha: int = 255) -> None:
    renderer.draw_texture(texture, rect, alpha=alpha)
