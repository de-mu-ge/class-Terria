"""合成系统：判定工作台等站点是否在手边，检查材料、执行合成。"""

from __future__ import annotations

from .defs import Defs, Recipe
from .inventory import Inventory
from .player import Player
from .world import World


class Crafting:
    def __init__(self, defs: Defs, inventory: Inventory) -> None:
        self._defs = defs
        self._inventory = inventory
        self._stations_cache: set[str] = set()
        self._station_key = (0, 0)

    # --- 站点 ---------------------------------------------------------
    def stations_near(self, world: World, player: Player, radius: int = 4) -> set[str]:
        """玩家周围是否有工作台等「制作站点」方块。"""
        px, py = player.tile_center()
        key = (px, py)
        if key == self._station_key and self._stations_cache:
            return self._stations_cache
        found: set[str] = set()
        for ty in range(py - radius, py + radius + 1):
            for tx in range(px - radius, px + radius + 1):
                tile = world.tile_at(tx, ty)
                if tile.station:
                    found.add(tile.station)
        self._station_key = key
        self._stations_cache = found
        return found

    # --- 判定 ---------------------------------------------------------
    def available(self, recipe: Recipe, stations: set[str]) -> bool:
        if recipe.station and recipe.station not in stations:
            return False
        return self._inventory.has_all(recipe.ingredients)

    def missing(self, recipe: Recipe) -> list[tuple[str, int, int]]:
        """返回 [(物品, 需要, 拥有)]，只列不足的。"""
        result = []
        for item_id, need in recipe.ingredients:
            have = self._inventory.count(item_id)
            if have < need:
                result.append((item_id, need, have))
        return result

    def craft(self, recipe: Recipe, stations: set[str]) -> bool:
        if not self.available(recipe, stations):
            return False
        for item_id, need in recipe.ingredients:
            if not self._inventory.remove(item_id, need):
                return False
        leftover = self._inventory.add(recipe.output, recipe.count)
        if leftover > 0:
            # 背包满：退回材料，避免吞物品
            for item_id, need in recipe.ingredients:
                self._inventory.add(item_id, need)
            self._inventory.remove(recipe.output, recipe.count - leftover)
            return False
        return True
