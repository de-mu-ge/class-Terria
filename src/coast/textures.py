"""程序化贴图：地块（含湿沙变体）与物品图标，16×16 硬像素。"""

from __future__ import annotations

import random

from ..core.types import Color
from ..render.renderer import Texture
from .defs import CoastDefs

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

    def to_bytes(self) -> bytes:
        return bytes(self.data)


def _shade(color: Color, factor: float) -> Color:
    return (max(0, min(255, int(color[0] * factor))),
            max(0, min(255, int(color[1] * factor))),
            max(0, min(255, int(color[2] * factor))))


def _mix(a: Color, b: Color, t: float) -> Color:
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def _seed(text: str) -> int:
    value = 0
    for index, char in enumerate(text):
        value = (value * 131 + ord(char) + index) & 0xFFFFFFFF
    return value


VARIANT_COUNT = 3


class TileTextures:
    def __init__(self) -> None:
        self._textures: dict[str, list[Texture]] = {}

    def build(self, ctx, defs: CoastDefs) -> None:
        for tile in defs.tiles:
            if tile.key == "air":
                continue
            variants = []
            for variant in range(VARIANT_COUNT):
                data = _build_tile(f"{tile.key}#{variant}", tile.color, tile.dark,
                                   tile.pattern, wet=False)
                variants.append(ctx.renderer.create_texture(TILE_PX, TILE_PX, data))
            self._textures[tile.key] = variants
            if tile.key in ("sand", "seabed"):
                wet_variants = []
                for variant in range(VARIANT_COUNT):
                    wet = _build_tile(f"{tile.key}_wet#{variant}", tile.color, tile.dark,
                                      tile.pattern, wet=True)
                    wet_variants.append(ctx.renderer.create_texture(TILE_PX, TILE_PX, wet))
                self._textures[f"{tile.key}_wet"] = wet_variants

    def get(self, key: str, salt: int = 0) -> Texture | None:
        variants = self._textures.get(key)
        if not variants:
            return None
        return variants[salt % len(variants)] if salt else variants[0]


def _build_tile(key: str, color: Color, dark: Color, pattern: str, wet: bool) -> bytes:
    rng = random.Random(_seed(key + ("_wet" if wet else "")))
    canvas = _Canvas(TILE_PX, TILE_PX)
    base = color
    if wet:
        base = _shade(_mix(base, (90, 110, 130), 0.28), 0.92)
    light = _shade(base, 1.08)
    darker = _shade(dark, 0.92 if not wet else 0.8)

    if pattern in ("sand", "seabed"):
        canvas.rect(0, 0, TILE_PX, TILE_PX, base)
        for _ in range(26):
            x = rng.randrange(TILE_PX)
            y = rng.randrange(TILE_PX)
            canvas.px(x, y, light if rng.random() < 0.5 else darker)
        # 波纹
        for row in range(2, TILE_PX, 6):
            offset = rng.randrange(3)
            for x in range(offset, TILE_PX, 4):
                canvas.px(x, row, darker)
        if pattern == "seabed":
            for _ in range(4):
                canvas.px(rng.randrange(TILE_PX), rng.randrange(TILE_PX), (240, 236, 226))
    elif pattern in ("rock", "cliff", "reef"):
        canvas.rect(0, 0, TILE_PX, TILE_PX, base)
        for _ in range(14):
            x = rng.randrange(TILE_PX)
            y = rng.randrange(TILE_PX)
            canvas.px(x, y, darker if rng.random() < 0.62 else _shade(base, 1.14))
        # 不规则裂纹：两三条短折线
        for _ in range(3):
            x = rng.randrange(TILE_PX - 4)
            y = rng.randrange(TILE_PX - 4)
            for step in range(rng.randint(3, 6)):
                canvas.px(x, y, darker)
                x += rng.choice((-1, 1))
                y += 1
        if pattern == "cliff":
            for _ in range(2):
                x = rng.randrange(TILE_PX - 2)
                canvas.rect(x, rng.randrange(TILE_PX - 6), 1, rng.randint(3, 7), darker)
        if pattern == "reef":
            for _ in range(6):
                x = rng.randrange(TILE_PX - 3)
                y = rng.randrange(TILE_PX - 3)
                canvas.rect(x, y, 2, 2, _shade(base, 1.18))
    elif pattern == "cave":
        canvas.rect(0, 0, TILE_PX, TILE_PX, base)
        for _ in range(18):
            x = rng.randrange(TILE_PX)
            y = rng.randrange(TILE_PX)
            canvas.px(x, y, darker if rng.random() < 0.7 else _shade(base, 1.12))
        for _ in range(2):
            x = rng.randrange(TILE_PX - 3)
            y = rng.randrange(TILE_PX - 3)
            canvas.rect(x, y, 2, 1, (96, 128, 168))
    else:
        canvas.rect(0, 0, TILE_PX, TILE_PX, base)
    return canvas.to_bytes()


