"""设置界面：本轮只有音量（整体风格与UI 与 epoch 提示词一致）。"""

from __future__ import annotations

from ..core.context import SceneContext
from ..core.events import InputEvent, InputKind
from ..core.scene import Scene
from ..ui.menu import Slider
from ..ui.panels import draw_plain_panel


class SettingsScene(Scene):
    scene_id = "settings"

    def __init__(self, ctx: SceneContext) -> None:
        super().__init__(ctx)
        cfg = ctx.config
        self._panel = cfg.rect("settings", "panel")
        self._slider_rect = cfg.rect("settings", "slider").move(self._panel.x, self._panel.y)
        self._line_height = cfg.number("settings", "line_height", default=24)
        self._title = cfg.text("ui_text", "settings_title", default="设置")
        self._volume_label = cfg.text("ui_text", "settings_volume", default="音量")
        self._hint = cfg.text("ui_text", "settings_hint", default="")
        self._font_title = ctx.resources.font("confirm")
        self._font = ctx.resources.font("menu_small")
        self._slider = Slider(ctx, self._slider_rect, ctx.state.master_volume, self._volume_label)

    def enter(self) -> None:
        self.ctx.state.current_scene_id = "settings"

    def handle_event(self, event: InputEvent) -> None:
        if event.kind == InputKind.CANCEL:
            self.ctx.audio.play_sfx("ui_cancel")
            self.ctx.router.back_to_title()
            return
        self._slider.handle_event(event)
        self.ctx.state.master_volume = self._slider.value

    def draw(self) -> None:
        renderer = self.ctx.renderer
        cfg = self.ctx.config
        renderer.clear(cfg.color("void"))
        panel = self._panel
        draw_plain_panel(renderer, panel, cfg.color("dialog_bg"),
                         cfg.alpha("panel_bg"),
                         border=cfg.color("dialog_border"), border_width=2)
        renderer.draw_text(self._title, (panel.centerx, panel.y + 24),
                           self._font_title, cfg.color("text"), align="center")
        self._slider.draw()
        if self._hint:
            renderer.draw_text(self._hint, (panel.centerx, panel.bottom - 40),
                               self._font, cfg.color("text_dim"), align="center")
