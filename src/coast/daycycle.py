"""昼夜循环：按关键帧插值天空、环境光、水色与光照强度。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..core.types import Color, mix, parse_color


@dataclass
class SkySample:
    sky_top: Color
    sky_bottom: Color
    ambient: Color
    ambient_alpha: int
    water_tint: Color
    light: float
    sun_x: float          # 0..1 屏幕横向位置（太阳/月亮）
    sun_y: float          # 0..1 屏幕纵向位置
    is_night: bool
    label: str


class DayCycle:
    def __init__(self, cfg: dict[str, Any]) -> None:
        self.length = max(30.0, float(cfg.get("length_seconds", 420.0)))
        self.start_time = float(cfg.get("start_time", 0.27))
        self.time = self.start_time % 1.0
        self.phases: list[dict[str, Any]] = list(cfg.get("phases", []))
        if not self.phases:
            raise ValueError("昼夜配置缺少 phases")
        self.phases.sort(key=lambda item: float(item.get("t", 0.0)))

    def update(self, dt: float) -> None:
        self.time = (self.time + dt / self.length) % 1.0

    @property
    def hours(self) -> float:
        """0..24 的时钟（0 = 午夜），用于 UI。"""
        return (self.time * 24.0) % 24.0

    def sample(self) -> SkySample:
        phases = self.phases
        t = self.time
        previous = phases[-1]
        following = phases[0]
        for index, phase in enumerate(phases):
            start = float(phase.get("t", 0.0))
            end = float(phases[(index + 1) % len(phases)].get("t", 1.0))
            if end <= start:
                end += 1.0
            local_t = t if t >= start else t + 1.0
            if start <= local_t < end:
                previous = phase
                following = phases[(index + 1) % len(phases)]
                span = end - start
                weight = (local_t - start) / span if span > 0 else 0.0
                break
        else:
            weight = 0.0

        def color_of(key: str, default: str) -> Color:
            return parse_color(previous.get(key, default))

        sky_top = mix(color_of("sky_top", "#1B2433"),
                      parse_color(following.get("sky_top", "#1B2433")), weight)
        sky_bottom = mix(color_of("sky_bottom", "#3E5A7A"),
                         parse_color(following.get("sky_bottom", "#3E5A7A")), weight)
        ambient = mix(color_of("ambient", "#101822"),
                      parse_color(following.get("ambient", "#101822")), weight)
        water = mix(color_of("water", "#3E7A99"),
                    parse_color(following.get("water", "#3E7A99")), weight)
        alpha_a = float(previous.get("ambient_alpha", 0.0))
        alpha_b = float(following.get("ambient_alpha", 0.0))
        alpha = alpha_a + (alpha_b - alpha_a) * weight
        light_a = float(previous.get("light", 1.0))
        light_b = float(following.get("light", 1.0))
        light = light_a + (light_b - light_a) * weight

        # 太阳/月亮沿弧线走
        sun_angle = math.pi * (self.time - 0.05)
        sun_x = 0.5 - math.cos(sun_angle) * 0.55
        sun_y = 0.62 - math.sin(sun_angle) * 0.55
        is_night = light < 0.45
        return SkySample(
            sky_top=sky_top,
            sky_bottom=sky_bottom,
            ambient=ambient,
            ambient_alpha=int(max(0.0, min(1.0, alpha)) * 255),
            water_tint=water,
            light=max(0.0, min(1.0, light)),
            sun_x=sun_x,
            sun_y=sun_y,
            is_night=is_night,
            label=str(previous.get("label", "")),
        )
