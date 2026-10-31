"""Galgame 对话框：面板 + 名字条 + 打字机 + 已读标记。

数值全部来自 data/config.json 的 dialogue 段（与整体风格与UI/SKILL.md 第 5 节一致）：
面板 36–924 × 393–516，名字条 180×39 @ y=363，外框 2px 暖金，正文 18px / 行高 27，40 字/秒。
"""

from __future__ import annotations

import logging
from typing import Callable

from ..core.context import SceneContext
from ..core.events import InputEvent, InputKind
from ..core.state_machine import StateMachine
from ..data.models import DialogueBlock, Line
from .panels import draw_panel
from .text_layout import slice_visible, wrap_text

log = logging.getLogger(__name__)

_PHASES = ("idle", "typing", "hold", "wait", "auto", "done")


class DialogueView:
    def __init__(
        self,
        ctx: SceneContext,
        on_line: Callable[[Line], None] | None = None,
    ) -> None:
        self._ctx = ctx
        cfg = ctx.config
        self._panel = cfg.rect("dialogue", "panel")
        self._name_bar = cfg.rect("dialogue", "name_bar")
        pad = cfg.section("dialogue").get("padding", {})
        self._pad_left = float(pad.get("left", 18))
        self._pad_top = float(pad.get("top", 15))
        self._chars_per_second = cfg.number("dialogue", "chars_per_second", default=40.0)
        self._blink_hz = cfg.number("dialogue", "indicator_blink_hz", default=1.5)
        self._name_padding = cfg.number("dialogue", "name_padding", default=12.0)
        self._border = int(cfg.number("dialogue", "border_outer", default=2))
        self._line_height = cfg.number("fonts", "line_height", "dialogue", default=27.0)
        self._hint = cfg.text("ui_text", "dialogue_hint", default="")
        self._skip_hint = cfg.text("ui_text", "skip_hint", default="")
        self._on_line = on_line
        self._block: DialogueBlock | None = None
        self._line: Line | None = None
        self._index = -1
        self._typed = 0.0
        self._hold_left = 0.0
        self._auto_left = 0.0
        self._ff_timer = 0.0
        self._line_was_read = False
        self._alpha = 0.0
        self._fading_out = False
        self._finished = False
        self._sm = StateMachine("dialogue", "idle", _PHASES)
        self._fonts = {
            "body": ctx.resources.font("dialogue"),
            "name": ctx.resources.font("name"),
        }
        self._width = self._panel.w - self._pad_left * 2
        self._measure = lambda text: ctx.renderer.measure_text(text, self._fonts["body"])[0]

    # --- 生命周期 -----------------------------------------------------
    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def active(self) -> bool:
        return self._block is not None and not self._finished

    @property
    def closed(self) -> bool:
        """整段台词结束且淡出完毕。"""
        return self._finished and self._block is None

    @property
    def typing(self) -> bool:
        return self._sm.state == "typing"

    @property
    def waiting(self) -> bool:
        return self._sm.state in ("wait", "auto")

    @property
    def current_line(self) -> Line | None:
        return self._line

    def start(self, block: DialogueBlock) -> None:
        self._block = block
        self._index = -1
        self._finished = False
        self._fading_out = False
        self._alpha = 0.0
        self._sm.transition("typing", force=True)
        self._advance_line()

    def stop(self) -> None:
        self._fading_out = True

    def hide_immediately(self) -> None:
        self._alpha = 0.0
        self._block = None
        self._line = None
        self._finished = True
        self._sm.transition("done", force=True)

    # --- 内部推进 -----------------------------------------------------
    def _advance_line(self) -> None:
        assert self._block is not None
        self._index += 1
        if self._index >= len(self._block.lines):
            self._line = None
            self._finished = True
            self._fading_out = True
            self._sm.transition("done")
            return
        line = self._block.lines[self._index]
        self._line = line
        self._line_was_read = self._ctx.state.is_read(line.id)
        self._typed = 0.0
        self._hold_left = line.pause
        self._auto_left = line.wait
        self._ff_timer = 0.0
        self._sm.transition("typing", force=True)
        self._ctx.state.mark_read(line.id)
        if self._on_line:
            try:
                self._on_line(line)
            except Exception:  # pragma: no cover - 演出回调不允许打断对话
                log.exception("对话行回调出错：%s", line.id)

    def _after_typing(self) -> None:
        line = self._line
        if line is None:
            return
        if line.pause > 0.0:
            self._hold_left = line.pause
            self._sm.transition("hold")
        elif line.wait > 0.0:
            self._auto_left = line.wait
            self._sm.transition("auto")
        else:
            self._sm.transition("wait")

    def _enter_waiting(self) -> None:
        line = self._line
        if line is not None and line.wait > 0.0:
            self._auto_left = line.wait
            self._sm.transition("auto")
        else:
            self._sm.transition("wait")

    def advance(self) -> None:
        """玩家点击 / 按键推进。"""
        if self._finished or self._line is None:
            return
        phase = self._sm.state
        if phase == "typing":
            self._typed = float(len(self._line.text))
            self._after_typing()
        elif phase == "hold":
            self._hold_left = 0.0
            self._enter_waiting()
        elif phase in ("wait", "auto"):
            self._advance_line()

    # --- 每帧 ---------------------------------------------------------
    def update(self, dt: float, fast_forward: bool = False) -> None:
        self._sm.update(dt)
        if self._block is None:
            return
        fade_speed = 6.0
        if self._fading_out:
            self._alpha = max(0.0, self._alpha - dt * fade_speed)
            if self._alpha <= 0.0 and self._finished:
                self._block = None
            return
        self._alpha = min(1.0, self._alpha + dt * fade_speed)

        if self._line is None:
            return
        phase = self._sm.state
        speed_factor = 8.0 if fast_forward else 1.0
        if phase == "typing":
            self._typed += self._chars_per_second * speed_factor * dt
            if self._typed >= len(self._line.text):
                self._typed = float(len(self._line.text))
                self._after_typing()
        elif phase == "hold":
            self._hold_left -= dt * speed_factor
            if self._hold_left <= 0.0:
                self._enter_waiting()
        elif phase == "auto":
            self._auto_left -= dt * speed_factor
            if self._auto_left <= 0.0 or fast_forward:
                self._advance_line()
        elif phase == "wait" and fast_forward:
            # 按住 Ctrl：连“等待点击”的行也自动翻页，实现整段快进
            self._ff_timer += dt
            if self._ff_timer >= 0.08:
                self._ff_timer = 0.0
                self._advance_line()

    # --- 输入 ---------------------------------------------------------
    def handle_event(self, event: InputEvent) -> bool:
        if not self.active or self._line is None:
            return False
        if event.kind in (InputKind.ADVANCE, InputKind.CLICK, InputKind.CONFIRM):
            self.advance()
            return True
        return False

    # --- 绘制 ---------------------------------------------------------
    def draw(self) -> None:
        if self._alpha <= 0.0 or self._block is None or self._line is None:
            return
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        alpha = int(255 * self._alpha)
        bg = cfg.color("dialog_bg")
        border = cfg.color("dialog_border")
        draw_panel(
            renderer,
            self._panel,
            bg,
            int(cfg.alpha("dialog_bg") * self._alpha),
            border,
            outer_width=self._border,
        )

        line = self._line
        character = self._character(line.speaker)
        self._draw_name_bar(character, alpha)

        font = self._fonts["body"]
        text = line.text
        visible = slice_visible(text, self._typed)
        wrapped_full = wrap_text(self._measure, text, int(self._width))
        wrapped_visible = wrap_text(self._measure, visible, int(self._width))
        read = self._line_was_read and self._typed >= len(text)
        text_color = cfg.color("text_dim") if read else cfg.color("text")
        x = self._panel.x + self._pad_left
        y = self._panel.y + self._pad_top
        for row in range(len(wrapped_full)):
            if row >= len(wrapped_visible):
                break
            renderer.draw_text(wrapped_visible[row], (x, y + row * self._line_height), font,
                               text_color, alpha=alpha)

        if self._sm.state == "wait":
            self._draw_indicator(alpha)

    def _character(self, speaker: str):
        try:
            return self._ctx.data.character(speaker)
        except Exception:
            return None

    def _draw_name_bar(self, character, alpha: int) -> None:
        if character is None:
            return
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        bar = self._name_bar
        draw_panel(renderer, bar, cfg.color("dialog_bg"),
                   int(cfg.alpha("dialog_bg") * self._alpha),
                   cfg.color("dialog_border"), outer_width=self._border)
        font = self._fonts["name"]
        text_height = renderer.measure_text(character.name, font)[1]
        renderer.draw_text(
            character.name,
            (bar.x + self._name_padding, bar.centery - text_height / 2),
            font,
            character.color,
            alpha=alpha,
        )

    def _draw_indicator(self, alpha: int) -> None:
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        phase = (self._sm.elapsed * self._blink_hz) % 1.0
        if phase > 0.55:
            return
        color = cfg.color("dialog_border")
        x = self._panel.right - 22
        y = self._panel.bottom - 18
        renderer.draw_polygon([(x, y), (x + 10, y), (x + 5, y + 7)], color, alpha=alpha)

    def _draw_hint(self, text: str, alpha: int) -> None:
        if not text:
            return
        renderer = self._ctx.renderer
        font = self._ctx.resources.font("menu_small")
        text_width, text_height = renderer.measure_text(text, font)
        renderer.draw_text(
            text,
            (self._panel.right - text_width - 12, self._panel.bottom - text_height - 6),
            font,
            self._ctx.config.color("text_dim"),
            alpha=int(alpha * 0.65),
        )
