"""菜单、确认框、音量滑条。

选中态：文字前加「▸」+ 1px 暖金下划线，不使用发光（整体风格与UI/SKILL.md 第 6 节）。
"""

from __future__ import annotations

from typing import Any, Sequence

from ..core.context import SceneContext
from ..core.events import InputEvent, InputKind
from ..core.types import Rect, dim
from .panels import draw_plain_panel


class MenuList:
    def __init__(
        self,
        ctx: SceneContext,
        items: Sequence[dict[str, Any]],
        origin: tuple[float, float],
        line_spacing: float,
        font_role: str = "menu",
    ) -> None:
        self._ctx = ctx
        self._items = list(items)
        self._origin = origin
        self._spacing = line_spacing
        self._font = ctx.resources.font(font_role)
        self._font_small = ctx.resources.font("menu_small")
        self._selected = self._first_enabled()

    # --- 状态 ---------------------------------------------------------
    def _first_enabled(self) -> int:
        for index, item in enumerate(self._items):
            if item.get("enabled", True):
                return index
        return 0

    @property
    def selected_id(self) -> str | None:
        if 0 <= self._selected < len(self._items):
            return str(self._items[self._selected].get("id"))
        return None

    def _move(self, delta: int) -> None:
        count = len(self._items)
        if count == 0:
            return
        index = self._selected
        for _ in range(count):
            index = (index + delta) % count
            if self._items[index].get("enabled", True):
                self._selected = index
                return

    # --- 输入 ---------------------------------------------------------
    def handle_event(self, event: InputEvent) -> str | None:
        """返回被选中的菜单 id（未触发则 None）。"""
        if event.kind == InputKind.MENU_UP:
            self._move(-1)
            self._ctx.audio.play_sfx("ui_click")
        elif event.kind == InputKind.MENU_DOWN:
            self._move(1)
            self._ctx.audio.play_sfx("ui_click")
        elif event.kind in (InputKind.CONFIRM, InputKind.ADVANCE):
            item = self._items[self._selected]
            if item.get("enabled", True):
                self._ctx.audio.play_sfx("ui_confirm")
                return str(item.get("id"))
            self._ctx.audio.play_sfx("ui_cancel")
        elif event.kind == InputKind.CLICK and event.pos:
            for index, item in enumerate(self._items):
                if self._item_rect(index).contains(*event.pos):
                    self._selected = index
                    if item.get("enabled", True):
                        self._ctx.audio.play_sfx("ui_confirm")
                        return str(item.get("id"))
                    self._ctx.audio.play_sfx("ui_cancel")
        return None

    # --- 绘制 ---------------------------------------------------------
    def _item_rect(self, index: int) -> Rect:
        height = 28.0
        return Rect(self._origin[0] - 8, self._origin[1] + index * self._spacing - 4, 260, height)

    def draw(self) -> None:
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        disabled_hint = cfg.text("ui_text", "menu_disabled_hint", default="")
        for index, item in enumerate(self._items):
            enabled = bool(item.get("enabled", True))
            selected = index == self._selected
            x = self._origin[0]
            y = self._origin[1] + index * self._spacing
            label = str(item.get("label", ""))
            color = cfg.color("text") if enabled else dim(cfg.color("text_dim"), 0.7)
            if not enabled:
                color = dim(color, 0.8)
            if selected:
                # 用三角形代替「▸」字符：当前可用字体（simsun/msyh）里 ▸ 字宽为 0
                renderer.draw_polygon(
                    [(x - 16, y + 6), (x - 16, y + 18), (x - 7, y + 12)],
                    cfg.color("warm_core"),
                )
                width = renderer.measure_text(label, self._font)[0]
                renderer.draw_line((x, y + 25), (x + width, y + 25),
                                   cfg.color("dialog_border"), width=1)
            if not enabled and disabled_hint and selected:
                renderer.draw_text(disabled_hint, (x + 250, y + 4), self._font_small,
                                   dim(cfg.color("text_dim"), 0.8))
            renderer.draw_text(label, (x, y), self._font, color)


