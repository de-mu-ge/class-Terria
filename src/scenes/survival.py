"""生存模式占位画面（Scene 07 交接控制权之后）。

本轮不做生存玩法，但必须证明「玩家已经拿到控制权」：
- 像素海岸 + 爱音 Sprite（程序化占位）可以左右走动
- HUD（生命 / 体温 + 快捷栏）常驻
- 右侧保留初始任务卡
- Esc 二次确认后回开始界面
"""

from __future__ import annotations

import logging

from ..core.context import SceneContext
from ..core.events import InputEvent, InputKind
from ..core.scene import Scene
from ..core.types import dim
from ..ui.hud import Hud
from ..ui.info_panels import TaskPanel
from ..ui.menu import ConfirmDialog
from ..ui.panels import draw_plain_panel
from .stage import BackgroundLayer, Camera, PixelActor

log = logging.getLogger(__name__)

_WALK_FRAMES = ("walk_1", "walk_2")


class SurvivalScene(Scene):
    scene_id = "survival"

    def __init__(self, ctx: SceneContext) -> None:
        super().__init__(ctx)
        self._bg = BackgroundLayer(ctx)
        self._hud = Hud(ctx)
        self._task = TaskPanel(ctx)
        self._sprite: PixelActor | None = None
        self._confirm: ConfirmDialog | None = None
        self._moving = 0
        self._walk_timer = 0.0
        self._walk_phase = 0
        self._elapsed = 0.0
        self._title = ctx.config.text("ui_text", "survival_title", default="")
        self._body = ctx.config.text("ui_text", "survival_body", default="")
        self._hint_lines = [str(line) for line in ctx.config.value("ui_text", "survival_hint", default=[])]
        self._info_panel = ctx.config.rect("survival", "panel")
        self._line_height = ctx.config.number("survival", "line_height", default=20)
        self._title_offset = ctx.config.number("survival", "title_offset", default=14)
        self._body_offset = ctx.config.number("survival", "body_offset", default=50)
        self._hint_offset = ctx.config.number("survival", "hint_offset", default=82)
        self._font_title = ctx.resources.font("title_sub")
        self._font_body = ctx.resources.font("menu_small")
        self._font_hint = ctx.resources.font("hint")

    def enter(self) -> None:
        self.ctx.state.current_scene_id = "survival"
        character = self.ctx.data.character("anon")
        self._sprite = PixelActor(self.ctx, character)
        self._sprite.x = self.ctx.renderer.width * 0.4
        self._sprite.set_pose("idle")

        spec = self.ctx.data.scene("s07")
        background = spec.backgrounds.get("coast") or next(iter(spec.backgrounds.values()), None)
        if background is not None:
            texture = self.ctx.resources.texture(self.ctx.paths.background(background.file))
            self._bg.set(texture, Camera(zoom=2.0, focus=(0.5, 0.6)), smooth=background.smooth)

        self._hud.show()
        self._hud.set_values(life=0.78, temp=0.55)
        self._load_task(spec)
        self.ctx.audio.play_ambience("waves")
        self.ctx.audio.play_music("unknown_world")

    def _load_task(self, spec) -> None:
        """沿用 Scene 07 的初始任务卡内容（同一份数据，不重复写死）。"""
        for command in reversed(spec.timeline):
            if command.get("cmd") == "task" and command.get("visible", True):
                rows = [(str(pair[0]), str(pair[1])) for pair in command.get("rows", [])]
                self._task.show(str(command.get("title", "")), rows)
                return

    def exit(self) -> None:
        self._confirm = None

    # --- 每帧 ---------------------------------------------------------
    def update(self, dt: float) -> None:
        self._elapsed += dt
        self._bg.update(dt)
        self._hud.update(dt)
        self._task.update(dt)
        if self._sprite is not None and self._moving != 0:
            self._walk_timer += dt
            if self._walk_timer >= 0.12:
                self._walk_timer = 0.0
                self._walk_phase = (self._walk_phase + 1) % len(_WALK_FRAMES)
                self._sprite.set_pose(_WALK_FRAMES[self._walk_phase])
            self._sprite.x = max(40.0, min(self.ctx.renderer.width - 40.0,
                                           self._sprite.x + self._moving * 140.0 * dt))
            self._sprite.flip = self._moving < 0
        elif self._sprite is not None:
            self._sprite.set_pose("idle")

    # --- 输入 ---------------------------------------------------------
    def handle_event(self, event: InputEvent) -> None:
        if self._confirm is not None:
            self._confirm.handle_event(event)
            if not self._confirm.active:
                if self._confirm.result == "yes":
                    self.ctx.router.goto_title()
                self._confirm = None
            return
        if event.kind == InputKind.CANCEL:
            cfg = self.ctx.config
            self._confirm = ConfirmDialog(
                self.ctx,
                title=cfg.text("ui_text", "confirm_title", default=""),
                body=cfg.text("ui_text", "confirm_body", default=""),
                yes=cfg.text("ui_text", "confirm_yes", default="是"),
                no=cfg.text("ui_text", "confirm_no", default="否"),
            )
            self.ctx.audio.play_sfx("ui_click")
        elif event.kind == InputKind.MOVE_LEFT:
            self._moving = -1
        elif event.kind == InputKind.MOVE_RIGHT:
            self._moving = 1
        elif event.kind == InputKind.MOVE_STOP:
            self._moving = 0

    # --- 绘制 ---------------------------------------------------------
    def draw(self) -> None:
        renderer = self.ctx.renderer
        cfg = self.ctx.config
        renderer.clear(cfg.color("black"))
        self._bg.draw(renderer)
        if self._sprite is not None:
            self._sprite.draw(renderer)
        self._hud.draw()
        self._task.draw()

        # 占位说明（本轮不做玩法，明确告知玩家）：左侧独立面板，避免压住角色和 HUD
        panel = self._info_panel
        draw_plain_panel(renderer, panel, cfg.color("dialog_bg"),
                         cfg.alpha("task_bg"),
                         border=dim(cfg.color("dialog_border"), 0.8), border_width=1)
        renderer.draw_text(self._title, (panel.x + 18, panel.y + self._title_offset),
                           self._font_title, cfg.color("warm_core"))
        renderer.draw_text(self._body, (panel.x + 18, panel.y + self._body_offset),
                           self._font_body, cfg.color("text_dim"))
        y = panel.y + self._hint_offset
        for line in self._hint_lines:
            renderer.draw_text(line, (panel.x + 18, y), self._font_hint,
                               dim(cfg.color("text"), 0.85))
            y += self._line_height
        if self._confirm is not None:
            self._confirm.draw()
