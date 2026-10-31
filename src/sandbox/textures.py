"""程序化地块贴图与物品图标（16×16，硬像素，不引入外部素材）。"""

from __future__ import annotations

import random

from ..core.types import Color
from ..render.renderer import Texture
from .defs import Defs, ItemDef, TileDef

TILE_PX = 16


class _Canvas:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.data = bytearray(width * height * 4)

    def px(self, x: int, y: int, color: Color, alpha: int = 255) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        i = (y * self.width + x) * 4
        self.data[i] = color[0]
        self.data[i + 1] = color[1]
        self.data[i + 2] = color[2]
        self.data[i + 3] = alpha

    def rect(self, x: int, y: int, w: int, h: int, color: Color, alpha: int = 255) -> None:
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.px(xx, yy, color, alpha)

    def line(self, x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for i in range(steps + 1):
            self.px(
                int(round(x0 + (x1 - x0) * i / steps)),
                int(round(y0 + (y1 - y0) * i / steps)),
                color,
            )

    def to_bytes(self) -> bytes:
        return bytes(self.data)


def _shade(color: Color, factor: float) -> Color:
    return (
        max(0, min(255, int(color[0] * factor))),
        max(0, min(255, int(color[1] * factor))),
        max(0, min(255, int(color[2] * factor))),
    )


def _stable_seed(text: str) -> int:
    value = 0
    for index, char in enumerate(text):
        value = (value * 131 + ord(char) + index) & 0xFFFFFFFF
    return value


class TileTextures:
    def __init__(self) -> None:
        self.raw: dict[str, bytes] = {}
        self._textures: dict[str, Texture] = {}

    def build(self, ctx, defs: Defs) -> None:
        stone_color = defs.tile_by_key("stone").color
        for tile in defs.tiles:
            if tile.key == "air":
                continue
            data = _build_tile(tile, stone_color)
            self.raw[tile.key] = data
            self._textures[tile.key] = ctx.renderer.create_texture(TILE_PX, TILE_PX, data)

    def get(self, key: str) -> Texture | None:
        return self._textures.get(key)

    def raw_data(self, key: str) -> bytes | None:
        return self.raw.get(key)


def _build_tile(tile: TileDef, stone_color: Color) -> bytes:
    rng = random.Random(_stable_seed(tile.key))
    canvas = _Canvas(TILE_PX, TILE_PX)
    base = tile.color
    dark = _shade(base, 0.78)
    light = _shade(base, 1.12)
    pattern = tile.pattern

    if pattern in ("dirt", "grass"):
        soil = _shade((122, 90, 58), 1.0) if pattern == "grass" else base
        canvas.rect(0, 0, TILE_PX, TILE_PX, soil)
        for _ in range(28):
            x = rng.randrange(TILE_PX)
            y = rng.randrange(TILE_PX)
            canvas.px(x, y, _shade(soil, 0.82 if rng.random() < 0.5 else 1.12))
        if pattern == "grass":
            canvas.rect(0, 0, TILE_PX, 4, base)
            canvas.rect(0, 4, TILE_PX, 1, _shade(base, 0.7))
            for x in range(0, TILE_PX, 2):
                if rng.random() < 0.7:
                    canvas.px(x, 0, light)
                if rng.random() < 0.4:
                    canvas.px(x + 1, 5, _shade(base, 0.85))

    elif pattern == "stone":
        canvas.rect(0, 0, TILE_PX, TILE_PX, base)
        for _ in range(22):
            x = rng.randrange(TILE_PX - 3)
            y = rng.randrange(TILE_PX - 2)
            canvas.rect(x, y, rng.randint(1, 3), 1, _shade(base, 0.85 if rng.random() < 0.5 else 1.1))
        canvas.line(2, 12, 12, 13, dark)
        canvas.line(9, 3, 13, 8, _shade(base, 1.15))

    elif pattern == "ore":
        canvas.rect(0, 0, TILE_PX, TILE_PX, stone_color)
        for _ in range(16):
            x = rng.randrange(TILE_PX - 2)
            y = rng.randrange(TILE_PX - 2)
            canvas.rect(x, y, 2, 2, _shade(stone_color, 0.8 if rng.random() < 0.5 else 1.1))
        for _ in range(5):
            x = rng.randrange(1, TILE_PX - 3)
            y = rng.randrange(1, TILE_PX - 3)
            canvas.rect(x, y, rng.randint(2, 3), 2, base)
            canvas.px(x, y, light)

    elif pattern == "bark":
        canvas.rect(0, 0, TILE_PX, TILE_PX, base)
        for x in range(0, TILE_PX, 3):
            canvas.rect(x, 0, 1, TILE_PX, dark)
        for _ in range(10):
            canvas.px(rng.randrange(TILE_PX), rng.randrange(TILE_PX), _shade(base, 1.15))

    elif pattern == "leaves":
        canvas.rect(0, 0, TILE_PX, TILE_PX, _shade(base, 0.85), alpha=235)
        for _ in range(26):
            x = rng.randrange(TILE_PX)
            y = rng.randrange(TILE_PX)
            canvas.rect(x, y, 2, 2, base if rng.random() < 0.6 else light, alpha=245)
        for _ in range(4):
            canvas.rect(rng.randrange(TILE_PX), rng.randrange(TILE_PX), 1, 1, (0, 0, 0, 0))

    elif pattern == "planks":
        canvas.rect(0, 0, TILE_PX, TILE_PX, base)
        for y in range(0, TILE_PX, 4):
            canvas.rect(0, y, TILE_PX, 1, dark)
        for _ in range(6):
            canvas.px(rng.randrange(TILE_PX), rng.randrange(TILE_PX), _shade(base, 1.1))

    elif pattern == "brick":
        canvas.rect(0, 0, TILE_PX, TILE_PX, base)
        for y in range(0, TILE_PX, 4):
            canvas.rect(0, y, TILE_PX, 1, _shade(base, 0.62))
            offset = 0 if (y // 4) % 2 == 0 else 4
            for x in range(offset, TILE_PX, 8):
                canvas.rect(x, y, 1, 4, _shade(base, 0.62))

    elif pattern == "bench":
        canvas.rect(0, 0, TILE_PX, TILE_PX, (0, 0, 0, 0))
        canvas.rect(1, 4, 14, 3, base)
        canvas.rect(1, 4, 14, 1, light)
        canvas.rect(2, 7, 2, 7, _shade(base, 0.75))
        canvas.rect(12, 7, 2, 7, _shade(base, 0.75))
        canvas.rect(4, 8, 8, 1, _shade(base, 0.85))

    elif pattern == "torch":
        canvas.rect(0, 0, TILE_PX, TILE_PX, (0, 0, 0, 0))
        canvas.rect(7, 7, 2, 8, (107, 74, 47))
        canvas.rect(6, 4, 4, 4, (255, 217, 160))
        canvas.rect(7, 2, 2, 3, (242, 166, 90))
        canvas.px(7, 3, (255, 236, 200))

    else:
        canvas.rect(0, 0, TILE_PX, TILE_PX, base)

    return canvas.to_bytes()


class ItemIcons:
    def __init__(self) -> None:
        self._textures: dict[str, Texture] = {}

    def build(self, ctx, defs: Defs, tiles: TileTextures) -> None:
        for item in defs.items.values():
            data = self._build(item, tiles)
            self._textures[item.id] = ctx.renderer.create_texture(TILE_PX, TILE_PX, data)

    def get(self, item_id: str) -> Texture | None:
        return self._textures.get(item_id)

    def _build(self, item: ItemDef, tiles: TileTextures) -> bytes:
        if item.tile and tiles.raw_data(item.tile):
            return tiles.raw_data(item.tile) or b""
        canvas = _Canvas(TILE_PX, TILE_PX)
        base = item.color
        light = _shade(base, 1.2)
        dark = _shade(base, 0.7)
        handle = (138, 106, 69)
        icon = item.icon or ("gem" if item.kind == "material" else "chunk")

        if icon in ("pickaxe", "axe", "sword"):
            if icon == "pickaxe":
                canvas.line(3, 13, 12, 4, handle)
                canvas.line(2, 13, 4, 14, handle)
                canvas.line(6, 2, 13, 9, base)
                canvas.line(6, 2, 8, 1, light)
                canvas.line(13, 9, 14, 8, light)
            elif icon == "axe":
                canvas.line(4, 13, 11, 5, handle)
                canvas.rect(7, 2, 6, 3, base)
                canvas.rect(10, 4, 4, 4, base)
                canvas.rect(7, 2, 6, 1, light)
                canvas.rect(9, 5, 3, 2, _shade(base, 0.75))
            else:  # sword
                canvas.line(3, 13, 12, 4, base)
                canvas.line(4, 13, 13, 5, light)
                canvas.line(2, 11, 6, 15, handle)
                canvas.line(11, 3, 14, 1, _shade(base, 1.3))
        elif icon == "gem":
            canvas.rect(4, 4, 8, 8, base)
            canvas.rect(5, 3, 6, 1, light)
            canvas.rect(5, 5, 2, 2, light)
            canvas.rect(9, 9, 2, 2, dark)
            canvas.px(4, 4, dark)
        else:
            canvas.rect(4, 5, 8, 7, base)
            canvas.rect(5, 4, 6, 1, light)
            canvas.rect(5, 6, 2, 2, light)
            canvas.rect(9, 9, 2, 2, dark)
        return canvas.to_bytes()
