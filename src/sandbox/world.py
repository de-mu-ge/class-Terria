"""地块世界：生成、读写、光照。

坐标：地块（tile）为整数格，1 格 = 16px；世界尺寸与生成参数在 data/world.json。
光照用「天空光 + 火把」BFS 扩散，结果缓存在 light 数组里，只有改动地形才重算。
"""

from __future__ import annotations

import json
import logging
import random
from collections import deque
from pathlib import Path
from typing import Any

from .defs import Defs

log = logging.getLogger(__name__)


def load_world_params(data_root: Path) -> dict[str, Any]:
    path = data_root / "world.json"
    if not path.is_file():
        raise FileNotFoundError(f"缺少世界生成参数：{path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


class World:
    def __init__(self, defs: Defs, params: dict[str, Any]) -> None:
        self.defs = defs
        self.params = params
        self.width = int(params.get("width_tiles", 256))
        self.height = int(params.get("height_tiles", 160))
        self.tile_size = defs.tile_size
        self._random = random.Random(int(params.get("seed", 1)))
        self.tiles: list[int] = [defs.air_id()] * (self.width * self.height)
        light_cfg = params.get("light", {})
        self.light_max = int(light_cfg.get("max", 15))
        self.air_decay = int(light_cfg.get("air_decay", 1))
        self.solid_decay = int(light_cfg.get("solid_decay", 3))
        self.light: list[int] = [0] * (self.width * self.height)
        self.light_dirty = True
        self._surface: list[int] = [0] * self.width

    # --- 索引 ---------------------------------------------------------
    def index(self, tx: int, ty: int) -> int:
        return ty * self.width + tx

    def in_bounds(self, tx: int, ty: int) -> bool:
        return 0 <= tx < self.width and 0 <= ty < self.height

    def id_at(self, tx: int, ty: int) -> int:
        if not self.in_bounds(tx, ty):
            return self.defs.tile_by_key("stone").id  # 边界当实心墙
        return self.tiles[ty * self.width + tx]

    def tile_at(self, tx: int, ty: int):
        return self.defs.tile_by_id(self.id_at(tx, ty))

    def is_solid(self, tx: int, ty: int) -> bool:
        return self.defs.tile_by_id(self.id_at(tx, ty)).solid

    def surface_y(self, tx: int) -> int:
        return self._surface[max(0, min(self.width - 1, tx))]

    def set_tile(self, tx: int, ty: int, key: str) -> None:
        if not self.in_bounds(tx, ty):
            return
        self.tiles[ty * self.width + tx] = self.defs.tile_by_key(key).id
        self.light_dirty = True

    # --- 生成 ---------------------------------------------------------
    def generate(self) -> None:
        defs = self.defs
        grass = defs.tile_by_key("grass").id
        dirt = defs.tile_by_key("dirt").id
        stone = defs.tile_by_key("stone").id

        surface_cfg = self.params.get("surface", {})
        base = float(surface_cfg.get("base_height", 58))
        amp = float(surface_cfg.get("amplitude", 7))
        noise_scale = float(surface_cfg.get("noise_scale", 0.035))
        detail_scale = float(surface_cfg.get("detail_scale", 0.11))
        detail_amp = float(surface_cfg.get("detail_amplitude", 2))
        layer_cfg = self.params.get("layers", {})
        dirt_min = int(layer_cfg.get("dirt_min", 5))
        dirt_max = int(layer_cfg.get("dirt_max", 11))

        for tx in range(self.width):
            height = (base
                      + _value_noise(tx * noise_scale, rng_seed=self.params.get("noise_seed", 7)) * amp
                      + _value_noise(tx * detail_scale, rng_seed=13) * detail_amp)
            sy = max(8, min(self.height - 20, int(height)))
            self._surface[tx] = sy
            self.tiles[self.index(tx, sy)] = grass
            dirt_depth = dirt_min + int(_value_noise(tx * 0.21, rng_seed=23) * (dirt_max - dirt_min))
            for ty in range(sy + 1, self.height):
                if ty <= sy + dirt_depth:
                    self.tiles[self.index(tx, ty)] = dirt
                else:
                    self.tiles[self.index(tx, ty)] = stone

        self._carve_caves()
        self._scatter_ores()
        self._grow_trees()
        self._clear_spawn()
        self._recompute_surface()
        self.light_dirty = True
        self.rebuild_light()
        log.info("世界生成完成：%dx%d 格，种子 %s", self.width, self.height,
                 self.params.get("seed"))

    def _carve_caves(self) -> None:
        cfg = self.params.get("caves", {})
        count = int(cfg.get("count", 40))
        rmin = int(cfg.get("radius_min", 3))
        rmax = int(cfg.get("radius_max", 9))
        min_depth = int(cfg.get("min_depth", 12))
        max_depth = int(cfg.get("max_depth", 150))
        rng = self._random
        air = self.defs.air_id()
        directions = [(1, 0), (1, 1), (1, -1), (0, 1), (-1, 1), (-1, -1)]
        for _ in range(count):
            tx = rng.randrange(4, self.width - 4)
            min_y = self._surface[tx] + min_depth
            max_y = min(self.height - 4, self._surface[tx] + max_depth)
            if max_y <= min_y:
                continue
            ty = rng.randrange(min_y, max_y)
            radius = rng.uniform(rmin, rmax)
            dx, dy = rng.choice(directions)
            steps_cfg = cfg.get("steps", [4, 8])
            for _ in range(rng.randint(int(steps_cfg[0]), int(steps_cfg[1]))):
                rx = max(1, int(radius * rng.uniform(0.8, 1.25)))
                ry = max(1, int(radius * rng.uniform(0.55, 0.95)))
                self._carve_ellipse(tx, ty, rx, ry, air)
                step = max(2, int(radius * 0.8))
                tx += dx * step + rng.randint(-1, 1)
                ty += dy * step + rng.randint(-1, 1)
                tx = max(3, min(self.width - 4, tx))
                ty = max(self._surface[tx] + 3, min(self.height - 4, ty))
                if rng.random() < 0.35:
                    dx, dy = rng.choice(directions)

    def _carve_ellipse(self, cx: int, cy: int, rx: int, ry: int, air: int) -> None:
        for ty in range(cy - ry, cy + ry + 1):
            for tx in range(cx - rx, cx + rx + 1):
                if not self.in_bounds(tx, ty):
                    continue
                dx = (tx - cx) / max(1, rx)
                dy = (ty - cy) / max(1, ry)
                if dx * dx + dy * dy <= 1.0:
                    # 不挖穿地表：保留最上面几格
                    if ty <= self._surface[tx] + 1:
                        continue
                    self.tiles[self.index(tx, ty)] = air

    def _scatter_ores(self) -> None:
        rng = self._random
        for entry in self.params.get("ores", []):
            key = entry["tile"]
            tile_id = self.defs.tile_by_key(key).id
            count = int(entry.get("count", 60))
            rmin, rmax = entry.get("radius", [1, 2])
            dmin, dmax = entry.get("depth", [4, 60])
            for _ in range(count):
                tx = rng.randrange(2, self.width - 2)
                ty = self._surface[tx] + rng.randint(int(dmin), int(dmax))
                if not self.in_bounds(tx, ty) or ty >= self.height - 2:
                    continue
                radius = rng.randint(int(rmin), int(rmax))
                for oy in range(ty - radius, ty + radius + 1):
                    for ox in range(tx - radius, tx + radius + 1):
                        if not self.in_bounds(ox, oy):
                            continue
                        if (ox - tx) ** 2 + (oy - ty) ** 2 > radius * radius:
                            continue
                        current = self.defs.tile_by_id(self.tiles[self.index(ox, oy)])
                        if current.key in ("stone", "dirt"):
                            self.tiles[self.index(ox, oy)] = tile_id

    def _grow_trees(self) -> None:
        cfg = self.params.get("trees", {})
        spacing_min, spacing_max = cfg.get("spacing", [5, 14])
        height_min, height_max = cfg.get("height", [5, 9])
        canopy = int(cfg.get("canopy_radius", 2))
        trunk = self.defs.tile_by_key(cfg.get("trunk_tile", "trunk")).id
        leaves = self.defs.tile_by_key(cfg.get("leaf_tile", "leaves")).id
        grass = self.defs.tile_by_key("grass").id
        air = self.defs.air_id()
        rng = self._random
        tx = 4
        while tx < self.width - 4:
            tx += rng.randint(int(spacing_min), int(spacing_max))
            if tx >= self.width - 4:
                break
            sy = self._surface[tx]
            if self.tiles[self.index(tx, sy)] != grass:
                continue
            # 地面要平一点，避免树悬空
            if abs(self._surface[tx] - self._surface[tx - 1]) > 2:
                continue
            height = rng.randint(int(height_min), int(height_max))
            top = sy - height
            if top < 4:
                continue
            for ty in range(sy - 1, top - 1, -1):
                self.tiles[self.index(tx, ty)] = trunk
            # 树冠
            for oy in range(top - canopy - 1, top + 1):
                for ox in range(tx - canopy, tx + canopy + 1):
                    if not self.in_bounds(ox, oy):
                        continue
                    dist = abs(ox - tx) + abs(oy - top)
                    if dist > canopy + 1:
                        continue
                    if rng.random() < 0.12 and dist > 1:
                        continue
                    if self.tiles[self.index(ox, oy)] == air:
                        self.tiles[self.index(ox, oy)] = leaves

    def _clear_spawn(self) -> None:
        cfg = self.params.get("player", {})
        tx = int(self.width * float(cfg.get("spawn_x_ratio", 0.5)))
        clear = int(cfg.get("spawn_clear_tiles", 4))
        air = self.defs.air_id()
        sy = self._surface[tx]
        for ox in range(tx - 3, tx + 4):
            if not self.in_bounds(ox, sy):
                continue
            for oy in range(sy - clear - 1, sy):
                self.tiles[self.index(ox, oy)] = air
            # 清掉树干/树叶，避免出生点卡住
            for oy in range(sy - clear * 3, sy - clear):
                if self.in_bounds(ox, oy):
                    tile = self.defs.tile_by_id(self.tiles[self.index(ox, oy)])
                    if tile.key in ("trunk", "leaves"):
                        self.tiles[self.index(ox, oy)] = air

    def _recompute_surface(self) -> None:
        for tx in range(self.width):
            for ty in range(self.height):
                if self.defs.tile_by_id(self.tiles[self.index(tx, ty)]).solid:
                    self._surface[tx] = ty
                    break

    # --- 光照 ---------------------------------------------------------
    def rebuild_light(self) -> None:
        width, height = self.width, self.height
        light = self.light
        for i in range(len(light)):
            light[i] = 0
        queue: deque[tuple[int, int]] = deque()

        for tx in range(width):
            for ty in range(height):
                idx = ty * width + tx
                tile = self.defs.tile_by_id(self.tiles[idx])
                if tile.solid:
                    break
                light[idx] = self.light_max
                queue.append((tx, ty))
        for tx in range(width):
            for ty in range(height):
                idx = ty * width + tx
                tile = self.defs.tile_by_id(self.tiles[idx])
                if tile.light > 0:
                    value = min(self.light_max, tile.light)
                    if light[idx] < value:
                        light[idx] = value
                        queue.append((tx, ty))

        while queue:
            tx, ty = queue.popleft()
            current = light[ty * width + tx]
            if current <= 1:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = tx + dx, ty + dy
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                nidx = ny * width + nx
                tile = self.defs.tile_by_id(self.tiles[nidx])
                decay = self.solid_decay if tile.solid else self.air_decay
                value = current - decay
                if value > light[nidx]:
                    light[nidx] = value
                    queue.append((nx, ny))
        self.light_dirty = False

    def light_at(self, tx: int, ty: int) -> int:
        if not self.in_bounds(tx, ty):
            return 0
        return self.light[ty * self.width + tx]

    def ensure_light(self) -> None:
        if self.light_dirty:
            self.rebuild_light()


def _value_noise(x: float, rng_seed: int = 0) -> float:
    """一维平滑值噪声，返回 -1..1。"""
    import math

    xi = int(math.floor(x))
    frac = x - xi

    def h(n: int) -> float:
        n = (n * 374761393 + rng_seed * 668265263) & 0xFFFFFFFF
        n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 0xFFFF) / 32767.5 - 1.0

    smooth = frac * frac * (3 - 2 * frac)
    return h(xi) * (1 - smooth) + h(xi + 1) * smooth
