"""过场与遮罩：淡入淡出、闪白、黑屏、天气渐变遮罩。

时长默认值来自 data/config.json 的 transitions 段（0.6 / 0.5 / 0.15），
与 整体风格与UI/SKILL.md 第 7 节一致。
"""

from __future__ import annotations

from ..core.timeline import clamp01, easing
from ..core.types import Color, Rect, mix
from ..render.renderer import Renderer, Texture
from .panels import build_vertical_gradient


class Fade:
    """单向渐变遮罩（黑屏淡入 / 淡出 / 定格黑）。"""

    def __init__(self, renderer: Renderer, color: Color, start_alpha: int, end_alpha: int,
                 duration: float, ease: str = "linear") -> None:
        self.color = color
        self.start_alpha = max(0, min(255, int(start_alpha)))
        self.end_alpha = max(0, min(255, int(end_alpha)))
        self.duration = max(0.0, float(duration))
        self._ease = easing(ease)
        self._elapsed = 0.0
        self._done = self.duration <= 0.0
        self._renderer = renderer

    @property
    def done(self) -> bool:
        return self._done

    @property
    def alpha(self) -> int:
        if self.duration <= 0.0:
            return self.end_alpha
        t = self._ease(clamp01(self._elapsed / self.duration))
        return int(self.start_alpha + (self.end_alpha - self.start_alpha) * t)

    def update(self, dt: float) -> bool:
        if self._done:
            return True
        self._elapsed += dt
        if self._elapsed >= self.duration:
            self._elapsed = self.duration
            self._done = True
        return self._done

    def finish(self) -> None:
        self._elapsed = self.duration
        self._done = True

    def draw(self) -> None:
        alpha = self.alpha
        if alpha <= 0:
            return
        self._renderer.draw_rect(Rect(0, 0, self._renderer.width, self._renderer.height),
                                 self.color, alpha=alpha)


class Flash:
    """闪白：0 → 255 → 0，总时长即 duration（默认 0.15s）。"""

    def __init__(self, renderer: Renderer, color: Color, duration: float = 0.15) -> None:
        self._renderer = renderer
        self.color = color
        self.duration = max(0.001, float(duration))
        self._elapsed = 0.0
        self._done = False

    @property
    def done(self) -> bool:
        return self._done

    @property
    def alpha(self) -> int:
        t = clamp01(self._elapsed / self.duration)
        shape = 1.0 - abs(2.0 * t - 1.0)  # 三角波
        return int(255 * shape)

    def update(self, dt: float) -> bool:
        if self._done:
            return True
        self._elapsed += dt
        if self._elapsed >= self.duration:
            self._done = True
        return self._done

    def finish(self) -> None:
        self._done = True

    def draw(self) -> None:
        alpha = self.alpha
        if alpha <= 0:
            return
        self._renderer.draw_rect(Rect(0, 0, self._renderer.width, self._renderer.height),
                                 self.color, alpha=alpha)


class GradientMask:
    """天气渐变遮罩：不换背景图，只用一层可调的冷色渐变把“晴”压成“阴”。"""

    def __init__(self, renderer: Renderer, top: Color, bottom: Color,
                 top_alpha: int, bottom_alpha: int, duration: float = 0.0,
                 ease: str = "out") -> None:
        self._renderer = renderer
        self.duration = max(0.0, float(duration))
        self._ease = easing(ease)
        self._elapsed = 0.0
        self._strength = 0.0 if self.duration > 0 else 1.0
        self._done = self.duration <= 0.0
        self._texture: Texture = build_vertical_gradient(
            renderer, top, bottom, top_alpha, bottom_alpha, height=renderer.height
        )

    @property
    def done(self) -> bool:
        return self._done

    @property
    def strength(self) -> float:
        return self._strength

    def set_strength(self, value: float) -> None:
        self._strength = clamp01(value)
        self._done = True

    def update(self, dt: float) -> bool:
        if self._done:
            return True
        self._elapsed += dt
        t = clamp01(self._elapsed / self.duration)
        self._strength = self._ease(t)
        if self._elapsed >= self.duration:
            self._done = True
        return self._done

    def finish(self) -> None:
        self._strength = 1.0
        self._done = True

    def draw(self) -> None:
        if self._strength <= 0.001:
            return
        self._renderer.draw_texture(
            self._texture,
            Rect(0, 0, self._renderer.width, self._renderer.height),
            alpha=int(255 * self._strength),
        )


def make_fade_in(renderer: Renderer, color: Color, duration: float) -> Fade:
    return Fade(renderer, color, 255, 0, duration)


def make_fade_out(renderer: Renderer, color: Color, duration: float) -> Fade:
    return Fade(renderer, color, 0, 255, duration)


def lerp_color(a: Color, b: Color, t: float) -> Color:
    return mix(a, b, t)
