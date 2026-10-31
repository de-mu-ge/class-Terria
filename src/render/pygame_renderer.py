"""pygame-ce 渲染实现。

要点：
- 所有绘制先落到 960×540 的逻辑画布，最后一帧用整数倍最近邻放大到窗口（禁止平滑拉伸）。
- 纹理缩放按 (纹理, 源矩形, 目标尺寸, 平滑标志) 缓存，避免每帧重复采样。
- 文字渲染按 (文字, 字体, 颜色) 缓存，打字机逐帧重绘也不贵。
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from pathlib import Path
from typing import Sequence

import pygame

from ..core.types import Color, Rect, parse_color
from .renderer import Font, Renderer, Texture

log = logging.getLogger(__name__)

_TEXT_CACHE_LIMIT = 512
_SCALE_CACHE_LIMIT = 96


class _Cache(OrderedDict):
    def get_or(self, key, factory):
        if key in self:
            self.move_to_end(key)
            return self[key]
        value = factory()
        self[key] = value
        if len(self) > _TEXT_CACHE_LIMIT:
            self.popitem(last=False)
        return value


class PygameRenderer(Renderer):
    def __init__(
        self,
        width: int,
        height: int,
        window_scale: int = 2,
        caption: str = "",
        headless: bool = False,
        fullscreen: bool = False,
    ) -> None:
        super().__init__(width, height)
        if headless:
            import os

            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

        pygame.init()
        pygame.display.init()
        if caption:
            pygame.display.set_caption(caption)

        self.window_scale = max(1, int(window_scale))
        self._headless = headless
        flags = pygame.SCALED if False else 0
        size = (width * self.window_scale, height * self.window_scale)
        if fullscreen:
            try:
                self._window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            except pygame.error:
                log.warning("全屏不可用，退回窗口模式")
                self._window = pygame.display.set_mode(size, flags)
        else:
            self._window = pygame.display.set_mode(size, flags)

        # 逻辑画布（所有游戏绘制都在这上面）
        self._canvas = pygame.Surface((width, height)).convert()
        self._clip_stack: list[pygame.Rect] = []
        self._text_cache = _Cache()
        self._scale_cache = _Cache()
        self._font_cache: dict[tuple[str, int], Font] = {}

    # --- 帧 -----------------------------------------------------------
    def begin_frame(self) -> None:
        self._clip_stack.clear()
        self._canvas.set_clip(None)

    def present(self) -> None:
        if self.window_scale != 1:
            pygame.transform.scale(self._canvas, self._window.get_size(), self._window)
        else:
            self._window.blit(self._canvas, (0, 0))
        pygame.display.flip()

    def clear(self, color: Color) -> None:
        self._canvas.fill(parse_color(color))

    # --- 纹理 ---------------------------------------------------------
    def load_texture(self, path: Path) -> Texture:
        image = pygame.image.load(str(path))
        image = image.convert_alpha()
        return Texture(image.get_width(), image.get_height(), image, key=str(path))

    def create_texture(self, width: int, height: int, rgba: bytes) -> Texture:
        surface = pygame.image.frombuffer(rgba, (width, height), "RGBA").convert_alpha()
        return Texture(width, height, surface, key=f"proc:{width}x{height}")

    def create_solid(self, width: int, height: int, color: Color) -> Texture:
        surface = pygame.Surface((max(1, width), max(1, height)), pygame.SRCALPHA)
        surface.fill((*parse_color(color), 255))
        return Texture(width, height, surface, key=f"solid:{color}:{width}x{height}")

    def _scaled(self, texture: Texture, size: tuple[int, int], src: Rect | None, smooth: bool,
                flip_x: bool) -> pygame.Surface:
        surface: pygame.Surface = texture.opaque
        dw, dh = max(1, int(round(size[0]))), max(1, int(round(size[1])))
        key = (texture.key, id(surface), dw, dh,
               None if src is None else src.to_int_tuple(), smooth, flip_x)
        if not smooth and src is None and (texture.width, texture.height) == (dw, dh) and not flip_x:
            return surface
        cached = self._scale_cache.get(key)
        if cached is not None:
            self._scale_cache.move_to_end(key)
            return cached

        work = surface
        if src is not None:
            rect = pygame.Rect(src.to_int_tuple()).clip(surface.get_rect())
            if rect.width <= 0 or rect.height <= 0:
                rect = surface.get_rect()
            work = surface.subsurface(rect)
        if flip_x:
            work = pygame.transform.flip(work, True, False)
        if (work.get_width(), work.get_height()) != (dw, dh):
            if smooth:
                work = pygame.transform.smoothscale(work, (dw, dh))
            else:
                work = pygame.transform.scale(work, (dw, dh))
        elif flip_x:
            work = work.copy()
        self._scale_cache[key] = work
        if len(self._scale_cache) > _SCALE_CACHE_LIMIT:
            self._scale_cache.popitem(last=False)
        return work

    def draw_texture(
        self,
        texture: Texture,
        dest: Rect,
        src: Rect | None = None,
        alpha: int = 255,
        smooth: bool = False,
        flip_x: bool = False,
    ) -> None:
        if texture is None or texture.opaque is None:
            return
        if alpha <= 0 or dest.w <= 0 or dest.h <= 0:
            return
        surface = self._scaled(texture, dest.to_int_size(), src, smooth, flip_x)
        surface.set_alpha(int(max(0, min(255, alpha))))
        self._canvas.blit(surface, (int(round(dest.x)), int(round(dest.y))))
        surface.set_alpha(255)

    # --- 图元 ---------------------------------------------------------
    def draw_rect(self, rect: Rect, color: Color, alpha: int = 255) -> None:
        if rect.w <= 0 or rect.h <= 0 or alpha <= 0:
            return
        if alpha >= 255:
            pygame.draw.rect(self._canvas, parse_color(color), rect.to_int_tuple())
            return
        layer = pygame.Surface(rect.to_int_size(), pygame.SRCALPHA)
        layer.fill((*parse_color(color), int(alpha)))
        self._canvas.blit(layer, (int(round(rect.x)), int(round(rect.y))))

    def draw_frame(self, rect: Rect, color: Color, width: int = 1, alpha: int = 255) -> None:
        if rect.w <= 0 or rect.h <= 0 or alpha <= 0:
            return
        w = max(1, int(width))
        r = rect.to_int_tuple()
        if alpha >= 255:
            pygame.draw.rect(self._canvas, parse_color(color), r, w)
            return
        layer = pygame.Surface((r[2] + w, r[3] + w), pygame.SRCALPHA)
        pygame.draw.rect(layer, (*parse_color(color), int(alpha)), pygame.Rect(0, 0, r[2], r[3]), w)
        self._canvas.blit(layer, (r[0], r[1]))

    def draw_round_rect(self, rect: Rect, color: Color, radius: int, alpha: int = 255) -> None:
        if rect.w <= 0 or rect.h <= 0 or alpha <= 0:
            return
        if alpha >= 255:
            pygame.draw.rect(self._canvas, parse_color(color), rect.to_int_tuple(), border_radius=int(radius))
            return
        layer = pygame.Surface(rect.to_int_size(), pygame.SRCALPHA)
        pygame.draw.rect(layer, (*parse_color(color), int(alpha)),
                         pygame.Rect(0, 0, *rect.to_int_size()), border_radius=int(radius))
        self._canvas.blit(layer, (int(round(rect.x)), int(round(rect.y))))

    def draw_round_frame(self, rect: Rect, color: Color, radius: int, width: int = 1,
                         alpha: int = 255) -> None:
        if rect.w <= 0 or rect.h <= 0 or alpha <= 0:
            return
        layer = pygame.Surface(rect.to_int_size(), pygame.SRCALPHA)
        pygame.draw.rect(layer, (*parse_color(color), int(alpha)),
                         pygame.Rect(0, 0, *rect.to_int_size()), max(1, int(width)),
                         border_radius=int(radius))
        self._canvas.blit(layer, (int(round(rect.x)), int(round(rect.y))))

    def draw_line(self, start, end, color: Color, width: int = 1, alpha: int = 255) -> None:
        if alpha <= 0:
            return
        w = max(1, int(width))
        x0, y0 = int(round(start[0])), int(round(start[1]))
        x1, y1 = int(round(end[0])), int(round(end[1]))
        if alpha < 255:
            # 只为线段包围盒分配表面：粒子（雨丝）每帧几十上百条，不能一条一个整屏
            pad = w + 2
            left = min(x0, x1) - pad
            top = min(y0, y1) - pad
            size = (abs(x1 - x0) + pad * 2 + 1, abs(y1 - y0) + pad * 2 + 1)
            layer = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.line(layer, (*parse_color(color), int(alpha)),
                             (x0 - left, y0 - top), (x1 - left, y1 - top), w)
            self._canvas.blit(layer, (left, top))
            return
        pygame.draw.line(self._canvas, parse_color(color), (x0, y0), (x1, y1), w)

    def draw_polygon(self, points: Sequence[tuple[float, float]], color: Color, alpha: int = 255) -> None:
        if len(points) < 3 or alpha <= 0:
            return
        pts = [(int(round(x)), int(round(y))) for x, y in points]
        if alpha < 255:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            left, top = min(xs) - 2, min(ys) - 2
            size = (max(xs) - left + 3, max(ys) - top + 3)
            layer = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.polygon(layer, (*parse_color(color), int(alpha)),
                                [(x - left, y - top) for x, y in pts])
            self._canvas.blit(layer, (left, top))
            return
        pygame.draw.polygon(self._canvas, parse_color(color), pts)

    # --- 文字 ---------------------------------------------------------
    def load_font(self, path: str, size: int) -> Font:
        key = (path, int(size))
        cached = self._font_cache.get(key)
        if cached is not None:
            return cached
        try:
            handle = pygame.font.Font(path, int(size))
        except (OSError, pygame.error):
            log.warning("字体加载失败，改用默认字体：%s", path)
            handle = pygame.font.Font(None, int(size))
        font = Font(path, size, handle)
        font.line_height = int(handle.get_linesize())
        font.ascent = int(handle.get_ascent())
        self._font_cache[key] = font
        return font

    def _render_text(self, text: str, font: Font, color: Color, alpha: int) -> pygame.Surface:
        key = (text, font.path, font.size, color, alpha)
        return self._text_cache.get_or(
            key, lambda: self._render_text_uncached(text, font, color, alpha)
        )

    def _render_text_uncached(self, text: str, font: Font, color: Color, alpha: int) -> pygame.Surface:
        surface = font.opaque.render(text, True, parse_color(color)).convert_alpha()
        if alpha < 255:
            surface.set_alpha(int(max(0, min(255, alpha))))
        return surface

    def measure_text(self, text: str, font: Font) -> tuple[int, int]:
        if not text:
            return (0, font.line_height)
        return font.opaque.size(text)

    def draw_text(self, text, position, font, color, align="left", alpha=255) -> None:
        if not text or alpha <= 0:
            return
        surface = self._render_text(text, font, color, alpha)
        x, y = position
        width = surface.get_width()
        if align == "center":
            x -= width / 2
        elif align == "right":
            x -= width
        self._canvas.blit(surface, (int(round(x)), int(round(y))))

    # --- 裁剪 ---------------------------------------------------------
    def push_clip(self, rect: Rect) -> None:
        current = self._canvas.get_clip()
        target = pygame.Rect(rect.to_int_tuple())
        self._clip_stack.append(current)
        self._canvas.set_clip(target if current is None else current.clip(target))

    def pop_clip(self) -> None:
        if self._clip_stack:
            self._canvas.set_clip(self._clip_stack.pop())

    # --- 其它 ---------------------------------------------------------
    def capture(self, path: Path) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(self._canvas, str(path))
            return True
        except Exception:  # pragma: no cover
            log.exception("截图失败：%s", path)
            return False

    def shutdown(self) -> None:
        pygame.quit()
