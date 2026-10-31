"""广播字幕条。

Scene 05 要求：广播用「字幕条 + 环境音」表现，不占用对话系统。
默认位置在对话框区域上方，带金色左侧竖条与「船上广播」小标签。
"""

from __future__ import annotations

from ..core.context import SceneContext
from ..core.types import Rect, dim
from .panels import draw_plain_panel
from .text_layout import wrap_text


class SubtitleBar:
    def __init__(self, ctx: SceneContext) -> None:
        self._ctx = ctx
        cfg = ctx.config
        self._bar = cfg.rect("subtitle", "bar")
        self._padding = cfg.number("subtitle", "padding", default=14.0)
        self._label = cfg.text("subtitle", "label", default="")
        self._font = ctx.resources.font("subtitle")
        self._label_font = ctx.resources.font("broadcast_label")
        self._line_height = cfg.number("fonts", "line_height", "subtitle", default=22.0)
        self._text = ""
        self._hold = 0.0
        self._elapsed = 0.0
        self._alpha = 0.0
        self._fading_out = False
        self._visible = False
        self._done = True

    @property
    def visible(self) -> bool:
        return self._visible

    @property
    def done(self) -> bool:
        return self._done

    def show(self, text: str, label: str | None = None, duration: float = 6.0) -> None:
        self._text = text
        if label:
            self._label = label
        self._hold = max(0.2, duration)
        self._elapsed = 0.0
        self._alpha = 0.0
        self._fading_out = False
        self._visible = True
        self._done = False

    def hide(self) -> None:
        if self._visible:
            self._fading_out = True

    def hide_immediately(self) -> None:
        self._visible = False
        self._alpha = 0.0
        self._done = True

    def update(self, dt: float) -> bool:
        if not self._visible:
            return True
        if self._fading_out:
            self._alpha = max(0.0, self._alpha - dt * 4.0)
            if self._alpha <= 0.0:
                self._visible = False
                self._done = True
            return self._done
        self._alpha = min(1.0, self._alpha + dt * 4.0)
        self._elapsed += dt
        if self._elapsed >= self._hold:
            self._fading_out = True
        return False

    def draw(self) -> None:
        if not self._visible or self._alpha <= 0.0 or not self._text:
            return
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        alpha = int(255 * self._alpha)
        bar = self._bar
        draw_plain_panel(renderer, bar, cfg.color("dialog_bg"),
                         int(cfg.alpha("subtitle_bg") * self._alpha),
                         border=dim(cfg.color("dialog_border"), 0.8), border_width=1)

        # 左侧金色竖条
        renderer.draw_rect(Rect(bar.x, bar.y, 3, bar.h), cfg.color("dialog_border"), alpha=alpha)

        # 标签
        label_font = self._label_font
        if self._label:
            label_w, label_h = renderer.measure_text(self._label, label_font)
            renderer.draw_text(self._label,
                               (bar.x + self._padding, bar.y + self._padding * 0.5),
                               label_font, cfg.color("dialog_border"), alpha=alpha)

        inner_width = int(bar.w - self._padding * 2 - 3)
        lines = wrap_text(lambda t: renderer.measure_text(t, self._font)[0],
                          self._text, inner_width)
        text_y = bar.y + self._padding * 0.5 + (
            renderer.measure_text(self._label, label_font)[1] + 2 if self._label else 0
        )
        for index, line in enumerate(lines):
            renderer.draw_text(line, (bar.x + self._padding + 3, text_y + index * self._line_height),
                               self._font, cfg.color("text"), alpha=alpha)
