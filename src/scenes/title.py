"""开始界面。

整体风格与UI/SKILL.md 第 6 / 8 节：开始界面属于「游戏外」，统一用像素语言 ——
像素海岸背景 + 暗角 + 左侧标题区 + 菜单列 + 右下角版本号。
"""

from __future__ import annotations

import logging

from ..core.context import SceneContext
from ..core.events import InputEvent
from ..core.scene import Scene
from ..core.types import Rect, dim
from ..ui.menu import MenuList
from ..ui.panels import build_horizontal_gradient, build_vertical_gradient

log = logging.getLogger(__name__)


class TitleScene(Scene):
    scene_id = "title"

    def __init__(self, ctx: SceneContext) -> None:
        super().__init__(ctx)
        cfg = ctx.config
        section = cfg.section("title_screen")
        self._menu_origin = section.get("menu_origin", [72, 306])
        self._menu_spacing = float(section.get("menu_line_spacing", 24))
        self._title_origin = section.get("title_origin", [72, 176])
        self._sub_origin = section.get("title_sub_origin", [76, 232])
        self._underline_width = float(section.get("title_underline_width", 260))
        self._underline_gap = float(section.get("underline_gap", 30))
        vignette = section.get("vignette", {}) or {}
        self._vig_top = float(vignette.get("top", 120))
        self._vig_bottom = float(vignette.get("bottom", 120))
        self._vig_left = float(vignette.get("left", 200))
        self._vig_right = float(vignette.get("right", 200))
        self._dim_alpha = cfg.alpha("menu_dim", default=0.62)
        self._title = cfg.text("meta", "title", default="")
        self._subtitle = cfg.text("meta", "subtitle", default="")
        self._version_prefix = cfg.text("ui_text", "version_prefix", default="v")
        self._version = cfg.text("meta", "version", default="0.1")
        version_margin = section.get("version_margin", [18, 16])
        self._version_margin = (float(version_margin[0]), float(version_margin[1]))
        self._font_title = ctx.resources.font("title")
        self._font_sub = ctx.resources.font("title_sub")
        self._font_version = ctx.resources.font("version")

        items = cfg.ui_text("menu", default=[])
        self._menu = MenuList(ctx, items, (self._menu_origin[0], self._menu_origin[1]),
                              self._menu_spacing, font_role="menu")

        self._bg = None
        bg_name = str(section.get("background", ""))
        if bg_name:
            self._bg = ctx.resources.texture_or_none(ctx.paths.background(bg_name))
        self._elapsed = 0.0
        self._vignette_top = None
        self._vignette_bottom = None
        self._vignette_left = None
        self._vignette_right = None

    # --- 生命周期 -----------------------------------------------------
    def enter(self) -> None:
        self.ctx.state.current_scene_id = "title"
        self._build_vignette()
        self.ctx.audio.stop_all()
        cfg_volume = self.ctx.state.master_volume
        self.ctx.audio.set_master_volume(cfg_volume)

    def _build_vignette(self) -> None:
        if self._vignette_top is not None:
            return
        renderer = self.ctx.renderer
        void = self.ctx.config.color("void")
        self._vignette_top = build_vertical_gradient(renderer, void, void, 190, 0, int(self._vig_top))
        self._vignette_bottom = build_vertical_gradient(renderer, void, void, 0, 210, int(self._vig_bottom))
        self._vignette_left = build_horizontal_gradient(renderer, void, void, 150, 0, int(self._vig_left))
        self._vignette_right = build_horizontal_gradient(renderer, void, void, 0, 120, int(self._vig_right))

    # --- 输入 ---------------------------------------------------------
    def handle_event(self, event: InputEvent) -> None:
        action = self._menu.handle_event(event)
        if action == "start":
            self.ctx.state.reset_progress()
            self.ctx.router.start_scene("s01")
        elif action == "settings":
            self.ctx.router.open_settings()
        elif action == "quit":
            self.ctx.router.quit_game()

    # --- 每帧 ---------------------------------------------------------
    def update(self, dt: float) -> None:
        self._elapsed += dt

    # --- 绘制 ---------------------------------------------------------
    def draw(self) -> None:
        renderer = self.ctx.renderer
        cfg = self.ctx.config
        renderer.clear(cfg.color("void"))
        if self._bg is not None:
            renderer.draw_texture(self._bg, Rect(0, 0, *renderer.size), smooth=False)
        renderer.draw_rect(Rect(0, 0, *renderer.size), cfg.color("void"),
                           alpha=int(self._dim_alpha))

        # 暗角
        width, height = renderer.size
        if self._vignette_top is not None:
            renderer.draw_texture(self._vignette_top, Rect(0, 0, width, self._vig_top))
            renderer.draw_texture(self._vignette_bottom,
                                  Rect(0, height - self._vig_bottom, width, self._vig_bottom))
            renderer.draw_texture(self._vignette_left, Rect(0, 0, self._vig_left, height))
            renderer.draw_texture(self._vignette_right,
                                  Rect(width - self._vig_right, 0, self._vig_right, height))

        # 标题
        renderer.draw_text(self._title, (self._title_origin[0], self._title_origin[1]),
                           self._font_title, cfg.color("cream"))
        if self._subtitle:
            renderer.draw_text(self._subtitle, (self._sub_origin[0], self._sub_origin[1]),
                               self._font_sub, cfg.color("warm_core"))
        underline_y = self._sub_origin[1] + self._underline_gap
        renderer.draw_line(
            (self._title_origin[0], underline_y),
            (self._title_origin[0] + self._underline_width, underline_y),
            dim(cfg.color("dialog_border"), 0.75), width=1,
        )

        self._menu.draw()

        version = f"{self._version_prefix}{self._version}"
        text_w, _ = renderer.measure_text(version, self._font_version)
        renderer.draw_text(
            version,
            (width - text_w - self._version_margin[0], height - 28 - self._version_margin[1]),
            self._font_version,
            cfg.color("text_dim"),
        )
