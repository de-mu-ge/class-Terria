"""场景运行期上下文。

SceneContext 是场景唯一能摸到的“外面”：渲染器、资源、数据、音频、状态、路由。
场景不 import pygame，也不 import 其它场景。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from .input_state import KeyboardState, MouseState

if TYPE_CHECKING:  # pragma: no cover
    from ..assets.paths import AssetPaths
    from ..audio.audio import AudioService
    from ..data.config import GameConfig
    from ..data.models import Character, Line, SceneSpec
    from ..data.repository import DataRepository
    from ..render.renderer import Renderer
    from .resource_manager import ResourceManager


class SceneRouter(Protocol):
    """场景切换接口（由 app 实现，内部委托 SceneStack）。"""

    def goto_title(self) -> None: ...

    def start_scene(self, scene_id: str) -> None: ...

    def next_scene(self) -> None: ...

    def quit_game(self) -> None: ...

    def handoff_to_gameplay(self) -> None: ...


@dataclass
class GameState:
    """全局运行状态（本轮只存内存，退出即清空）。"""

    current_scene_id: str | None = None
    visited_scenes: list[str] = field(default_factory=list)
    read_lines: set[str] = field(default_factory=set)
    flags: dict[str, object] = field(default_factory=dict)
    master_volume: float = 0.7
    debug: bool = False

    def mark_read(self, line_id: str) -> None:
        self.read_lines.add(line_id)

    def is_read(self, line_id: str) -> bool:
        return line_id in self.read_lines

    def reset_progress(self) -> None:
        self.current_scene_id = None
        self.visited_scenes.clear()
        self.read_lines.clear()
        self.flags.clear()


@dataclass
class SceneContext:
    renderer: "Renderer"
    resources: "ResourceManager"
    data: "DataRepository"
    audio: "AudioService"
    paths: "AssetPaths"
    config: "GameConfig"
    state: GameState
    router: SceneRouter
    mouse: MouseState = field(default_factory=MouseState)
    keys: KeyboardState = field(default_factory=KeyboardState)
    headless: bool = False
    debug: bool = False

    # --- 便捷访问 -----------------------------------------------------
    @property
    def width(self) -> int:
        return self.renderer.size[0]

    @property
    def height(self) -> int:
        return self.renderer.size[1]

    def scene_spec(self, scene_id: str) -> "SceneSpec":
        return self.data.scene(scene_id)

    def character(self, char_id: str) -> "Character":
        return self.data.character(char_id)

    def lines(self, block_id: str) -> list["Line"]:
        return self.data.dialogue_block(block_id)
