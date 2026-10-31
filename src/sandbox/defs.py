"""地块 / 物品 / 配方定义（全部来自 data/tiles.json 与 data/items.json）。"""

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
    hardness: float
    tool: str
    drop: str | None
    light: int
    color: Color
    pattern: str
    station: str | None = None

    @property
    def is_air(self) -> bool:
        return self.key == "air"


@dataclass(frozen=True)
class ItemDef:
    id: str
    name: str
    kind: str                       # block / material / furniture / tool
    color: Color
    stack: int
    tile: str | None = None
    tool: str | None = None
    power: float = 1.0
    icon: str | None = None

    @property
    def is_placeable(self) -> bool:
        return self.tile is not None


@dataclass(frozen=True)
class Recipe:
    id: str
    output: str
    count: int
    station: str | None
    ingredients: tuple[tuple[str, int], ...] = field(default_factory=tuple)


class Defs:
    """地块与物品注册表。"""

    def __init__(self, tiles: list[TileDef], items: dict[str, ItemDef],
                 recipes: list[Recipe], tile_size: int) -> None:
        self.tiles = tiles
        self.tiles_by_key = {tile.key: tile for tile in tiles}
        self.tiles_by_id = {tile.id: tile for tile in tiles}
        self.items = items
        self.recipes = recipes
        self.tile_size = tile_size

    # --- 载入 ---------------------------------------------------------
    @classmethod
    def load(cls, data_root: Path) -> "Defs":
        tiles_raw = _read(data_root / "tiles.json")
        items_raw = _read(data_root / "items.json")

        tiles: list[TileDef] = []
        for entry in tiles_raw.get("tiles", []):
            tiles.append(
                TileDef(
                    id=int(entry["id"]),
                    key=entry["key"],
                    name=entry.get("name", entry["key"]),
                    solid=bool(entry.get("solid", True)),
                    hardness=float(entry.get("hardness", 0.0)),
                    tool=entry.get("tool", "any"),
                    drop=entry.get("drop"),
                    light=int(entry.get("light", 0)),
                    color=parse_color(entry.get("color", "#FFFFFF")),
                    pattern=entry.get("pattern", "none"),
                    station=entry.get("station"),
                )
            )
        tiles.sort(key=lambda tile: tile.id)

        items: dict[str, ItemDef] = {}
        for entry in items_raw.get("items", []):
            item = ItemDef(
                id=entry["id"],
                name=entry.get("name", entry["id"]),
                kind=entry.get("kind", "material"),
                color=parse_color(entry.get("color", "#FFFFFF")),
                stack=int(entry.get("stack", 99)),
                tile=entry.get("tile"),
                tool=entry.get("tool"),
                power=float(entry.get("power", 1.0)),
                icon=entry.get("icon"),
            )
            items[item.id] = item

        recipes: list[Recipe] = []
        for entry in items_raw.get("recipes", []):
            recipes.append(
                Recipe(
                    id=entry["id"],
                    output=entry["output"],
                    count=int(entry.get("count", 1)),
                    station=entry.get("station"),
                    ingredients=tuple(
                        (str(pair["item"]), int(pair["count"]))
                        for pair in entry.get("ingredients", [])
                    ),
                )
            )
        if not tiles or not items:
            raise ValueError("沙盒数据为空：检查 data/tiles.json 与 data/items.json")
        log.info("沙盒定义载入：%d 种地块 / %d 种物品 / %d 条配方",
                 len(tiles), len(items), len(recipes))
        return cls(tiles, items, recipes, int(tiles_raw.get("tile_size", 16)))

    # --- 查询 ---------------------------------------------------------
    def tile_by_id(self, tile_id: int) -> TileDef:
        return self.tiles_by_id.get(tile_id, self.tiles[0])

    def tile_by_key(self, key: str) -> TileDef:
        return self.tiles_by_key[key]

    def item(self, item_id: str) -> ItemDef:
        return self.items[item_id]

    def air_id(self) -> int:
        return self.tile_by_key("air").id


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"缺少沙盒数据文件：{path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))
