"""数据模型：配置、角色、台词、场景。

全部是只读数据结构，由 DataRepository 从 data/*.json 组装。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ..core.types import Color, Rect, parse_color


class GameConfig:
    """data/config.json 的只读包装，提供带默认值的取值方法。"""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw

    # --- 通用取值 -----------------------------------------------------
    def _get(self, path: Iterable[str], default: Any = None) -> Any:
        node: Any = self.raw
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def section(self, name: str) -> dict[str, Any]:
        value = self.raw.get(name, {})
        return value if isinstance(value, dict) else {}

    def value(self, *path: str, default: Any = None) -> Any:
        return self._get(path, default)

    def number(self, *path: str, default: float = 0.0) -> float:
        value = self._get(path, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def integer(self, *path: str, default: int = 0) -> int:
        return int(round(self.number(*path, default=default)))

    def text(self, *path: str, default: str = "") -> str:
        value = self._get(path, default)
        return default if value is None else str(value)

    def flag(self, *path: str, default: bool = False) -> bool:
        value = self._get(path, default)
        return bool(value) if value is not None else default

    def color(self, name: str) -> Color:
        palette = self.section("palette")
        return parse_color(palette.get(name, "#FFFFFF"))

    def alpha(self, name: str, default: float = 1.0) -> int:
        value = self.section("alpha").get(name, default)
        try:
            return int(round(max(0.0, min(1.0, float(value))) * 255))
        except (TypeError, ValueError):
            return int(default * 255)

    def rect(self, *path: str, default: tuple[float, float, float, float] = (0, 0, 0, 0)) -> Rect:
        value = self._get(path, default)
        try:
            return Rect.from_sequence(value)
        except (TypeError, ValueError):
            return Rect.from_sequence(default)

    def ui_text(self, key: str, default: Any = "") -> Any:
        return self.section("ui_text").get(key, default)


@dataclass(frozen=True)
class Line:
    id: str
    block_id: str
    index: int
    speaker: str
    text: str
    portrait: str | None = None
    emotion: str = ""
    action: str = ""
    camera: str | None = None
    sfx: str | None = None
    wait: float = 0.0
    pause: float = 0.0
    pose: str | None = None

    @property
    def is_narration(self) -> bool:
        return self.speaker in ("", "narrator")


@dataclass(frozen=True)
class DialogueBlock:
    id: str
    scene: str
    lines: tuple[Line, ...]

    def __len__(self) -> int:
        return len(self.lines)

    def __iter__(self):
        return iter(self.lines)


@dataclass(frozen=True)
class Character:
    id: str
    name: str
    short_name: str
    color: Color
    color_status: str
    role: str
    paper_dolls: dict[str, str] = field(default_factory=dict)
    sprite: dict[str, Any] = field(default_factory=dict)

    def doll_path(self, portrait: str | None) -> str | None:
        if not portrait:
            return None
        return self.paper_dolls.get(portrait)


@dataclass(frozen=True)
class BackgroundSpec:
    id: str
    file: str
    smooth: bool = True
    label: str = ""


@dataclass(frozen=True)
class SceneSpec:
    id: str
    index: int
    title: str
    stage: str
    pipeline: str
    backgrounds: dict[str, BackgroundSpec]
    timeline: tuple[dict[str, Any], ...]
    next_scene: str | None = None
    music: str | None = None
    ambience: str | None = None
    source_file: str = ""

    def background(self, bg_id: str) -> BackgroundSpec | None:
        return self.backgrounds.get(bg_id)

    @property
    def debug_flag(self) -> str:
        return f"--scene {self.index:02d}"
