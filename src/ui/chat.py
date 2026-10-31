"""手机群聊 UI（独立 UI 层，不画进背景）。

Scene 01 要求：三条消息依次出现、每条带提示音、停留约两秒、然后切回爱音。
所有文案来自 data/scenes.json 的 chat 指令，本文件只负责排版与计时。
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Sequence

from ..core.context import SceneContext
from ..core.types import Rect, dim
from ..render.renderer import Renderer
from .panels import draw_plain_panel
from .text_layout import wrap_text

log = logging.getLogger(__name__)


class ChatView:
    def __init__(self, ctx: SceneContext) -> None:
        self._ctx = ctx
        cfg = ctx.config
        self._frame = cfg.rect("chat", "frame")
        self._header_h = cfg.number("chat", "header_height", default=44.0)
        self._bubble_pad = cfg.number("chat", "bubble_padding", default=10.0)
        self._radius = int(cfg.number("chat", "bubble_radius", default=8))
        self._max_width = cfg.number("chat", "bubble_max_width", default=250.0)
        self._line_height = cfg.number("chat", "line_height", default=20.0)
        self._gap = cfg.number("chat", "message_gap", default=8.0)
        self._fonts = {
            "text": ctx.resources.font("chat"),
            "name": ctx.resources.font("chat_name"),
            "header": ctx.resources.font("chat_header"),
        }
        self._measure = lambda text, font=None: ctx.renderer.measure_text(
            text, font or self._fonts["text"]
        )[0]

        self._active = False
        self._title = ""
        self._messages: list[dict[str, Any]] = []
        self._shown = 0
        self._timer = 0.0
        self._per_message = 0.9
        self._hold = 2.0
        self._alpha = 0.0
        self._fading_out = False
        self._done = False
        self._sound: str | None = "message_ping"
        self._on_message: Callable[[int], None] | None = None

    # --- 生命周期 -----------------------------------------------------
    @property
    def active(self) -> bool:
        return self._active

    @property
    def done(self) -> bool:
        return self._done

    def start(
        self,
        title: str,
        messages: Sequence[dict[str, Any]],
        per_message: float = 0.9,
        hold: float = 2.0,
        sound: str | None = "message_ping",
        on_message: Callable[[int], None] | None = None,
    ) -> None:
        self._active = True
        self._done = False
        self._fading_out = False
        self._title = title
        self._messages = list(messages)
        self._shown = 0
        self._timer = 0.0
        self._per_message = max(0.01, per_message)
        self._hold = max(0.0, hold)
        self._alpha = 0.0
        self._sound = sound
        self._on_message = on_message
        self._emit_next()

    def stop(self) -> None:
        self._fading_out = True

    def fail(self) -> None:
        self._active = False
        self._done = True

    def _emit_next(self) -> None:
        if self._shown < len(self._messages):
            self._shown += 1
            message = self._messages[self._shown - 1]
            sfx = message.get("sfx", self._sound)
            if sfx:
                self._ctx.audio.play_sfx(str(sfx))
            if self._on_message:
                try:
                    self._on_message(self._shown - 1)
                except Exception:  # pragma: no cover
                    log.exception("群聊消息回调出错")

    # --- 每帧 ---------------------------------------------------------
    def update(self, dt: float) -> None:
        if not self._active:
            return
        if self._fading_out:
            self._alpha = max(0.0, self._alpha - dt * 5.0)
            if self._alpha <= 0.0:
                self._active = False
                self._done = True
            return
        self._alpha = min(1.0, self._alpha + dt * 5.0)
        self._timer += dt
        if self._shown < len(self._messages):
            if self._timer >= self._per_message:
                self._timer = 0.0
                self._emit_next()
            return
        # 全部消息出现后停留，再淡出
        if self._timer >= self._hold:
            self._fading_out = True

    # --- 绘制 ---------------------------------------------------------
    def draw(self) -> None:
        if not self._active or self._alpha <= 0.0:
            return
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        alpha = int(255 * self._alpha)
        frame = self._frame

        # 机身
        renderer.draw_round_rect(frame.move(6, 8), cfg.color("black"),
                                 int(self._radius * 2), alpha=int(90 * self._alpha))
        renderer.draw_round_rect(frame, cfg.color("chat_frame"), int(self._radius * 2),
                                 alpha=int(250 * self._alpha))
        renderer.draw_round_frame(frame, dim(cfg.color("dialog_border"), 0.7),
                                  int(self._radius * 2), width=2, alpha=alpha)

        header = Rect(frame.x, frame.y, frame.w, self._header_h)
        renderer.draw_round_rect(header, cfg.color("chat_header"), int(self._radius * 2),
                                 alpha=int(235 * self._alpha))
        renderer.draw_rect(Rect(header.x, header.bottom - 1, header.w, 1),
                           cfg.color("dialog_border"), alpha=int(120 * self._alpha))

        # 标题
        font_header = self._fonts["header"]
        text_w, text_h = renderer.measure_text(self._title, font_header)
        renderer.draw_text(self._title, (header.centerx - text_w / 2,
                                         header.centery - text_h / 2),
                           font_header, cfg.color("text"), alpha=alpha)

        # 消息气泡
        y = self._frame.y + self._header_h + self._gap * 2
        for index in range(self._shown):
            bubble_height = self._draw_message(renderer, self._messages[index], y, alpha)
            y += bubble_height + self._gap

    def _draw_message(self, renderer: Renderer, message: dict[str, Any], y: float,
                      alpha: int) -> float:
        cfg = self._ctx.config
        text = str(message.get("text", ""))
        name = str(message.get("name", ""))
        color = cfg.color("chat_bubble")
        sender_color = cfg.color("cold_white")
        speaker = message.get("from")
        if speaker:
            try:
                character = self._ctx.data.character(str(speaker))
                sender_color = character.color
                if not name:
                    name = character.name
            except Exception:
                pass

        padding = self._bubble_pad
        inner_width = int(self._max_width - padding * 2)
        lines = wrap_text(lambda t: self._measure(t, self._fonts["text"]), text, inner_width)
        text_height = len(lines) * self._line_height
        name_height = 18.0 if name else 0.0
        bubble_w = min(self._max_width, max(
            [self._measure(line, self._fonts["text"]) for line in lines] + [len(name) * 13.0]
        ) + padding * 2)
        bubble_h = padding * 2 + text_height + name_height

        x = self._frame.x + 26
        bubble = Rect(x, y, bubble_w, bubble_h)
        draw_plain_panel(renderer, bubble, color, int(230 * self._alpha),
                         border=dim(sender_color, 0.75), border_width=1,
                         radius=self._radius)

        # 头像点（角色代表色）
        dot = Rect(self._frame.x + 8, y + 6, 10, 10)
        renderer.draw_round_rect(dot, sender_color, 5, alpha=alpha)

        cursor_y = y + padding
        if name:
            renderer.draw_text(name, (bubble.x + padding, cursor_y),
                               self._fonts["name"], sender_color, alpha=int(alpha * 0.95))
            cursor_y += name_height
        for line in lines:
            renderer.draw_text(line, (bubble.x + padding, cursor_y),
                               self._fonts["text"], cfg.color("chat_bubble_text"), alpha=alpha)
            cursor_y += self._line_height
        return bubble_h
