"""海岸世界的定义层：地块、生态对象、物品、配方、生成参数。

全部来自 data/coast/*.json；代码里不写死资源名与颜色。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.types import Color, parse_color

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TileDef:
    id: int
    key: str
    name: str
    solid: bool
    color: Color
    dark: Color
    pattern: str


@dataclass(frozen=True)
class Harvest:
    item: str
    count: int


@dataclass(frozen=True)
class ObjectDef:
    id: str
    name: str
    kind: str                       # harvestable / placeable
    size: tuple[int, int]
    color: Color
    accent: Color
    harvest: Harvest | None = None
    zones: tuple[str, ...] = ()
    sway: float = 0.0
    light: int = 0
    prompt: str = ""


@dataclass(frozen=True)
class ItemDef:
    id: str
    name: str
    kind: str                       # material / placeable
    color: Color
    icon: str
    stack: int = 99
    object: str | None = None


@dataclass(frozen=True)
class Recipe:
    id: str
    output: str
    count: int
    ingredients: tuple[tuple[str, int], ...] = field(default_factory=tuple)


class CoastDefs:
    def __init__(self, tiles: list[TileDef], objects: dict[str, ObjectDef],
                 items: dict[str, ItemDef], recipes: list[Recipe], tile_size: int,
                 world_params: dict[str, Any]) -> None:
        self.tiles = tiles
        self.tiles_by_id = {tile.id: tile for tile in tiles}
        self.tiles_by_key = {tile.key: tile for tile in tiles}
        self.objects = objects
        self.items = items
        self.recipes = recipes
        self.tile_size = tile_size
        self.world = world_params

    # --- 载入 ---------------------------------------------------------
    @classmethod
    def load(cls, data_root: Path) -> "CoastDefs":
        root = data_root / "coast"
        tiles_raw = _read(root / "tiles.json")
        objects_raw = _read(root / "objects.json")
        items_raw = _read(root / "items.json")
        world_raw = _read(root / "world.json")

        tiles: list[TileDef] = []
        for entry in tiles_raw.get("tiles", []):
            tiles.append(TileDef(
                id=int(entry["id"]),
                key=entry["key"],
                name=entry.get("name", entry["key"]),
                solid=bool(entry.get("solid", True)),
                color=parse_color(entry.get("color", "#FFFFFF")),
                dark=parse_color(entry.get("dark", entry.get("color", "#FFFFFF"))),
                pattern=entry.get("pattern", "none"),
            ))
        tiles.sort(key=lambda tile: tile.id)

        objects: dict[str, ObjectDef] = {}
        for entry in objects_raw.get("objects", []):
            harvest = entry.get("harvest")
            objects[entry["id"]] = ObjectDef(
                id=entry["id"],
                name=entry.get("name", entry["id"]),
                kind=entry.get("kind", "harvestable"),
                size=(int(entry.get("size", [16, 16])[0]), int(entry.get("size", [16, 16])[1])),
                color=parse_color(entry.get("color", "#FFFFFF")),
                accent=parse_color(entry.get("accent", entry.get("color", "#FFFFFF"))),
                harvest=Harvest(str(harvest["item"]), int(harvest.get("count", 1))) if harvest else None,
                zones=tuple(entry.get("zones", ())),
                sway=float(entry.get("sway", 0.0)),
                light=int(entry.get("light", 0)),
                prompt=entry.get("prompt", ""),
            )

        items: dict[str, ItemDef] = {}
        for entry in items_raw.get("items", []):
            items[entry["id"]] = ItemDef(
                id=entry["id"],
                name=entry.get("name", entry["id"]),
                kind=entry.get("kind", "material"),
                color=parse_color(entry.get("color", "#FFFFFF")),
                icon=entry.get("icon", "gem"),
                stack=int(entry.get("stack", 99)),
                object=entry.get("object"),
            )

        recipes = [
            Recipe(
                id=entry["id"],
                output=entry["output"],
                count=int(entry.get("count", 1)),
                ingredients=tuple((str(p["item"]), int(p["count"]))
                                  for p in entry.get("ingredients", [])),
            )
            for entry in items_raw.get("recipes", [])
        ]

        if not tiles or not objects or not items:
            raise ValueError("海岸数据为空：检查 data/coast/*.json")
        log.info("海岸定义载入：%d 地块 / %d 对象 / %d 物品 / %d 配方",
                 len(tiles), len(objects), len(items), len(recipes))
        return cls(tiles, objects, items, recipes, int(tiles_raw.get("tile_size", 16)), world_raw)

    # --- 查询 ---------------------------------------------------------
    def tile_by_id(self, tile_id: int) -> TileDef:
        return self.tiles_by_id.get(tile_id, self.tiles[0])

    def tile_by_key(self, key: str) -> TileDef:
        return self.tiles_by_key[key]

    def item(self, item_id: str) -> ItemDef:
        return self.items[item_id]

    def obj(self, obj_id: str) -> ObjectDef:
        return self.objects[obj_id]

    def air_id(self) -> int:
        return self.tile_by_key("air").id


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"缺少海岸数据文件：{path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))