class ItemIcons:
    def __init__(self) -> None:
        self._textures: dict[str, Texture] = {}

    def build(self, ctx, defs: CoastDefs) -> None:
        for item in defs.items.values():
            data = _build_icon(item.icon, item.color)
            self._textures[item.id] = ctx.renderer.create_texture(TILE_PX, TILE_PX, data)

    def get(self, item_id: str) -> Texture | None:
        return self._textures.get(item_id)


def _build_icon(icon: str, color: Color) -> bytes:
    canvas = _Canvas(TILE_PX, TILE_PX)
    light = _shade(color, 1.22)
    dark = _shade(color, 0.68)
    wood = (138, 106, 69)

    if icon == "log":
        canvas.rect(2, 6, 12, 5, color)
        canvas.rect(2, 6, 12, 1, light)
        canvas.rect(2, 10, 12, 1, dark)
        canvas.px(3, 5, wood)
        canvas.px(11, 11, wood)
    elif icon == "stone":
        canvas.rect(4, 5, 8, 7, color)
        canvas.rect(5, 4, 6, 1, light)
        canvas.rect(6, 6, 2, 2, light)
        canvas.rect(9, 9, 2, 2, dark)
    elif icon == "shell":
        canvas.rect(4, 6, 8, 6, color)
        canvas.rect(5, 4, 6, 2, light)
        for x in range(5, 11, 2):
            canvas.rect(x, 6, 1, 6, _shade(color, 0.86))
    elif icon == "fiber":
        for i, x in enumerate((4, 6, 8, 10)):
            canvas.rect(x, 3 + i % 2, 2, 10 - i, color if i % 2 == 0 else light)
    elif icon == "coral":
        canvas.rect(7, 6, 2, 8, dark)
        canvas.rect(3, 4, 3, 3, color)
        canvas.rect(10, 3, 3, 3, color)
        canvas.rect(6, 2, 3, 3, light)
    elif icon == "gem":
        canvas.rect(6, 3, 4, 2, light)
        canvas.rect(5, 5, 6, 4, color)
        canvas.rect(6, 9, 4, 3, dark)
        canvas.rect(6, 5, 2, 2, (255, 255, 255))
    elif icon == "campfire":
        canvas.rect(3, 11, 10, 2, wood)
        canvas.rect(5, 9, 6, 2, _shade(wood, 0.8))
        canvas.rect(6, 4, 4, 5, (242, 166, 90))
        canvas.rect(7, 2, 2, 4, (255, 217, 160))
    elif icon == "chest":
        canvas.rect(3, 6, 10, 7, color)
        canvas.rect(3, 4, 10, 3, light)
        canvas.rect(7, 7, 2, 3, dark)
        canvas.rect(3, 6, 10, 1, dark)
    elif icon == "torch":
        canvas.rect(7, 7, 2, 7, wood)
        canvas.rect(6, 3, 4, 4, (255, 217, 160))
        canvas.rect(7, 1, 2, 3, (242, 166, 90))
    else:
        canvas.rect(4, 4, 8, 8, color)
    return canvas.to_bytes()
