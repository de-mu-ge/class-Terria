"""任务卡与操作提示。

Scene 07 结束于「显示初始任务」：寻找失散的伙伴 / 当前角色 / 当前地点 / 同行伙伴。
文案全部来自 data/scenes.json 的 task 指令。
"""

from __future__ import annotations

from ..core.context import SceneContext
from ..core.types import Rect, dim
from .panels import draw_plain_panel
from .text_layout import wrap_text


class TaskPanel:
    def __init__(self, ctx: SceneContext) -> None:
        self._ctx = ctx
        cfg = ctx.config
        self._panel = cfg.rect("task", "panel")
        self._padding = cfg.number("task", "padding", default=14.0)
        self._title_lh = cfg.number("task", "title_line_height", default=26.0)
        self._line_lh = cfg.number("task", "line_height", default=22.0)
        self._font_title = ctx.resources.font("task_title")
        self._font = ctx.resources.font("task")
        self._title = ""
        self._rows: list[tuple[str, str]] = []
        self._alpha = 0.0
        self._target = 0.0
        self._slide = 0.0

    @property
    def visible(self) -> bool:
        return self._target > 0.0

    def show(self, title: str, rows: list[tuple[str, str]]) -> None:
        self._title = title
        self._rows = list(rows)
        self._target = 1.0

    def hide(self) -> None:
        self._target = 0.0

    def update(self, dt: float) -> None:
        speed = 3.0
        if self._alpha < self._target:
            self._alpha = min(self._target, self._alpha + dt * speed)
        elif self._alpha > self._target:
            self._alpha = max(self._target, self._alpha - dt * speed)
        self._slide = (1.0 - self._alpha) * 12.0

    def draw(self) -> None:
        if self._alpha <= 0.01:
            return
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        alpha = int(255 * self._alpha)
        panel = Rect(self._panel.x + self._slide, self._panel.y, self._panel.w, self._panel.h)
        draw_plain_panel(renderer, panel, cfg.color("dialog_bg"),
                         int(cfg.alpha("task_bg") * self._alpha),
                         border=dim(cfg.color("dialog_border"), 0.85), border_width=1)
        renderer.draw_rect(Rect(panel.x, panel.y, 3, panel.h), cfg.color("dialog_border"), alpha=alpha)

        y = panel.y + self._padding
        renderer.draw_text(self._title, (panel.x + self._padding, y),
                           self._font_title, cfg.color("warm_core"), alpha=alpha)
        y += self._title_lh
        renderer.draw_line((panel.x + self._padding, y - 6), (panel.right - self._padding, y - 6),
                           dim(cfg.color("dialog_border"), 0.6), width=1, alpha=int(alpha * 0.8))

        inner_width = int(panel.w - self._padding * 2)
        for label, value in self._rows:
            line = f"{label}：{value}" if label else value
            for part in wrap_text(lambda t: renderer.measure_text(t, self._font)[0], line, inner_width):
                renderer.draw_text(part, (panel.x + self._padding, y), self._font,
                                   cfg.color("text"), alpha=alpha)
                y += self._line_lh


class HintPanel:
    """操作提示（Scene 07 交接控制权时短暂显示）。"""

    def __init__(self, ctx: SceneContext) -> None:
        self._ctx = ctx
        cfg = ctx.config
        self._panel = cfg.rect("hint", "panel")
        self._line_lh = cfg.number("hint", "line_height", default=20.0)
        self._font_title = ctx.resources.font("task_title")
        self._font = ctx.resources.font("hint")
        self._title = ""
        self._lines: list[str] = []
        self._alpha = 0.0
        self._target = 0.0

    @property
    def visible(self) -> bool:
        return self._target > 0.0

    def show(self, title: str, lines: list[str]) -> None:
        self._title = title
        self._lines = list(lines)
        self._target = 1.0

    def hide(self) -> None:
        self._target = 0.0

    def update(self, dt: float) -> None:
        if self._alpha < self._target:
            self._alpha = min(self._target, self._alpha + dt * 3.0)
        elif self._alpha > self._target:
            self._alpha = max(self._target, self._alpha - dt * 3.0)

    def draw(self) -> None:
        if self._alpha <= 0.01:
            return
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        alpha = int(255 * self._alpha)
        panel = self._panel
        draw_plain_panel(renderer, panel, cfg.color("dialog_bg"),
                         int(cfg.alpha("hint_bg") * self._alpha),
                         border=dim(cfg.color("dialog_border"), 0.6), border_width=1)
        y = panel.y + 8
        if self._title:
            renderer.draw_text(self._title, (panel.x + 12, y), self._font_title,
                               cfg.color("cold_white"), alpha=alpha)
            y += self._line_lh
        for line in self._lines:
            renderer.draw_text(line, (panel.x + 12, y), self._font,
                               cfg.color("text"), alpha=alpha)
            y += self._line_lh
