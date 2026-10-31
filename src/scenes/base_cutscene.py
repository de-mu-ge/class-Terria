"""数据驱动的剧情场景基类。

一个 Scene 类 + 一份 timeline 数据 = 一段演出；场景之间只通过 SceneStack 切换。
按 Esc 弹出二次确认，确认后回开始界面。
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..core.context import SceneContext
from ..core.events import InputEvent, InputKind
from ..core.scene import Scene
from ..data.models import SceneSpec
from ..ui.menu import ConfirmDialog
from .director import Director

log = logging.getLogger(__name__)


class CutsceneScene(Scene):
    def __init__(self, ctx: SceneContext, scene_id: str) -> None:
        super().__init__(ctx)
        self._scene_id = scene_id
        self.spec: SceneSpec | None = None
        self.director: Director | None = None
        self._confirm: ConfirmDialog | None = None
        self.scene_id = scene_id

    # --- 生命周期 -----------------------------------------------------
    def enter(self) -> None:
        spec = self.ctx.data.scene(self._scene_id)
        self.spec = spec
        self.scene_id = spec.id
        self.ctx.state.current_scene_id = spec.id
        if spec.id not in self.ctx.state.visited_scenes:
            self.ctx.state.visited_scenes.append(spec.id)
        self._preload(spec)
        self.director = Director(self.ctx, spec, on_complete=self._on_complete)
        self.director.autoplay = bool(self.ctx.state.flags.get("autoplay"))
        log.info("Scene %s 开始：%s（%d 条演出指令）", spec.id, spec.title, len(spec.timeline))

    def exit(self) -> None:
        if self.director is not None:
            self.director.stop_all_ui()
        self._confirm = None

    def _preload(self, spec: SceneSpec) -> None:
        doll_paths: list[Path] = []
        seen: set[str] = set()
        for command in spec.timeline:
            if command.get("cmd") == "dialogue":
                try:
                    block = self.ctx.data.dialogue_block(str(command.get("block", "")))
                except Exception:
                    continue
                for line in block.lines:
                    if not line.portrait:
                        continue
                    try:
                        character = self.ctx.data.character(line.speaker)
                    except Exception:
                        continue
                    relative = character.doll_path(line.portrait)
                    if relative and relative not in seen:
                        seen.add(relative)
                        doll_paths.append(self.ctx.paths.paper_doll(relative))
        self.ctx.resources.preload_scene(spec, doll_paths)

    # --- 每帧 ---------------------------------------------------------
    def update(self, dt: float) -> None:
        if self.director is not None:
            self.director.update(dt)

    def handle_event(self, event: InputEvent) -> None:
        if self._confirm is not None:
            self._confirm.handle_event(event)
            if not self._confirm.active:
                if self._confirm.result == "yes":
                    self._confirm = None
                    self.ctx.router.goto_title()
                else:
                    self._confirm = None
            return

        if event.kind == InputKind.CANCEL:
            self._open_confirm()
            return
        if event.kind == InputKind.TOGGLE_DEBUG:
            self.ctx.debug = not self.ctx.debug
            if self.director is not None:
                self.director.ctx.debug = self.ctx.debug
            return
        if self.director is not None:
            self.director.handle_event(event)

    def _open_confirm(self) -> None:
        cfg = self.ctx.config
        self._confirm = ConfirmDialog(
            self.ctx,
            title=cfg.text("ui_text", "confirm_title", default="返回开始界面？"),
            body=cfg.text("ui_text", "confirm_body", default=""),
            yes=cfg.text("ui_text", "confirm_yes", default="是"),
            no=cfg.text("ui_text", "confirm_no", default="否"),
        )
        self.ctx.audio.play_sfx("ui_click")

    # --- 绘制 ---------------------------------------------------------
    def draw(self) -> None:
        if self.director is None:
            self.ctx.renderer.clear(self.ctx.config.color("black"))
            return
        self.director.draw()
        if self._confirm is not None:
            self._confirm.draw()

    # --- 完成回调 -----------------------------------------------------
    def _on_complete(self, kind: str) -> None:
        scene_id = self.spec.id if self.spec else self._scene_id
        log.info("Scene %s 演出结束（kind=%s）", scene_id, kind)
        if kind == "handoff":
            self.ctx.router.handoff_to_gameplay()
        else:
            self.ctx.router.next_scene(scene_id)
