"""数据读取与校验。

只做读取：JSON 内容属于“数据”，代码里不允许出现剧情台词。
校验失败给出可读的错误信息，而不是在演出中途崩溃。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..assets.paths import AssetPaths
from ..core.types import parse_color
from .models import (
    BackgroundSpec,
    Character,
    DialogueBlock,
    GameConfig,
    Line,
    SceneSpec,
)

log = logging.getLogger(__name__)


class DataError(RuntimeError):
    pass


def normalize_scene_id(value: str) -> str:
    """'03' / '3' / 's03' / 'S03' → 's03'。"""
    text = str(value).strip().lower()
    if text.startswith("s"):
        text = text[1:]
    if text.isdigit():
        return f"s{int(text):02d}"
    return f"s{text}"


class DataRepository:
    def __init__(self, paths: AssetPaths) -> None:
        self._paths = paths
        self.config = GameConfig({})
        self._characters: dict[str, Character] = {}
        self._scenes: dict[str, SceneSpec] = {}
        self._order: list[str] = []
        self._blocks: dict[str, DialogueBlock] = {}
        self._raw: dict[str, Any] = {}
        self.placeholder_config: dict[str, Any] = {}

    # --- 载入 ---------------------------------------------------------
    def load(self) -> "DataRepository":
        root = self._paths.data_root
        self._raw["config"] = self._read_json(root / "config.json")
        self._raw["characters"] = self._read_json(root / "characters.json")
        self._raw["dialogues"] = self._read_json(root / "dialogues.json")
        self._raw["scenes"] = self._read_json(root / "scenes.json")

        self.config = GameConfig(self._raw["config"])
        self._load_characters(self._raw["characters"])
        self._load_dialogues(self._raw["dialogues"])
        self._load_scenes(self._raw["scenes"])
        self.validate()
        log.info("数据载入完成：%d 角色 / %d 场景 / %d 台词段", len(self._characters),
                 len(self._scenes), len(self._blocks))
        return self

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise DataError(f"缺少数据文件：{path}")
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except json.JSONDecodeError as exc:
            raise DataError(f"{path.name} 不是合法 JSON：{exc}") from exc

    # --- 角色 ---------------------------------------------------------
    def _load_characters(self, raw: dict[str, Any]) -> None:
        self.placeholder_config = dict(raw.get("placeholder", {}))
        for item in raw.get("characters", []):
            char = Character(
                id=item["id"],
                name=item.get("name", item["id"]),
                short_name=item.get("short_name", item.get("name", item["id"])),
                color=parse_color(item.get("color", "#FFFFFF")),
                color_status=item.get("color_status", "provisional"),
                role=item.get("role", ""),
                paper_dolls=dict(item.get("paper_dolls", {})),
                sprite=dict(item.get("sprite", {})),
            )
            if char.id in self._characters:
                raise DataError(f"角色 ID 重复：{char.id}")
            self._characters[char.id] = char
        if not self._characters:
            raise DataError("characters.json 里没有任何角色")

    # --- 台词 ---------------------------------------------------------
    def _load_dialogues(self, raw: dict[str, Any]) -> None:
        for block_id, payload in raw.get("blocks", {}).items():
            lines: list[Line] = []
            for index, item in enumerate(payload.get("lines", [])):
                speaker = item.get("speaker", "")
                lines.append(
                    Line(
                        id=f"{block_id}:{index}",
                        block_id=block_id,
                        index=index,
                        speaker=speaker,
                        text=item.get("text", ""),
                        portrait=item.get("portrait"),
                        emotion=item.get("emotion", ""),
                        action=item.get("action", ""),
                        camera=item.get("camera"),
                        sfx=item.get("sfx"),
                        wait=float(item.get("wait", 0.0) or 0.0),
                        pause=float(item.get("pause", 0.0) or 0.0),
                        pose=item.get("pose"),
                    )
                )
            self._blocks[block_id] = DialogueBlock(
                id=block_id, scene=payload.get("scene", ""), lines=tuple(lines)
            )

    # --- 场景 ---------------------------------------------------------
    def _load_scenes(self, raw: dict[str, Any]) -> None:
        self._order = list(raw.get("order", []))
        for scene_id, payload in raw.get("scenes", {}).items():
            backgrounds: dict[str, BackgroundSpec] = {}
            for bg_id, bg in payload.get("backgrounds", {}).items():
                backgrounds[bg_id] = BackgroundSpec(
                    id=bg_id,
                    file=bg.get("file", ""),
                    smooth=bool(bg.get("smooth", True)),
                    label=bg.get("label", ""),
                )
            scene = SceneSpec(
                id=scene_id,
                index=int(payload.get("index", 0)),
                title=payload.get("title", scene_id),
                stage=payload.get("stage", "real"),
                pipeline=payload.get("pipeline", "galgame"),
                backgrounds=backgrounds,
                timeline=tuple(payload.get("timeline", [])),
                next_scene=payload.get("next"),
                music=payload.get("music"),
                ambience=payload.get("ambience"),
            )
            self._scenes[scene_id] = scene
        if not self._scenes:
            raise DataError("scenes.json 里没有任何场景")
        if not self._order:
            self._order = sorted(self._scenes, key=lambda sid: self._scenes[sid].index)

    # --- 校验 ---------------------------------------------------------
    def validate(self) -> None:
        problems: list[str] = []
        for scene_id in self._order:
            if scene_id not in self._scenes:
                problems.append(f"order 里列出的场景 {scene_id} 不存在")
                continue
            scene = self._scenes[scene_id]
            if scene.next_scene and scene.next_scene not in self._scenes:
                problems.append(f"{scene_id}.next 指向不存在的场景 {scene.next_scene}")
            if not scene.timeline:
                problems.append(f"{scene_id} 没有 timeline")
            for command in scene.timeline:
                cmd = command.get("cmd")
                if not cmd:
                    problems.append(f"{scene_id} 存在缺少 cmd 的指令：{command}")
                    continue
                if cmd == "dialogue":
                    block_id = command.get("block")
                    if block_id not in self._blocks:
                        problems.append(f"{scene_id} 引用了不存在的台词段 {block_id}")
                    elif self._blocks[block_id].scene and self._blocks[block_id].scene != scene_id:
                        problems.append(
                            f"台词段 {block_id} 标注为 {self._blocks[block_id].scene}，却被 {scene_id} 使用"
                        )
                elif cmd == "bg":
                    bg_id = command.get("id")
                    if bg_id not in scene.backgrounds:
                        problems.append(f"{scene_id} 引用了未登记的背景 {bg_id}")
                elif cmd == "sprite":
                    char_id = command.get("char")
                    if char_id not in self._characters:
                        problems.append(f"{scene_id} 引用了不存在的角色 {char_id}")
                elif cmd == "doll_show":
                    char_id = command.get("char")
                    if char_id not in self._characters:
                        problems.append(f"{scene_id} 引用了不存在的角色 {char_id}")

        for block in self._blocks.values():
            for line in block.lines:
                if line.speaker and line.speaker not in self._characters and not line.is_narration:
                    problems.append(f"{line.id} 的说话人 {line.speaker} 未在 characters.json 登记")

        if problems:
            raise DataError("数据校验失败：\n  - " + "\n  - ".join(problems))

    # --- 查询 ---------------------------------------------------------
    @property
    def scene_order(self) -> list[str]:
        return list(self._order)

    def scene(self, scene_id: str) -> SceneSpec:
        key = scene_id if scene_id in self._scenes else normalize_scene_id(scene_id)
        if key not in self._scenes:
            raise DataError(f"没有这个场景：{scene_id}（可用：{', '.join(self._order)}）")
        return self._scenes[key]

    def has_scene(self, scene_id: str) -> bool:
        return scene_id in self._scenes

    def character(self, char_id: str) -> Character:
        if char_id not in self._characters:
            raise DataError(f"没有这个角色：{char_id}")
        return self._characters[char_id]

    @property
    def characters(self) -> dict[str, Character]:
        return dict(self._characters)

    def dialogue_block(self, block_id: str) -> DialogueBlock:
        if block_id not in self._blocks:
            raise DataError(f"没有这个台词段：{block_id}")
        return self._blocks[block_id]

    @property
    def dialogue_blocks(self) -> dict[str, DialogueBlock]:
        return dict(self._blocks)

    # --- 素材缺口清单 -------------------------------------------------
    def required_assets(self) -> list[dict[str, str]]:
        """列出全部“应当存在”的素材：背景 + 纸片 + 精灵，用于缺图清单。"""
        required: list[dict[str, str]] = []
        seen: set[str] = set()

        for scene_id in self._order:
            scene = self._scenes[scene_id]
            for bg in scene.backgrounds.values():
                key = f"bg:{scene_id}:{bg.id}"
                if key in seen:
                    continue
                seen.add(key)
                required.append(
                    {
                        "kind": "background",
                        "scene": scene_id,
                        "id": bg.id,
                        "path": str(self._paths.background(bg.file)),
                        "label": bg.label or bg.id,
                    }
                )

        for block in self._blocks.values():
            scene_id = block.scene
            for line in block.lines:
                if not line.portrait or line.is_narration:
                    continue
                char = self._characters.get(line.speaker)
                if char is None:
                    continue
                relative = char.doll_path(line.portrait)
                if not relative:
                    continue
                key = f"doll:{char.id}:{line.portrait}"
                if key in seen:
                    continue
                seen.add(key)
                required.append(
                    {
                        "kind": "paper_doll",
                        "scene": scene_id,
                        "id": line.portrait,
                        "character": char.id,
                        "path": str(self._paths.paper_doll(relative)),
                        "label": f"{char.name} / {line.portrait}",
                    }
                )

        for char in self._characters.values():
            for frame in char.sprite.get("frames", []):
                key = f"sprite:{char.id}:{frame}"
                if key in seen:
                    continue
                seen.add(key)
                required.append(
                    {
                        "kind": "sprite",
                        "scene": "s07",
                        "id": frame,
                        "character": char.id,
                        "path": "",
                        "label": f"{char.name} / {frame}（程序化占位）",
                    }
                )
        return required

    def missing_assets(self) -> list[dict[str, str]]:
        missing: list[dict[str, str]] = []
        for item in self.required_assets():
            if item["kind"] == "sprite":
                continue  # 程序化生成，不算缺
            path = Path(item["path"])
            if not path.is_file():
                missing.append(item)
        return missing
