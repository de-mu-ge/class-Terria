"""海岸生态对象与生物：可采集物、鱼群、海鸟、蟹，以及它们的程序化绘制。

道具用图元直接画（不是贴图），这样才能做摆动、火焰闪烁这类动态；
坐标一律是「世界像素」，绘制时由场景传入相机偏移。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from ..core.types import Color, Rect, dim
from ..render.renderer import Renderer
from .defs import CoastDefs, ObjectDef


# --- 可交互对象 -----------------------------------------------------------
@dataclass
class Prop:
    obj_id: str
    x: float
    y: float
    phase: float = 0.0
    harvested: bool = False
    lit: bool = True
    storage: list = field(default_factory=list)

    @property
    def bottom(self) -> tuple[float, float]:
        return (self.x, self.y)


class PropWorld:
    def __init__(self, defs: CoastDefs) -> None:
        self._defs = defs
        self.props: list[Prop] = []

    def add(self, obj_id: str, x: float, y: float) -> Prop:
        prop = Prop(obj_id=obj_id, x=x, y=y, phase=random.uniform(0, math.tau))
        self.props.append(prop)
        return prop

    def active(self) -> list[Prop]:
        return [prop for prop in self.props if not prop.harvested]

    def nearest(self, wx: float, wy: float, radius: float) -> Prop | None:
        best: Prop | None = None
        best_dist = radius * radius
        for prop in self.props:
            if prop.harvested:
                continue
            dx = prop.x - wx
            dy = prop.y - wy
            dist = dx * dx + dy * dy
            if dist < best_dist:
                best = prop
                best_dist = dist
        return best

    def lights(self) -> list[tuple[float, float, float]]:
        """返回发光对象的 (x, y, 强度)。"""
        result = []
        for prop in self.props:
            if prop.harvested:
                continue
            obj = self._defs.obj(prop.obj_id)
            if obj.light <= 0:
                continue
            if obj.id in ("campfire", "torch") and not prop.lit:
                continue
            result.append((prop.x, prop.y, float(obj.light)))
        return result


# --- 生物 -----------------------------------------------------------------
@dataclass
class FishSchool:
    x: float
    y: float
    radius: float
    count: int
    speed: float
    phase: float = 0.0
    direction: int = 1
    fish: list[tuple[float, float, float]] = field(default_factory=list)  # 相对位置 + 相位

    def __post_init__(self) -> None:
        if not self.fish:
            rng = random.Random(int(self.x * 31 + self.y * 17))
            for _ in range(self.count):
                angle = rng.uniform(0, math.tau)
                dist = rng.uniform(0.2, 1.0) * self.radius
                self.fish.append((math.cos(angle) * dist, math.sin(angle) * dist * 0.55,
                                  rng.uniform(0, math.tau)))

    def update(self, dt: float, player_x: float, player_y: float) -> None:
        self.phase += dt
        self.x += self.speed * self.direction * dt
        dx = self.x - player_x
        dy = self.y - player_y
        if dx * dx + dy * dy < 90 * 90:
            self.direction = -1 if dx > 0 else 1
        if self.phase > 6.0:
            self.phase = 0.0
            if random.random() < 0.35:
                self.direction *= -1

    def draw(self, renderer: Renderer, cam: tuple[float, float], color: Color,
             alpha: int = 255) -> None:
        for ox, oy, phase in self.fish:
            wobble = math.sin(self.phase * 2.0 + phase) * 3.0
            sx = self.x + ox + cam[0] - 4
            sy = self.y + oy + wobble + cam[1] - 2
            renderer.draw_rect(Rect(sx, sy, 6, 3), color, alpha=alpha)
            tail = sx + 6 if self.direction > 0 else sx - 2
            renderer.draw_rect(Rect(tail, sy + 1, 2, 2), dim(color, 0.8), alpha=alpha)


@dataclass
class Bird:
    x: float
    y: float
    speed: float
    phase: float = 0.0
    direction: int = 1
    span: float = 900.0

    def update(self, dt: float, world_width: float) -> None:
        self.phase += dt
        self.x += self.speed * self.direction * dt
        if self.x > self.span:
            self.x = -40
        elif self.x < -60:
            self.x = self.span
        self.y += math.sin(self.phase * 0.8) * 6 * dt

    def draw(self, renderer: Renderer, cam: tuple[float, float], color: Color) -> None:
        flap = math.sin(self.phase * 6.0)
        sx = self.x + cam[0]
        sy = self.y + cam[1]
        wing = 5 * flap
        renderer.draw_line((sx - 4, sy + wing), (sx, sy), color, width=1)
        renderer.draw_line((sx, sy), (sx + 4, sy + wing), color, width=1)


@dataclass
class Crab:
    x: float
    y: float
    speed: float
    direction: int = 1
    pause: float = 0.0
    phase: float = 0.0

    def update(self, dt: float, world) -> None:
        self.phase += dt
        if self.pause > 0:
            self.pause -= dt
            return
        self.x += self.speed * self.direction * dt
        tx = int(self.x // world.tile_size)
        ty = int(self.y // world.tile_size)
        if not world.is_solid(tx, ty) or world.is_underwater(tx, ty - 1):
            self.direction *= -1
            self.x += self.speed * self.direction * dt * 3
        if random.random() < dt * 0.6:
            self.pause = random.uniform(0.4, 1.4)

    def draw(self, renderer: Renderer, cam: tuple[float, float], color: Color) -> None:
        sx = self.x + cam[0]
        sy = self.y + cam[1]
        body = Rect(sx - 4, sy - 4, 8, 4)
        renderer.draw_rect(body, color)
        wiggle = 1 if math.sin(self.phase * 6) > 0 else 0
        for i in range(3):
            renderer.draw_line((sx - 4 + i * 3, sy - 1), (sx - 5 + i * 3, sy + 1 + wiggle),
                               dim(color, 0.75), width=1)
        renderer.draw_rect(Rect(sx - 5, sy - 6, 1, 2), dim(color, 0.8))
        renderer.draw_rect(Rect(sx + 4, sy - 6, 1, 2), dim(color, 0.8))


# --- 对象绘制 -------------------------------------------------------------
def draw_prop(renderer: Renderer, prop: Prop, obj: ObjectDef, time: float,
              cam: tuple[float, float]) -> None:
    if prop.harvested:
        return
    sx = prop.x + cam[0]
    sy = prop.y + cam[1]
    color = obj.color
    accent = obj.accent
    w, h = obj.size

    if obj.id == "driftwood":
        renderer.draw_round_rect(Rect(sx - w / 2, sy - h, w, h), color, 3)
        renderer.draw_round_rect(Rect(sx - w / 2, sy - h, w, h // 2), accent, 3, alpha=120)
        renderer.draw_line((sx + 4, sy - h), (sx + 10, sy - h - 6), color, width=2)
        renderer.draw_line((sx - 6, sy - h + 2), (sx - 12, sy - h - 4), color, width=2)

    elif obj.id == "stone_small":
        renderer.draw_polygon([(sx - w / 2, sy), (sx - w / 2 + 3, sy - h),
                               (sx + w / 2 - 4, sy - h + 1), (sx + w / 2, sy)],
                              color)
        renderer.draw_line((sx - 3, sy - h + 2), (sx + 2, sy - h + 3), accent, width=1)

    elif obj.id == "shell":
        renderer.draw_polygon([(sx - w / 2, sy), (sx, sy - h), (sx + w / 2, sy)], color)
        renderer.draw_line((sx, sy - h + 1), (sx, sy - 1), accent, width=1)
        renderer.draw_line((sx - 3, sy - 2), (sx, sy - h + 2), accent, width=1)
        renderer.draw_line((sx + 3, sy - 2), (sx, sy - h + 2), accent, width=1)

    elif obj.id in ("seagrass", "kelp"):
        blades = 5 if obj.id == "seagrass" else 3
        amp = 3.0 * obj.sway
        for i in range(blades):
            base_x = sx + (i - blades / 2) * 3.2
            sway = math.sin(time * 1.6 + prop.phase + i * 0.7) * amp
            top_x = base_x + sway
            top_y = sy - h * (0.7 + 0.3 * ((i % 3) / 2))
            renderer.draw_polygon([(base_x - 1.4, sy), (base_x + 1.4, sy),
                                   (top_x + 1.1, top_y), (top_x - 1.1, top_y)],
                                  color if i % 2 == 0 else accent, alpha=235)

    elif obj.id == "coral":
        renderer.draw_rect(Rect(sx - 2, sy - h * 0.6, 4, h * 0.6), color)
        for i, (dx, up) in enumerate(((-6, 8), (6, 10), (0, 12))):
            tip_x = sx + dx + math.sin(time * 0.9 + i) * 1.2
            tip_y = sy - h * 0.6 - up
            renderer.draw_line((sx, sy - h * 0.5), (tip_x, tip_y),
                               accent if i == 1 else color, width=3)
            renderer.draw_round_rect(Rect(tip_x - 2, tip_y - 3, 4, 4), accent, 2, alpha=210)

    elif obj.id == "crystal":
        glow = 0.6 + 0.4 * math.sin(time * 2.2 + prop.phase)
        for i, (dx, height) in enumerate(((-4, 12), (2, 18), (6, 10))):
            base_x = sx + dx
            renderer.draw_polygon([(base_x - 3, sy), (base_x, sy - height),
                                   (base_x + 3, sy)], color, alpha=235)
            renderer.draw_line((base_x, sy - height), (base_x, sy - 2), accent, width=1)
        renderer.draw_round_rect(Rect(sx - 10, sy - 20, 20, 20), accent, 10,
                                 alpha=int(40 * glow))

    elif obj.id == "campfire":
        # 石圈 + 木柴 + 火焰
        for i in range(6):
            angle = i / 6 * math.tau
            px = sx + math.cos(angle) * 10
            py = sy + math.sin(angle) * 3 - 2
            renderer.draw_round_rect(Rect(px - 2, py - 2, 4, 3), dim(color, 0.85), 1)
        renderer.draw_line((sx - 7, sy - 3), (sx + 7, sy - 5), color, width=2)
        renderer.draw_line((sx - 7, sy - 5), (sx + 7, sy - 3), color, width=2)
        if prop.lit:
            flicker = 1.0 + 0.18 * math.sin(time * 11 + prop.phase)
            flame_h = 12 * flicker
            renderer.draw_polygon([(sx - 5, sy - 5), (sx, sy - 5 - flame_h),
                                   (sx + 5, sy - 5)], accent, alpha=225)
            renderer.draw_polygon([(sx - 2.5, sy - 5), (sx + 1, sy - 5 - flame_h * 0.62),
                                   (sx + 2.5, sy - 5)], (255, 236, 200), alpha=225)

    elif obj.id == "chest":
        renderer.draw_rect(Rect(sx - w / 2, sy - h, w, h), color)
        renderer.draw_rect(Rect(sx - w / 2, sy - h, w, 5), accent, alpha=210)
        renderer.draw_rect(Rect(sx - w / 2, sy - h, w, 1), dim(color, 1.2))
        renderer.draw_rect(Rect(sx - 2, sy - h + 5, 4, 5), accent)

    elif obj.id == "torch":
        renderer.draw_rect(Rect(sx - 2, sy - h, 4, h), color)
        if prop.lit:
            flicker = 1.0 + 0.25 * math.sin(time * 12 + prop.phase)
            renderer.draw_round_rect(Rect(sx - 4, sy - h - 6 * flicker, 8, 7), accent, 3,
                                     alpha=235)
            renderer.draw_round_rect(Rect(sx - 2, sy - h - 9 * flicker, 4, 4), (255, 240, 210),
                                     2, alpha=220)