class ConfirmDialog:
    def __init__(self, ctx: SceneContext, title: str, body: str, yes: str, no: str) -> None:
        self._ctx = ctx
        screen_w, screen_h = ctx.renderer.size
        self._panel = Rect.from_center(screen_w / 2, screen_h / 2, 380, 168)
        self._title = title
        self._body = body
        self._yes = yes
        self._no = no
        self._font_title = ctx.resources.font("confirm")
        self._font = ctx.resources.font("menu_small")
        self._selected = 0  # 0 = 否，1 = 是（默认不误触）
        self._result: str | None = None

    @property
    def active(self) -> bool:
        return self._result is None

    @property
    def result(self) -> str | None:
        return self._result

    def _buttons(self) -> list[Rect]:
        base = Rect(self._panel.x + 24, self._panel.bottom - 54, 150, 34)
        return [base, Rect(self._panel.right - 24 - 150, base.y, 150, 34)]

    def handle_event(self, event: InputEvent) -> None:
        if self._result is not None:
            return
        if event.kind in (InputKind.MENU_LEFT, InputKind.MENU_RIGHT):
            self._selected = 1 - self._selected
            self._ctx.audio.play_sfx("ui_click")
        elif event.kind in (InputKind.CONFIRM, InputKind.ADVANCE):
            self._result = "yes" if self._selected == 1 else "no"
            self._ctx.audio.play_sfx("ui_confirm" if self._result == "yes" else "ui_cancel")
        elif event.kind == InputKind.CANCEL:
            self._result = "no"
            self._ctx.audio.play_sfx("ui_cancel")
        elif event.kind == InputKind.CLICK and event.pos:
            for index, rect in enumerate(self._buttons()):
                if rect.contains(*event.pos):
                    self._selected = index
                    self._result = "yes" if index == 1 else "no"
                    self._ctx.audio.play_sfx("ui_confirm" if self._result == "yes" else "ui_cancel")

    def draw(self) -> None:
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        renderer.draw_rect(Rect(0, 0, renderer.width, renderer.height),
                           cfg.color("void"), alpha=150)
        draw_plain_panel(renderer, self._panel, cfg.color("dialog_bg"),
                         int(cfg.alpha("panel_bg") * 255),
                         border=cfg.color("dialog_border"), border_width=2)
        renderer.draw_text(self._title, (self._panel.centerx, self._panel.y + 26),
                           self._font_title, cfg.color("text"), align="center")
        if self._body:
            renderer.draw_text(self._body, (self._panel.centerx, self._panel.y + 66),
                               self._font, cfg.color("text_dim"), align="center")
        for index, rect in enumerate(self._buttons()):
            selected = index == self._selected
            label = self._no if index == 0 else self._yes
            draw_plain_panel(renderer, rect, cfg.color("mid") if selected else cfg.color("dark"),
                             235, border=cfg.color("dialog_border") if selected else dim(cfg.color("dialog_border"), 0.5),
                             border_width=2 if selected else 1)
            renderer.draw_text(label, (rect.centerx, rect.centery - 11), self._font,
                               cfg.color("text") if selected else cfg.color("text_dim"),
                               align="center")


class Slider:
    def __init__(self, ctx: SceneContext, rect: Rect, value: float, label: str) -> None:
        self._ctx = ctx
        self._rect = rect
        self._value = max(0.0, min(1.0, value))
        self._label = label
        self._font = ctx.resources.font("confirm")
        self._font_small = ctx.resources.font("menu_small")
        self._dragging = False

    @property
    def value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        self._value = max(0.0, min(1.0, value))

    def _apply_x(self, x: float) -> None:
        t = (x - self._rect.x) / max(1.0, self._rect.w)
        self.set_value(t)

    def handle_event(self, event: InputEvent) -> bool:
        changed = False
        if event.kind in (InputKind.MENU_LEFT,):
            self.set_value(self._value - 0.1)
            changed = True
        elif event.kind in (InputKind.MENU_RIGHT,):
            self.set_value(self._value + 0.1)
            changed = True
        elif event.kind == InputKind.CLICK and event.pos:
            track = Rect(self._rect.x - 10, self._rect.y - 12, self._rect.w + 20, self._rect.h + 24)
            if track.contains(*event.pos):
                self._apply_x(event.pos[0])
                self._dragging = True
                changed = True
        elif event.kind == InputKind.POINTER and self._dragging and event.pos:
            self._apply_x(event.pos[0])
            changed = True
        if changed:
            self._ctx.audio.set_master_volume(self._value)
        return changed

    def draw(self) -> None:
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        renderer.draw_text(f"{self._label}", (self._rect.x, self._rect.y - 34),
                           self._font, cfg.color("text"))
        renderer.draw_rect(self._rect, cfg.color("dark"), alpha=230)
        filled = Rect(self._rect.x, self._rect.y, self._rect.w * self._value, self._rect.h)
        renderer.draw_rect(filled, cfg.color("warm_mid"), alpha=245)
        renderer.draw_frame(self._rect, cfg.color("dialog_border"), width=1)
        knob = Rect(self._rect.x + self._rect.w * self._value - 6, self._rect.y - 6, 12, self._rect.h + 12)
        renderer.draw_rect(knob, cfg.color("cream"))
        percent = f"{int(round(self._value * 100))}%"
        renderer.draw_text(percent, (self._rect.right + 16, self._rect.y - 4),
                           self._font_small, cfg.color("text_dim"))
