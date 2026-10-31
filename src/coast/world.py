"""海岸世界：地形生成（海滩 / 岩壁 / 潮间带 / 浅海 / 礁石 / 深水 / 洞穴）、潮汐、水深查询。

保存的只有「地块」；海水是算出来的 —— 水面高度由潮汐驱动，
某个格子是否在水下 = 该格是空气 且 格中心低于当前水面。
这样潮汐不用改写地图，涨落时海岸线自然变化。
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any

from .defs import CoastDefs

log = logging.getLogger(__name__)


class CoastWorld:
    def __init__(self, defs: CoastDefs) -> None:
        self.defs = defs
        self.params: dict[str, Any] = defs.world
        self.tile_size = defs.tile_size
        self.width = int(self.params.get("width_tiles", 320))
        self.height = int(self.params.get("height_tiles", 180))
        self.sea_level_base = float(self.params.get("sea_level", 96))
        tide = self.params.get("tide", {})
        self.tide_amplitude = float(tide.get("amplitude", 1.7))
        self.tide_period = max(1.0, float(tide.get("period", 150.0)))
        self.sea_level = self.sea_level_base

        self.tiles: list[int] = [defs.air_id()] * (self.width * self.height)
        self.cave_air: set[int] = set()
        self.cave_region: set[int] = set()
        self._surface = [0] * self.width
        self._random = random.Random(int(self.params.get("seed", 1)))

        self.beach_cfg = self.params.get("beach", {})
        self.cliff_cfg = self.params.get("cliff", {})
        self.ocean_cfg = self.params.get("ocean", {})
        self.cave_cfg = self.params.get("cave", {})
        self.detail_cfg = self.params.get("detail", {})

    # --- 索引与基本查询 -----------------------------------------------
    def index(self, tx: int, ty: int) -> int:
        return ty * self.width + tx

    def in_bounds(self, tx: int, ty: int) -> bool:
        return 0 <= tx < self.width and 0 <= ty < self.height

    def id_at(self, tx: int, ty: int) -> int:
        if not self.in_bounds(tx, ty):
            key = "rock" if ty >= self.height else "air"
            return self.defs.tile_by_key(key).id
        return self.tiles[ty * self.width + tx]

    def tile_key(self, tx: int, ty: int) -> str:
        return self.defs.tile_by_id(self.id_at(tx, ty)).key

    def is_solid(self, tx: int, ty: int) -> bool:
        return self.defs.tile_by_id(self.id_at(tx, ty)).solid

    def surface_y(self, tx: int) -> int:
        return self._surface[max(0, min(self.width - 1, tx))]

    def is_cave(self, tx: int, ty: int) -> bool:
        return self.in_bounds(tx, ty) and self.index(tx, ty) in self.cave_air

    # --- 潮汐 / 水体 --------------------------------------------------
    def update_tide(self, elapsed: float) -> None:
        phase = elapsed / self.tide_period * math.tau
        self.sea_level = self.sea_level_base + math.sin(phase) * self.tide_amplitude

    @property
    def sea_level_y(self) -> float:
        """水面在世界坐标里的 y（像素，格边界）。"""
        return self.sea_level * self.tile_size

    def is_underwater(self, tx: int, ty: int) -> bool:
        if self.is_solid(tx, ty):
            return False
        return (ty + 0.5) >= self.sea_level

    def depth_at(self, tx: int, ty: int) -> float:
        """该格的水深（格）；正数表示水下，0 表示露出水面。"""
        if self.is_solid(tx, ty):
            return 0.0
        return max(0.0, (ty + 0.5) - self.sea_level)

    def zone_at(self, tx: int, ty: int) -> str:
        if self.is_cave(tx, ty):
            return "cave"
        if self.is_solid(tx, ty):
            return "solid"
        depth = self.depth_at(tx, ty)
        if depth <= 0.0:
            return "beach" if tx < int(self.beach_cfg.get("end", 132)) else "coast"
        reef_start = int(self.ocean_cfg.get("reef_start", 186))
        reef_end = int(self.ocean_cfg.get("reef_end", 246))
        if reef_start <= tx <= reef_end and depth <= 22:
            return "reef"
        if depth <= 3.5:
            return "intertidal"
        if depth <= 14:
            return "shallow"
        if depth <= 30:
            return "seabed"
        return "deep"

    # --- 生成 ---------------------------------------------------------
    def generate(self) -> None:
        self._generate_terrain()
        self._carve_cave()
        self._recompute_surface()
        log.info("海岸世界生成完成：%dx%d 格，海平面 %.1f，洞穴空腔 %d 格",
                 self.width, self.height, self.sea_level_base, len(self.cave_air))

    def _generate_terrain(self) -> None:
        sand = self.defs.tile_by_key("sand").id
        seabed = self.defs.tile_by_key("seabed").id
        rock = self.defs.tile_by_key("rock").id
        cliff = self.defs.tile_by_key("cliff").id
        reef = self.defs.tile_by_key("reef").id

        cliff_end = int(self.cliff_cfg.get("end", 46))
        cliff_top = float(self.cliff_cfg.get("top", 72))
        beach_start = int(self.beach_cfg.get("start", 46))
        beach_end = int(self.beach_cfg.get("end", 132))
        beach_height = float(self.beach_cfg.get("height", 92))
        floor_shore = float(self.ocean_cfg.get("floor_at_shore", 102))
        floor_deep = float(self.ocean_cfg.get("floor_at_deep", 168))
        slope_power = float(self.ocean_cfg.get("slope_power", 1.35))
        reef_start = int(self.ocean_cfg.get("reef_start", 186))
        reef_end = int(self.ocean_cfg.get("reef_end", 246))
        reef_height = float(self.ocean_cfg.get("reef_height", 6))
        noise_scale = float(self.detail_cfg.get("noise_scale", 0.055))
        noise_amp = float(self.detail_cfg.get("noise_amplitude", 3.2))
        fine_scale = float(self.detail_cfg.get("fine_scale", 0.19))
        fine_amp = float(self.detail_cfg.get("fine_amplitude", 1.1))

        for tx in range(self.width):
            coarse = _value_noise(tx * noise_scale, 11) * noise_amp
            fine = _value_noise(tx * fine_scale, 29) * fine_amp

            if tx < cliff_end:
                # 岩壁高地：从崖顶一直实心到底
                top = int(round(cliff_top + coarse))
                for ty in range(top, self.height):
                    self.tiles[self.index(tx, ty)] = cliff
            elif tx < beach_end:
                # 沙滩：平缓下降，靠近水面更湿更低
                t = (tx - beach_start) / max(1, beach_end - beach_start)
                top = int(round(beach_height - 2.5 * t + coarse * 0.55 + fine * 0.6))
                sand_depth = 16 + int(abs(coarse) * 2.4) + int(abs(fine) * 2.0)
                for ty in range(top, self.height):
                    if ty <= top + sand_depth:
                        self.tiles[self.index(tx, ty)] = sand
                    else:
                        self.tiles[self.index(tx, ty)] = rock
            else:
                # 海底：从岸边向外逐渐变深，礁石区抬升
                t = (tx - beach_end) / max(1, self.width - beach_end)
                floor = floor_shore + (floor_deep - floor_shore) * (t ** slope_power)
                if reef_start <= tx <= reef_end:
                    span = max(1, reef_end - reef_start)
                    local = (tx - reef_start) / span
                    floor -= math.sin(local * math.pi) * reef_height
                floor += coarse * 0.7 + fine * 0.5
                top = int(round(floor))
                top_layer = 6 + int(abs(coarse) * 1.2) + int(abs(fine))
                for ty in range(top, self.height):
                    if ty <= top + top_layer:
                        self.tiles[self.index(tx, ty)] = seabed
                    elif reef_start <= tx <= reef_end and ty <= top + top_layer + 3:
                        self.tiles[self.index(tx, ty)] = reef
                    else:
                        self.tiles[self.index(tx, ty)] = rock

    def _carve_cave(self) -> None:
        cfg = self.cave_cfg
        mouth_x = int(cfg.get("mouth_x", 32))
        mouth_y = int(cfg.get("mouth_y", 84))
        depth = int(cfg.get("depth", 16))
        chamber_radius = int(cfg.get("chamber_radius", 7))
        cliff_end = int(self.cliff_cfg.get("end", 46))
        cave_rock = self.defs.tile_by_key("cave").id

        # 从崖壁外沿（沙滩一侧）开口，向岩体内部水平进入，再向下折进洞厅
        start_x = cliff_end - 1
        self._carve_capsule(start_x, mouth_y, mouth_x, mouth_y + 2, 2)
        self._carve_capsule(mouth_x, mouth_y + 2, mouth_x - 8, mouth_y + 8, 2)
        self._carve_capsule(mouth_x - 8, mouth_y + 8, mouth_x - 4, mouth_y + depth, 2)
        chamber_x = mouth_x - 4
        chamber_y = mouth_y + depth
        self._carve_disc(chamber_x, chamber_y, chamber_radius)
        # 支洞：通向晶簇区
        self._carve_capsule(chamber_x + 2, chamber_y + 2, chamber_x + 12, chamber_y + 7, 2)
        self._carve_disc(chamber_x + 12, chamber_y + 7, 4)

        # 紧邻空腔的实心格换成「洞穴岩壁」，洞穴内部氛围才统一
        border: set[int] = set()
        for idx in list(self.cave_air):
            tx, ty = idx % self.width, idx // self.width
            for dy in (-2, -1, 1, 2):
                for dx in (-2, -1, 1, 2):
                    nx, ny = tx + dx, ty + dy
                    if not self.in_bounds(nx, ny):
                        continue
                    nidx = self.index(nx, ny)
                    if nidx in self.cave_air:
                        continue
                    if self.defs.tile_by_id(self.tiles[nidx]).solid:
                        border.add(nidx)
        self.cave_region = set(self.cave_air)
        for idx in border:
            self.tiles[idx] = cave_rock
            self.cave_region.add(idx)

    def _carve_capsule(self, x0: int, y0: int, x1: int, y1: int, radius: int) -> None:
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for i in range(steps + 1):
            tx = int(round(x0 + (x1 - x0) * i / steps))
            ty = int(round(y0 + (y1 - y0) * i / steps))
            self._carve_disc(tx, ty, radius)

    def _carve_disc(self, cx: int, cy: int, radius: int) -> None:
        air = self.defs.air_id()
        for ty in range(cy - radius, cy + radius + 1):
            for tx in range(cx - radius, cx + radius + 1):
                if not self.in_bounds(tx, ty):
                    continue
                if (tx - cx) ** 2 + (ty - cy) ** 2 > radius * radius:
                    continue
                idx = self.index(tx, ty)
                self.tiles[idx] = air
                self.cave_air.add(idx)

    def _recompute_surface(self) -> None:
        for tx in range(self.width):
            found = self.height - 1
            for ty in range(self.height):
                if self.defs.tile_by_id(self.tiles[self.index(tx, ty)]).solid:
                    found = ty
                    break
            self._surface[tx] = found

    # --- 工具 ---------------------------------------------------------
    def solid_surface_below(self, tx: int, from_ty: int) -> int | None:
        for ty in range(max(0, from_ty), self.height):
            if self.is_solid(tx, ty):
                return ty
        return None

    def air_above(self, tx: int, ty: int, count: int = 2) -> bool:
        for offset in range(1, count + 1):
            if self.is_solid(tx, ty - offset):
                return False
        return True


def _value_noise(x: float, seed: int) -> float:
    """一维平滑值噪声，返回 -1..1。"""
    xi = int(math.floor(x))
    frac = x - xi

    def h(n: int) -> float:
        n = (n * 374761393 + seed * 668265263) & 0xFFFFFFFF
        n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 0xFFFF) / 32767.5 - 1.0

    smooth = frac * frac * (3 - 2 * frac)
    return h(xi) * (1 - smooth) + h(xi + 1) * smooth
