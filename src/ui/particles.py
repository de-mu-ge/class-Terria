"""粒子演出：樱花花瓣 / 雨丝 / 雾团 / 浪花。

剧情文档里点名的两处：
- Scene 01「数片樱花花瓣从镜头前缓缓飘过」
- Scene 02 结尾「樱花花瓣从画面前方飘过」
其余（雨丝、雾团、浪花）服务于 Scene 05/06/07 的天气与海岸氛围。

参数全部来自 data/config.json 的 particles 段；绘制只用 Renderer 图元，不碰后端。
随机数用固定种子，保证同一画面可复现（截图比对需要）。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from ..core.context import SceneContext
from ..core.timeline import clamp01
from ..core.types import Color, Rect, parse_color
from ..render.renderer import Renderer


def _range(spec, rng: random.Random, default: tuple[float, float]) -> float:
    if isinstance(spec, (int, float)):
        return float(spec)
    if isinstance(spec, (list, tuple)) and len(spec) >= 2:
        return rng.uniform(float(spec[0]), float(spec[1]))
    return rng.uniform(*default)


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    size: float
    alpha: float
    phase: float
    sway_amp: float = 0.0
    sway_hz: float = 0.0
    spin: float = 0.0
    color: Color = (255, 255, 255)
    life: float = 0.0


@dataclass
class ParticlePreset:
    kind: str
    count: int
    colors: list[Color]
    spawn_y: tuple[float, float]
    velocity_x: tuple[float, float]
    velocity_y: tuple[float, float]
    size: tuple[float, float]
    alpha: tuple[float, float]
    sway_amplitude: tuple[float, float] = (0.0, 0.0)
    sway_frequency: tuple[float, float] = (0.0, 0.0)
    spin: tuple[float, float] = (0.0, 0.0)
    area: tuple[float, float] | None = None
    seed: int = 0
    label: str = ""


class ParticleField:
    def __init__(self, ctx: SceneContext, preset_name: str) -> None:
        self._ctx = ctx
        self.name = preset_name
        config = ctx.config.value("particles", "presets", preset_name, default=None)
        if not isinstance(config, dict):
            raise ValueError(f"未定义的粒子预设：{preset_name}")
        self.preset = self._parse(config, preset_name)
        self._rng = random.Random(self.preset.seed)
        self._particles: list[Particle] = []
        self._alpha = 0.0
        self._target = 1.0
        self._fade_speed = 1.4
        for _ in range(self.preset.count):
            self._particles.append(self._spawn(initial=True))

    # --- 解析 ---------------------------------------------------------
    def _parse(self, config: dict, name: str) -> ParticlePreset:
        width, height = self._ctx.renderer.size
        spawn = config.get("spawn_y", [-40, 0])
        area = config.get("area")
        return ParticlePreset(
            kind=str(config.get("type", "petal")),
            count=int(config.get("count", 24)),
            colors=[parse_color(c) for c in config.get("colors", ["#FFFFFF"])],
            spawn_y=(float(spawn[0]), float(spawn[1])),
            velocity_x=(float(config.get("velocity_x", [-10, 10])[0]),
                        float(config.get("velocity_x", [-10, 10])[1])),
            velocity_y=(float(config.get("velocity_y", [20, 40])[0]),
                        float(config.get("velocity_y", [20, 40])[1])),
            size=(float(config.get("size", [3, 6])[0]), float(config.get("size", [3, 6])[1])),
            alpha=(float(config.get("alpha", [140, 220])[0]), float(config.get("alpha", [140, 220])[1])),
            sway_amplitude=(float(config.get("sway_amplitude", [0, 0])[0]),
                            float(config.get("sway_amplitude", [0, 0])[1])),
            sway_frequency=(float(config.get("sway_frequency", [0, 0])[0]),
                            float(config.get("sway_frequency", [0, 0])[1])),
            spin=(float(config.get("spin", [0, 0])[0]), float(config.get("spin", [0, 0])[1])),
            area=(float(area[0]), float(area[1])) if area else None,
            seed=int(config.get("seed", 20260101)),
            label=config.get("label", name),
        )

    @property
    def active(self) -> bool:
        return self._target > 0.0 or self._alpha > 0.0

    def stop(self) -> None:
        self._target = 0.0

    # --- 生成 ---------------------------------------------------------
    def _spawn(self, initial: bool = False) -> Particle:
        preset = self.preset
        rng = self._rng
        width, height = self._ctx.renderer.size
        if preset.area:
            x = rng.uniform(preset.area[0], preset.area[1])
            y = rng.uniform(preset.spawn_y[0], preset.spawn_y[1])
        else:
            x = rng.uniform(-40, width + 40)
            y = rng.uniform(preset.spawn_y[0], preset.spawn_y[1])
            if initial:
                y = rng.uniform(0, height)
        return Particle(
            x=x,
            y=y,
            vx=_range(preset.velocity_x, rng, (-10, 10)),
            vy=_range(preset.velocity_y, rng, (20, 40)),
            size=_range(preset.size, rng, (3, 6)),
            alpha=_range(preset.alpha, rng, (150, 220)) / 255.0,
            phase=rng.uniform(0.0, math.tau),
            sway_amp=_range(preset.sway_amplitude, rng, (0, 0)),
            sway_hz=_range(preset.sway_frequency, rng, (0, 0)),
            spin=_range(preset.spin, rng, (0, 0)),
            color=rng.choice(preset.colors),
            life=0.0,
        )

    # --- 更新 ---------------------------------------------------------
    def update(self, dt: float) -> None:
        if self._alpha < self._target:
            self._alpha = min(self._target, self._alpha + dt * self._fade_speed)
        elif self._alpha > self._target:
            self._alpha = max(self._target, self._alpha - dt * self._fade_speed)

        width, height = self._ctx.renderer.size
        kind = self.preset.kind
        for particle in self._particles:
            particle.life += dt
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            if particle.sway_amp:
                particle.phase += particle.sway_hz * math.tau * dt
                particle.x += math.sin(particle.phase) * particle.sway_amp * dt

            # 回收
            if kind == "mist":
                if particle.x - particle.size > width + 60:
                    recycled = self._spawn()
                    recycled.y = particle.y
                    particle.__dict__.update(recycled.__dict__)
            elif kind == "spray":
                if particle.life > 1.6:
                    recycled = self._spawn()
                    particle.__dict__.update(recycled.__dict__)
            else:
                if particle.y > height + 30 or particle.x < -80 or particle.x > width + 80:
                    recycled = self._spawn()
                    particle.__dict__.update(recycled.__dict__)

    # --- 绘制 ---------------------------------------------------------
    def draw(self, renderer: Renderer) -> None:
        if self._alpha <= 0.01:
            return
        kind = self.preset.kind
        fade = self._alpha
        if kind == "petal":
            self._draw_petals(renderer, fade)
        elif kind == "rain":
            self._draw_rain(renderer, fade)
        elif kind == "mist":
            self._draw_mist(renderer, fade)
        elif kind == "spray":
            self._draw_spray(renderer, fade)

    def _draw_petals(self, renderer: Renderer, fade: float) -> None:
        for p in self._particles:
            angle = p.phase if p.spin else 0.0
            half = p.size / 2
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            points = []
            for dx, dy in ((-half, 0.0), (0.0, -half * 0.7), (half, 0.0), (0.0, half * 0.7)):
                points.append((p.x + dx * cos_a - dy * sin_a, p.y + dx * sin_a + dy * cos_a))
            renderer.draw_polygon(points, p.color, alpha=int(255 * p.alpha * fade))

    def _draw_rain(self, renderer: Renderer, fade: float) -> None:
        for p in self._particles:
            length = p.size * 6
            renderer.draw_line(
                (p.x, p.y),
                (p.x + p.vx * 0.05, p.y + length),
                p.color,
                width=1,
                alpha=int(255 * p.alpha * fade * 0.85),
            )

    def _draw_mist(self, renderer: Renderer, fade: float) -> None:
        """雾团：低透明度的小块叠加，避免出现明显的矩形/胶囊边界。"""
        for p in self._particles:
            for index, (scale, alpha_scale) in enumerate(((1.0, 1.0), (0.62, 0.7), (1.45, 0.5))):
                width = p.size * 9 * scale
                height = p.size * 1.6 * (1.0 + index * 0.25)
                rect = Rect(p.x - width / 2, p.y - height / 2 + index * 3, width, height)
                renderer.draw_round_rect(rect, p.color, int(height / 2),
                                         alpha=int(255 * p.alpha * fade * 0.22 * alpha_scale))

    def _draw_spray(self, renderer: Renderer, fade: float) -> None:
        for p in self._particles:
            life_fade = clamp01(1.0 - p.life / 1.6)
            size = max(1.0, p.size * 0.6)
            renderer.draw_rect(Rect(p.x, p.y, size, size), p.color,
                               alpha=int(255 * p.alpha * fade * life_fade * 0.85))
