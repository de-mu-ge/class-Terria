"""HUD：生命 / 体温两条横条 + 底部快捷栏，以及右上角信号图标。

数值来自 data/config.json 的 hud / signal 段（本轮按 epoch 提示词给的 288×18、8 格 ×96）。
HUD 只在未知世界（Scene 07 及之后）出现。
"""

from __future__ import annotations

from ..core.context import SceneContext
from ..core.types import Color, Rect, dim
from ..render.renderer import Renderer


class Hud:
    def __init__(self, ctx: SceneContext) -> None:
        self._ctx = ctx
        cfg = ctx.config
        self._life_rect = cfg.rect("hud", "life_bar")
        self._temp_rect = cfg.rect("hud", "temp_bar")
        hotbar = cfg.section("hud").get("hotbar", {})
        self._slots = int(hotbar.get("slots", 8))
        self._slot_size = float(hotbar.get("slot_size", 96))
        self._slot_y = float(hotbar.get("y", 432))
        self._gap = float(hotbar.get("gap", 2))
        self._lift = float(hotbar.get("selected_lift", 2))
        self._filled = int(hotbar.get("filled", 1))
        self._selected = 0
        self._visible = False
        self._alpha = 0.0
        self._life = 1.0
        self._temp = 1.0
        self._font = ctx.resources.font("hud")
        self._font_small = ctx.resources.font("menu_small")
        self._life_label = cfg.text("ui_text", "life_label", default="")
        self._temp_label = cfg.text("ui_text", "temp_label", default="")

    # --- 控制 ---------------------------------------------------------
    @property
    def visible(self) -> bool:
        return self._visible

    def show(self) -> None:
        self._visible = True

    def hide(self) -> None:
        self._visible = False

    def set_values(self, life: float | None = None, temp: float | None = None) -> None:
        if life is not None:
            self._life = max(0.0, min(1.0, life))
        if temp is not None:
            self._temp = max(0.0, min(1.0, temp))

    def set_selected(self, index: int) -> None:
        self._selected = max(0, min(self._slots - 1, index))

    def update(self, dt: float) -> None:
        target = 1.0 if self._visible else 0.0
        speed = 3.0
        if self._alpha < target:
            self._alpha = min(target, self._alpha + dt * speed)
        elif self._alpha > target:
            self._alpha = max(target, self._alpha - dt * speed)

    # --- 绘制 ---------------------------------------------------------
    def draw(self) -> None:
        if self._alpha <= 0.01:
            return
        alpha = int(255 * self._alpha)
        cfg = self._ctx.config
        renderer = self._ctx.renderer

        self._draw_bar(renderer, self._life_rect, self._life, cfg.color("hud_life"),
                       self._life_label, alpha)
        self._draw_bar(renderer, self._temp_rect, self._temp, cfg.color("hud_temp"),
                       self._temp_label, alpha)
        self._draw_hotbar(renderer, alpha)

    def _draw_bar(self, renderer: Renderer, rect: Rect, value: float, color: Color,
                  label: str, alpha: int) -> None:
        cfg = self._ctx.config
        renderer.draw_rect(rect, cfg.color("void"), alpha=int(220 * self._alpha))
        inner = rect.inset(2, 2)
        width = inner.w * max(0.0, min(1.0, value))
        if width > 0:
            renderer.draw_rect(Rect(inner.x, inner.y, width, inner.h), color, alpha=alpha)
        renderer.draw_frame(rect, cfg.color("hud_frame"), width=1, alpha=alpha)
        if label:
            # 标签画在条内侧左端，避免和上一条重叠
            renderer.draw_text(label, (rect.x + 6, rect.y + 3), self._font,
                               cfg.color("void"), alpha=int(alpha * 0.85))

    def _draw_hotbar(self, renderer: Renderer, alpha: int) -> None:
        cfg = self._ctx.config
        total = self._slots * self._slot_size + (self._slots - 1) * self._gap
        start_x = (renderer.width - total) / 2
        for index in range(self._slots):
            x = start_x + index * (self._slot_size + self._gap)
            lift = self._lift if index == self._selected else 0
            rect = Rect(x, self._slot_y - lift, self._slot_size, self._slot_size)
            renderer.draw_rect(rect, cfg.color("hud_slot"), alpha=int(205 * self._alpha))
            border = cfg.color("hud_frame") if index == self._selected else dim(cfg.color("hud_frame"), 0.45)
            renderer.draw_frame(rect, border, width=2 if index == self._selected else 1, alpha=alpha)
            if index < self._filled:
                # 本轮没有道具图标：用一个小方块表示“已占用”
                marker = Rect(rect.x + rect.w / 2 - 12, rect.y + rect.h / 2 - 12, 24, 24)
                renderer.draw_round_rect(marker, cfg.color("cold"), 3, alpha=int(alpha * 0.8))
                renderer.draw_round_frame(marker, cfg.color("cold_white"), 3, width=1, alpha=alpha)


