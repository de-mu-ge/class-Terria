"""合照定格界面。

Scene 04 要求：手机拍照音响起 → 切到照片界面，展示五个人的合照 → 停留约两秒 → 切回真实场景。
本轮不真的合成一张图，而是用「静态构图」：一张相纸 + 当前甲板背景的固定裁切 + 五个小人 + 说明。
"""

from __future__ import annotations

from typing import Sequence

from ..core.context import SceneContext
from ..core.types import Rect, dim
from ..data.models import Character
from ..render.renderer import Texture
from .paper_doll import PaperDollView


class PhotoView:
    def __init__(self, ctx: SceneContext) -> None:
        self._ctx = ctx
        cfg = ctx.config
        self._frame = cfg.rect("photo", "frame")
        self._border = cfg.number("photo", "border", default=14.0)
        inner_raw = cfg.rect("photo", "inner")
        # inner 是相对相纸的偏移与尺寸
        self._inner = Rect(self._frame.x + inner_raw.x, self._frame.y + inner_raw.y,
                           inner_raw.w, inner_raw.h)
        self._caption_y = cfg.number("photo", "caption_y", default=372.0)
        self._doll_scale = cfg.number("photo", "doll_scale", default=0.55)
        self._dim_alpha = cfg.alpha("photo_dim", default=0.45)
        self._font = ctx.resources.font("photo")
        self._dolls = PaperDollView(ctx)

        self._active = False
        self._texture: Texture | None = None
        self._caption = ""
        self._cast: list[tuple[Character, str | None, float]] = []
        self._duration = 2.0
        self._elapsed = 0.0
        self._alpha = 0.0

    @property
    def active(self) -> bool:
        return self._active

    @property
    def done(self) -> bool:
        return (not self._active) or self._elapsed >= self._duration

    def show(
        self,
        background: Texture | None,
        caption: str,
        cast: Sequence[tuple[Character, str | None, float]],
        duration: float = 2.0,
    ) -> None:
        self._texture = background
        self._caption = caption
        self._cast = list(cast)
        self._duration = max(0.3, duration)
        self._elapsed = 0.0
        self._alpha = 0.0
        self._active = True

    def hide(self) -> None:
        self._active = False
        self._alpha = 0.0

    def update(self, dt: float) -> None:
        if not self._active:
            return
        self._elapsed += dt
        appear = 0.16
        if self._elapsed < appear:
            self._alpha = self._elapsed / appear
        elif self._elapsed > self._duration - 0.2:
            self._alpha = max(0.0, min(1.0, (self._duration - self._elapsed) / 0.2))
        else:
            self._alpha = 1.0
        if self._elapsed >= self._duration:
            self._active = False
            self._alpha = 0.0

    def draw(self) -> None:
        if not self._active or self._alpha <= 0.0:
            return
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        alpha = int(255 * self._alpha)

        # 压暗背景
        renderer.draw_rect(Rect(0, 0, renderer.width, renderer.height),
                           cfg.color("void"), alpha=int(self._dim_alpha * self._alpha))
        # 相纸
        renderer.draw_rect(self._frame.move(6, 8), cfg.color("black"), alpha=int(90 * self._alpha))
        renderer.draw_rect(self._frame, cfg.color("cream"), alpha=alpha)

        inner = self._inner
        renderer.draw_rect(inner, cfg.color("void"), alpha=alpha)
        if self._texture is not None:
            # 固定构图：把背景铺满内框（cover）
            tex_w, tex_h = self._texture.size
            scale = max(inner.w / max(1, tex_w), inner.h / max(1, tex_h))
            draw_w = tex_w * scale
            draw_h = tex_h * scale
            renderer.draw_texture(
                self._texture,
                Rect(inner.centerx - draw_w / 2, inner.centery - draw_h / 2, draw_w, draw_h),
                alpha=alpha,
                smooth=True,
            )
            renderer.push_clip(inner)
            for character, portrait, ratio in self._cast:
                height = inner.h * self._doll_scale
                bottom = inner.bottom - 4
                center_x = inner.x + inner.w * ratio
                self._dolls.draw(character, portrait, center_x, bottom, height,
                                 alpha=alpha, label=False)
            renderer.pop_clip()

        # 说明文字
        if self._caption:
            text_w, text_h = renderer.measure_text(self._caption, self._font)
            renderer.draw_text(self._caption,
                               (self._frame.centerx - text_w / 2, self._frame.y + self._caption_y),
                               self._font, dim(cfg.color("void"), 0.6), alpha=alpha)
