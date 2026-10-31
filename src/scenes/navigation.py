"""场景路由：唯一允许决定“下一步去哪个场景”的地方。

场景自己只调用 router 的方法，不 import 其它场景，保证低耦合。
"""

from __future__ import annotations

import logging
from typing import Callable

from ..core.context import SceneContext
from ..core.scene import Scene
from ..core.scene_stack import SceneStack

log = logging.getLogger(__name__)


class Router:
    def __init__(self, stack: SceneStack, ctx_factory: Callable[[], SceneContext]) -> None:
        self._stack = stack
        self._ctx_factory = ctx_factory
        self._quit_requested = False

    # --- 工厂（延迟导入，避免循环引用） -------------------------------
    def _title_factory(self) -> Callable[[], Scene]:
        from .title import TitleScene

        return lambda: TitleScene(self._ctx_factory())

    def _settings_factory(self) -> Callable[[], Scene]:
        from .settings import SettingsScene

        return lambda: SettingsScene(self._ctx_factory())

    def _cutscene_factory(self, scene_id: str) -> Callable[[], Scene]:
        from .base_cutscene import CutsceneScene

        return lambda: CutsceneScene(self._ctx_factory(), scene_id)

    def _survival_factory(self) -> Callable[[], Scene]:
        from .coast import CoastScene

        return lambda: CoastScene(self._ctx_factory())

    # --- 场景切换 -----------------------------------------------------
    def goto_title(self) -> None:
        ctx = self._ctx_factory()
        ctx.state.reset_progress()
        ctx.audio.stop_all()
        self._stack.set(self._title_factory())

    def start_scene(self, scene_id: str) -> None:
        self._stack.set(self._cutscene_factory(scene_id))

    def next_scene(self, current_id: str) -> None:
        ctx = self._ctx_factory()
        try:
            spec = ctx.data.scene(current_id)
        except Exception:
            log.exception("找不到当前场景 %s，返回开始界面", current_id)
            self.goto_title()
            return
        if not spec.next_scene:
            self.handoff_to_gameplay()
            return
        self._stack.set(self._cutscene_factory(spec.next_scene))

    def handoff_to_gameplay(self) -> None:
        self._stack.set(self._survival_factory())

    def open_settings(self) -> None:
        self._stack.push(self._settings_factory())

    def back_to_title(self) -> None:
        self._stack.pop()

    def quit_game(self) -> None:
        self._quit_requested = True

    # --- 查询 ---------------------------------------------------------
    @property
    def quit_requested(self) -> bool:
        return self._quit_requested
