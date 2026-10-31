"""舞台层：背景（含镜头）、纸片站位、像素 Sprite、摇晃、天气遮罩。

镜头只作用于背景（推近 / 拉远 / 上抬 / 下移），人物站位由数据固定在屏幕坐标上，
避免“人物跟着背景一起缩放”这种错误演出。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from ..core.context import SceneContext
from ..core.timeline import clamp01, easing, lerp
from ..core.types import Rect
from ..data.models import Character
from ..render.renderer import Renderer, Texture
from ..ui.paper_doll import PaperDollView
from ..ui.transitions import GradientMask


@dataclass
class Camera:
    zoom: float = 1.0
    focus: tuple[float, float] = (0.5, 0.5)

    def copy(self) -> "Camera":
        return Camera(self.zoom, self.focus)

    def source_rect(self, size: tuple[int, int], canvas_size: tuple[int, int]) -> Rect:
        tex_w, tex_h = size
        canvas_w, canvas_h = canvas_size
        aspect = canvas_w / max(1, canvas_h)
        visible_h = tex_h / max(1.0, self.zoom)
        visible_w = visible_h * aspect
        if visible_w > tex_w:
            visible_w = tex_w
            visible_h = visible_w / aspect
        if visible_h > tex_h:
            visible_h = tex_h
            visible_w = visible_h * aspect
        cx = self.focus[0] * tex_w
        cy = self.focus[1] * tex_h
        x = max(0.0, min(tex_w - visible_w, cx - visible_w / 2))
        y = max(0.0, min(tex_h - visible_h, cy - visible_h / 2))
        return Rect(x, y, visible_w, visible_h)


class BackgroundLayer:
    def __init__(self, ctx: SceneContext) -> None:
        self._ctx = ctx
        self.camera = Camera()
        self.texture: Texture | None = None
        self.smooth = True
        self._prev_texture: Texture | None = None
        self._prev_camera = Camera()
        self._fade = 0.0
        self._fade_target = 0.0
        self._fade_duration = 0.0

    @property
    def had_texture(self) -> bool:
        return self.texture is not None

    def set(self, texture: Texture, camera: Camera, smooth: bool = True,
            crossfade: float = 0.0) -> None:
        if self.texture is not None and crossfade > 0.0:
            self._prev_texture = self.texture
            self._prev_camera = self.camera.copy()
            self._fade = 0.0
            self._fade_target = 1.0
            self._fade_duration = crossfade
        else:
            self._prev_texture = None
            self._fade = 1.0
            self._fade_target = 1.0
            self._fade_duration = 0.0
        self.texture = texture
        self.smooth = smooth
        self.camera = camera.copy()

    def update(self, dt: float) -> None:
        if self._fade < self._fade_target:
            if self._fade_duration <= 0.0:
                self._fade = 1.0
            else:
                self._fade = min(1.0, self._fade + dt / self._fade_duration)

    def draw(self, renderer: Renderer, offset: tuple[float, float] = (0.0, 0.0)) -> None:
        canvas = renderer.size
        dest = Rect(offset[0], offset[1], canvas[0], canvas[1])
        if self._prev_texture is not None and self._fade < 1.0:
            src = self._prev_camera.source_rect(self._prev_texture.size, canvas)
            renderer.draw_texture(self._prev_texture, dest, src=src, smooth=self.smooth)
        if self.texture is None:
            return
        src = self.camera.source_rect(self.texture.size, canvas)
        alpha = int(255 * (self._fade if self._prev_texture is not None else 1.0))
        renderer.draw_texture(self.texture, dest, src=src, alpha=alpha, smooth=self.smooth)


# --- 纸片站位 -------------------------------------------------------------
@dataclass
class Doll:
    character: Character
    portrait: str | None
    x: float
    bottom: float
    height: float
    alpha: float = 0.0
    flip: bool = False
    visible: bool = True
    _target: dict[str, float] = field(default_factory=dict)

    def snapshot(self) -> dict[str, float]:
        return {"x": self.x, "bottom": self.bottom, "height": self.height, "alpha": self.alpha}


class DollLayer:
    def __init__(self, ctx: SceneContext) -> None:
        self._ctx = ctx
        self._view = PaperDollView(ctx)
        self._dolls: dict[str, Doll] = {}
        clip_y = ctx.config.number("stage", "doll_clip_y", default=393.0)
        self._clip = Rect(0, 0, ctx.renderer.width, clip_y)

    @property
    def dolls(self) -> dict[str, Doll]:
        return self._dolls

    def get(self, char_id: str) -> Doll | None:
        return self._dolls.get(char_id)

    def show(self, character: Character, portrait: str | None, x: float, bottom: float,
             height: float, alpha: float = 1.0, flip: bool = False) -> Doll:
        doll = Doll(character=character, portrait=portrait, x=x, bottom=bottom,
                    height=height, alpha=alpha, flip=flip)
        self._dolls[character.id] = doll
        return doll

    def hide(self, char_id: str) -> None:
        self._dolls.pop(char_id, None)

    def clear(self) -> None:
        self._dolls.clear()

    def set_portrait(self, char_id: str, portrait: str | None) -> None:
        doll = self._dolls.get(char_id)
        if doll is not None and portrait:
            doll.portrait = portrait

    def draw(self, renderer: Renderer, active_speaker: str | None = None,
             offset: tuple[float, float] = (0.0, 0.0)) -> None:
        dim_alpha = self._ctx.config.number("dialogue", "portrait_dim_alpha", default=176.0) / 255.0
        renderer.push_clip(self._clip)
        for doll in self._dolls.values():
            if not doll.visible or doll.alpha <= 0.0:
                continue
            factor = 1.0
            if active_speaker and doll.character.id != active_speaker:
                factor = dim_alpha
            alpha = int(255 * clamp01(doll.alpha * factor))
            self._view.draw(doll.character, doll.portrait, doll.x + offset[0],
                            doll.bottom + offset[1], doll.height, alpha=alpha, flip=doll.flip)
        renderer.pop_clip()


# --- 镜头 / 人物 / 摇晃 动画 ---------------------------------------------
class Animator:
    """可并行播放的动画（不阻塞时间线）。"""

    def __init__(self, duration: float, ease: str = "linear") -> None:
        self.duration = max(0.0, duration)
        self._ease = easing(ease)
        self.elapsed = 0.0
        self._done = self.duration <= 0.0

    @property
    def done(self) -> bool:
        return self._done

    def progress(self) -> float:
        if self.duration <= 0.0:
            return 1.0
        return self._ease(clamp01(self.elapsed / self.duration))

    def update(self, dt: float) -> bool:
        if self._done:
            return True
        self.elapsed += dt
        if self.elapsed >= self.duration:
            self.elapsed = self.duration
            self._done = True
        return self._done


class CameraAnimator(Animator):
    def __init__(self, layer: BackgroundLayer, target: Camera, duration: float,
                 ease: str = "out") -> None:
        super().__init__(duration, ease)
        self._layer = layer
        self._from = layer.camera.copy()
        self._to = target

    def update(self, dt: float) -> bool:
        if self._done:
            return True
        self.elapsed += dt
        t = self.progress()
        self._layer.camera.zoom = lerp(self._from.zoom, self._to.zoom, t)
        self._layer.camera.focus = (
            lerp(self._from.focus[0], self._to.focus[0], t),
            lerp(self._from.focus[1], self._to.focus[1], t),
        )
        if self.elapsed >= self.duration:
            self._done = True
            self._layer.camera = self._to.copy()
        return self._done


class DollAnimator(Animator):
    def __init__(self, doll: Doll, target: dict[str, float], duration: float,
                 ease: str = "out", remove_on_finish: bool = False) -> None:
        super().__init__(duration, ease)
        self._doll = doll
        self._from = doll.snapshot()
        self._to = dict(self._from)
        self._to.update(target)
        self._remove = remove_on_finish

    def update(self, dt: float) -> bool:
        if self._done:
            return True
        self.elapsed += dt
        t = self.progress()
        doll = self._doll
        doll.x = lerp(self._from["x"], self._to["x"], t)
        doll.bottom = lerp(self._from["bottom"], self._to["bottom"], t)
        doll.height = lerp(self._from["height"], self._to["height"], t)
        doll.alpha = lerp(self._from["alpha"], self._to["alpha"], t)
        if self.elapsed >= self.duration:
            self._done = True
            doll.x = self._to["x"]
            doll.bottom = self._to["bottom"]
            doll.height = self._to["height"]
            doll.alpha = self._to["alpha"]
            if self._remove:
                doll.visible = False
        return self._done


class ShakeAnimator(Animator):
    def __init__(self, amplitude: float, frequency: float, duration: float | None) -> None:
        super().__init__(duration if duration is not None else 1e9)
        self.amplitude = amplitude
        self.frequency = max(0.01, frequency)
        self.forever = duration is None
        self.offset = (0.0, 0.0)

    def update(self, dt: float) -> bool:
        self.elapsed += dt
        t = self.elapsed
        dx = self.amplitude * math.sin(2.0 * math.pi * self.frequency * t)
        dy = self.amplitude * 0.5 * math.sin(2.0 * math.pi * self.frequency * t + 1.1)
        self.offset = (dx, dy)
        if self.forever:
            return False
        if self.elapsed >= self.duration:
            self.offset = (0.0, 0.0)
            self._done = True
        return self._done


class MaskAnimator(Animator):
    def __init__(self, mask: GradientMask, target: float, duration: float, ease: str = "out") -> None:
        super().__init__(duration, ease)
        self._mask = mask
        self._from = mask.strength
        self._to = clamp01(target)

    def update(self, dt: float) -> bool:
        if self._done:
            return True
        self.elapsed += dt
        t = self.progress()
        self._mask.set_strength(lerp(self._from, self._to, t))
        if self.elapsed >= self.duration:
            self._done = True
        return self._done


# --- 像素 Sprite ----------------------------------------------------------
class PixelActor:
    """未知世界阶段的角色 Sprite（程序化占位图）。"""

    def __init__(self, ctx: SceneContext, character: Character) -> None:
        from ..art.pixel_doll import PixelFigure

        self._ctx = ctx
        self.character = character
        self._figure = PixelFigure()
        self._textures: dict[str, Texture] = {}
        self.pose = "idle"
        self.x = ctx.renderer.width / 2
        self.ground_y = ctx.config.number("stage", "pixel_sprite_ground_y", default=470.0)
        self.scale = ctx.config.number("stage", "pixel_sprite_scale", default=2.0)
        self.flip = False
        self.alpha = 1.0
        self._time = 0.0

    def _texture(self, pose: str) -> Texture:
        if pose not in self._textures:
            width, height, data = self._figure.build(pose)
            self._textures[pose] = self._ctx.renderer.create_texture(width, height, data)
        return self._textures[pose]

    def set_pose(self, pose: str) -> None:
        self.pose = pose

    def update(self, dt: float) -> None:
        self._time += dt

    @property
    def size(self) -> tuple[int, int]:
        texture = self._texture(self.pose)
        return (int(texture.width * self.scale), int(texture.height * self.scale))

    def draw(self, renderer: Renderer, offset: tuple[float, float] = (0.0, 0.0)) -> None:
        if self.alpha <= 0.0:
            return
        texture = self._texture(self.pose)
        width = texture.width * self.scale
        height = texture.height * self.scale
        # 站立/行走时 1px 呼吸起伏，避免角色像贴图一样完全静止
        bob = math.sin(self._time * 2.2) * 1.0 if self.pose in ("idle", "walk_1", "walk_2") else 0.0
        rect = Rect(self.x - width / 2 + offset[0],
                    self.ground_y - height + offset[1] + bob,
                    width, height)
        renderer.draw_texture(texture, rect, alpha=int(255 * clamp01(self.alpha)),
                              flip_x=self.flip)
