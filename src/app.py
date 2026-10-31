"""应用装配：把数据、渲染、场景栈、音频、输入接到一起。

python -m src                 正常启动（开始界面）
python -m src --scene 03      单独调试某个 Scene
python -m src --headless ...  无窗口自动跑通（验证用）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pygame

from .assets.paths import AssetPaths
from .audio.audio import AudioService
from .core.context import GameState, SceneContext
from .core.events import InputEvent, InputKind
from .core.input_state import KeyboardState, MouseState
from .core.game_loop import FixedTimestepLoop
from .core.resource_manager import ResourceManager
from .core.scene_stack import SceneStack
from .data.repository import DataRepository, normalize_scene_id
from .render.pygame_renderer import PygameRenderer
from .scenes.navigation import Router

log = logging.getLogger(__name__)

_KEY_MAP: dict[int, list[str]] = {}


@dataclass
class AppOptions:
    scene: str | None = None
    headless: bool = False
    autoplay: bool = False
    speed: float = 1.0
    capture_dir: str | None = None
    capture_times: list[float] = field(default_factory=list)
    debug: bool = False
    no_audio: bool = False
    window_scale: int | None = None
    max_seconds: float = 600.0
    quit_on_handoff: bool = False
    smoke: bool = False


class Application:
    def __init__(self, options: AppOptions, project_root: Path | None = None) -> None:
        self.options = options
        self.project_root = project_root or Path(__file__).resolve().parent.parent
        self._running = True
        self._exit_code = 0
        self._capture_index = 0
        self._capture_plan = list(options.capture_times)
        self._elapsed = 0.0
        self._handoff_at: float | None = None
        self._smoke_started = False

        self.paths = AssetPaths(self.project_root)
        self.data = DataRepository(self.paths).load()
        self.config = self.data.config

        display = self.config.section("display")
        self.renderer = PygameRenderer(
            width=int(display.get("logical_width", 960)),
            height=int(display.get("logical_height", 540)),
            window_scale=options.window_scale or int(display.get("window_scale", 2)),
            caption=str(display.get("caption", "")),
            headless=options.headless,
        )
        self.resources = ResourceManager(self.renderer, self.paths, self.config)
        self.children: dict[str, Any] = {}
        self.state = GameState(
            master_volume=self.config.number("audio", "master_volume", default=0.7),
            debug=options.debug,
        )
        self.state.flags["autoplay"] = options.autoplay
        self.audio = AudioService(self.config, self.paths, enabled=not options.no_audio)
        self.audio.init()

        self.mouse = MouseState()
        self.keys = KeyboardState()
        self.ctx = SceneContext(
            renderer=self.renderer,
            resources=self.resources,
            data=self.data,
            audio=self.audio,
            paths=self.paths,
            config=self.config,
            state=self.state,
            router=None,  # type: ignore[arg-type]
            mouse=self.mouse,
            keys=self.keys,
            headless=options.headless or options.autoplay,
            debug=options.debug,
        )
        self.stack = SceneStack(lambda: self.ctx)
        self.router = Router(self.stack, lambda: self.ctx)
        self.ctx.router = self.router

        self._bind_initial_scene()

    # --- 场景装配 -----------------------------------------------------
    def _bind_initial_scene(self) -> None:
        if self.options.scene:
            alias = str(self.options.scene).lower()
            if alias in ("coast", "coastal"):
                from .scenes.coast import CoastScene

                self.stack.set(lambda: CoastScene(self.ctx))
                return
            scene_id = normalize_scene_id(self.options.scene)
            if not self.data.has_scene(scene_id):
                raise SystemExit(f"没有这个场景：{self.options.scene}")
            from .scenes.base_cutscene import CutsceneScene

            self.stack.set(lambda: CutsceneScene(self.ctx, scene_id))
        else:
            from .scenes.title import TitleScene

            self.stack.set(lambda: TitleScene(self.ctx))

    # --- 主循环 -------------------------------------------------------
    def run(self) -> int:
        display = self.config.section("display")
        loop = FixedTimestepLoop(
            update=self._update,
            render=self._render,
            poll=self._poll_events,
            should_continue=lambda: self._running,
            time_source=lambda: pygame.time.get_ticks() / 1000.0,
            fixed_dt=float(display.get("fixed_timestep", 1.0 / 60.0)),
            time_scale=max(0.0, self.options.speed),
            max_frame_time=float(display.get("max_frame_time", 0.1)),
            max_update_steps=32 if self.options.speed > 1.5 else int(display.get("max_update_steps", 6)),
        )
        try:
            loop.run()
        finally:
            self._shutdown()
        return self._exit_code

    def _update(self, dt: float) -> None:
        self._elapsed += dt
        if self.options.smoke and not self._smoke_started and self._elapsed > 1.0:
            if self.state.current_scene_id == "title":
                self._smoke_started = True
                log.info("自检模式：从开始界面进入 Scene 01")
                self.router.start_scene("s01")
        self.stack.update(dt)
        if self.router.quit_requested:
            self._running = False
        if self.state.current_scene_id == "survival" and self.options.quit_on_handoff:
            if self._handoff_at is None:
                self._handoff_at = self._elapsed
            elif self._elapsed - self._handoff_at > 1.5:
                log.info("自动测试：已抵达生存模式占位画面，退出")
                self._running = False
        if self._elapsed > self.options.max_seconds:
            log.warning("超过最大运行时长 %.0fs，自动退出", self.options.max_seconds)
            self._running = False

    def _render(self) -> None:
        self.renderer.begin_frame()
        self.stack.draw()
        self._maybe_capture()
        self.renderer.present()

    def _maybe_capture(self) -> None:
        if not self.options.capture_dir or not self._capture_plan:
            return
        if self._elapsed + 1e-6 < self._capture_plan[0]:
            return
        target = self._capture_plan.pop(0)
        folder = Path(self.options.capture_dir)
        name = f"frame_{self._capture_index:03d}_{target:05.1f}s.png"
        self._capture_index += 1
        if self.renderer.capture(folder / name):
            log.info("截图：%s", folder / name)

    # --- 输入 ---------------------------------------------------------
    def _poll_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
                continue
            mapped = self._map_event(event)
            for item in mapped:
                self.stack.handle_event(item)

    _HELD_KEYS = {
        pygame.K_LEFT: "left", pygame.K_a: "left",
        pygame.K_RIGHT: "right", pygame.K_d: "right",
        pygame.K_UP: "up", pygame.K_w: "up",
        pygame.K_DOWN: "down", pygame.K_s: "down",
        pygame.K_SPACE: "jump",
    }
    _LETTER_KEYS = {
        pygame.K_e: "e", pygame.K_c: "c", pygame.K_i: "i", pygame.K_f: "f",
        pygame.K_TAB: "tab",
    }

    def _map_event(self, event) -> list[InputEvent]:
        scale = self.renderer.window_scale
        events: list[InputEvent] = []
        if event.type == pygame.KEYDOWN:
            held = self._HELD_KEYS.get(event.key)
            if held:
                self.keys.press(held)
            letter = self._LETTER_KEYS.get(event.key)
            if letter:
                events.append(InputEvent(InputKind.KEY, key=letter))
            elif pygame.K_1 <= event.key <= pygame.K_8:
                events.append(InputEvent(InputKind.KEY, key=str(event.key - pygame.K_0)))

            if event.key == pygame.K_ESCAPE:
                events.append(InputEvent(InputKind.CANCEL))
            elif event.key in (pygame.K_UP, pygame.K_w):
                events.append(InputEvent(InputKind.MENU_UP))
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                events.append(InputEvent(InputKind.MENU_DOWN))
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                events.append(InputEvent(InputKind.MENU_LEFT))
                events.append(InputEvent(InputKind.MOVE_LEFT))
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                events.append(InputEvent(InputKind.MENU_RIGHT))
                events.append(InputEvent(InputKind.MOVE_RIGHT))
            elif event.key == pygame.K_SPACE:
                events.append(InputEvent(InputKind.ADVANCE))
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                events.append(InputEvent(InputKind.CONFIRM))
            elif event.key in (pygame.K_LCTRL, pygame.K_RCTRL):
                events.append(InputEvent(InputKind.FAST_FORWARD_START))
            elif event.key == pygame.K_F1:
                events.append(InputEvent(InputKind.TOGGLE_DEBUG))
        elif event.type == pygame.KEYUP:
            held = self._HELD_KEYS.get(event.key)
            if held:
                self.keys.release(held)
            if event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                events.append(InputEvent(InputKind.MOVE_STOP))
            elif event.key in (pygame.K_LCTRL, pygame.K_RCTRL):
                events.append(InputEvent(InputKind.FAST_FORWARD_END))
        elif event.type == pygame.MOUSEBUTTONDOWN:
            pos = (int(event.pos[0] / scale), int(event.pos[1] / scale))
            self.mouse.move(pos)
            self.mouse.set_button(event.button, True)
            if event.button == 1:
                events.append(InputEvent(InputKind.CLICK, pos=pos))
            elif event.button == 3:
                events.append(InputEvent(InputKind.CLICK_RIGHT, pos=pos))
        elif event.type == pygame.MOUSEBUTTONUP:
            pos = (int(event.pos[0] / scale), int(event.pos[1] / scale))
            self.mouse.move(pos)
            self.mouse.set_button(event.button, False)
        elif event.type == pygame.MOUSEMOTION:
            pos = (int(event.pos[0] / scale), int(event.pos[1] / scale))
            self.mouse.move(pos)
            events.append(InputEvent(InputKind.POINTER, pos=pos))
        return events

    # --- 收尾 ---------------------------------------------------------
    def _shutdown(self) -> None:
        log.info("退出：场景栈 %s，资源 %s", self.stack.scene_ids(), self.resources.stats())
        if self.resources.missing:
            log.warning("本轮缺失素材 %d 项（详见 --check-assets）", len(self.resources.missing))
        self.stack.shutdown()
        self.audio.shutdown()
        self.renderer.shutdown()