class SignalWidget:
    """右上角信号图标：在线 / 信号弱 / 无信号。Scene 05 通讯异常时切到无信号。"""

    def __init__(self, ctx: SceneContext) -> None:
        self._ctx = ctx
        cfg = ctx.config
        position = cfg.value("signal", "position", default=[872, 16])
        size = cfg.value("signal", "size", default=[64, 36])
        self._rect = Rect.from_sequence([position[0], position[1], size[0], size[1]])
        self._bars = int(cfg.number("signal", "bars", default=4))
        self._bar_w = max(1, int(cfg.number("signal", "bar_width", default=4)))
        self._bar_gap = max(0, int(cfg.number("signal", "bar_gap", default=2)))
        self._unit = max(1, int(cfg.number("signal", "bar_height_unit", default=4)))
        self._font = ctx.resources.font("hud")
        self._state = "ok"
        self._visible = False
        self._alpha = 0.0
        self._blink = 0.0

    @property
    def state(self) -> str:
        return self._state

    def show(self) -> None:
        self._visible = True

    def hide(self) -> None:
        self._visible = False

    def set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self._blink = 0.0
            self._visible = True

    def update(self, dt: float) -> None:
        target = 1.0 if self._visible else 0.0
        self._alpha += max(-dt * 3.0, min(dt * 3.0, target - self._alpha))
        self._blink += dt

    def draw(self) -> None:
        if self._alpha <= 0.01:
            return
        alpha = int(255 * self._alpha)
        cfg = self._ctx.config
        renderer = self._ctx.renderer
        rect = self._rect
        color = cfg.color("signal_ok") if self._state != "lost" else cfg.color("signal_lost")

        # 底板
        renderer.draw_round_rect(rect, cfg.color("void"), 4, alpha=int(150 * self._alpha))
        base_x = rect.x + 8
        base_y = rect.bottom - 8
        for index in range(self._bars):
            height = self._unit * (index + 1)
            bar = Rect(base_x + index * (self._bar_w + self._bar_gap), base_y - height,
                       self._bar_w, height)
            active = True
            if self._state == "weak" and index >= 2:
                active = False
            if self._state == "lost":
                active = False
            renderer.draw_rect(bar, color if active else dim(color, 0.35),
                               alpha=alpha if active else int(alpha * 0.5))

        if self._state == "lost":
            # 斜杠 + 闪烁，表示通讯中断
            blink = 0.6 + 0.4 * abs((self._blink * 2.0) % 2.0 - 1.0)
            renderer.draw_line((base_x - 2, base_y - 14), (base_x + 22, base_y + 2),
                               color, width=2, alpha=int(alpha * blink))

        label = cfg.text("ui_text", {"ok": "signal_ok", "weak": "signal_weak",
                                     "lost": "signal_lost"}.get(self._state, "signal_ok"),
                         default="")
        if label:
            label_w, label_h = renderer.measure_text(label, self._font)
            renderer.draw_text(label, (rect.right - label_w - 6, rect.y + 4),
                               self._font, color, alpha=alpha)
