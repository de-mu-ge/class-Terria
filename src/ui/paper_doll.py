"""纸片立绘渲染（现实世界阶段）。

规则（epoch 提示词第六节）：
- 有图 → 按统一高度绘制，脚底对齐画布底部，宽度按比例。
- 无图 → 占位纸片：角色代表色的圆角矩形 + 名字文字，尺寸同上，不得崩溃。
"""

from __future__ import annotations

from ..core.context import SceneContext
from ..core.types import Rect, dim
from ..data.models import Character
from ..render.renderer import Texture


class PaperDollView:
    def __init__(self, ctx: SceneContext) -> None:
        self._ctx = ctx
        cfg = ctx.config
        self._width_ratio = cfg.number("stage", "doll_width_ratio", default=0.6667)
        self._placeholder_cfg = dict(getattr(ctx.data, "placeholder_config", {}) or {})
        self._radius = int(self._placeholder_cfg.get("corner_radius", 18))
        self._outline = int(self._placeholder_cfg.get("outline_width", 2))
        self._name_offset = float(self._placeholder_cfg.get("name_top_offset", 26))
        self._tag_offset = float(self._placeholder_cfg.get("tag_bottom_offset", 30))
        self._body_alpha = float(self._placeholder_cfg.get("body_alpha", 0.88))
        self._tag_text = cfg.text("ui_text", "placeholder_tag", default="")
        self._font_name = ctx.resources.font("name")
        self._font_tag = ctx.resources.font("menu_small")
        self._texture_cache: dict[str, Texture | None] = {}

    # --- 尺寸 ---------------------------------------------------------
    def doll_size(self, height: float) -> tuple[float, float]:
        return (height * self._width_ratio, height)

    def doll_rect(self, center_x: float, bottom_y: float, height: float) -> Rect:
        width = height * self._width_ratio
        return Rect(center_x - width / 2, bottom_y - height, width, height)

    # --- 绘制 ---------------------------------------------------------
    def draw(self, character: Character, portrait: str | None, center_x: float, bottom_y: float,
             height: float, alpha: int = 255, flip: bool = False, label: bool = True) -> None:
        texture = self._texture(character, portrait)
        if texture is not None:
            self._draw_texture(texture, center_x, bottom_y, height, alpha, flip)
            return
        self._draw_placeholder(character, center_x, bottom_y, height, alpha, label)

    def _texture(self, character: Character, portrait: str | None) -> Texture | None:
        relative = character.doll_path(portrait)
        if not relative:
            return None
        cache_key = f"{character.id}:{portrait}"
        if cache_key in self._texture_cache:
            return self._texture_cache[cache_key]
        path = self._ctx.paths.paper_doll(relative)
        texture = self._ctx.resources.texture_or_none(path)
        self._texture_cache[cache_key] = texture
        return texture

    def _draw_texture(self, texture: Texture, center_x: float, bottom_y: float, height: float,
                      alpha: int, flip: bool) -> None:
        aspect = texture.width / max(1, texture.height)
        width = height * aspect
        rect = Rect(center_x - width / 2, bottom_y - height, width, height)
        self._ctx.renderer.draw_texture(texture, rect, alpha=alpha, flip_x=flip, smooth=True)

    def _draw_placeholder(self, character: Character, center_x: float, bottom_y: float,
                          height: float, alpha: int, label: bool = True) -> None:
        renderer = self._ctx.renderer
        rect = self.doll_rect(center_x, bottom_y, height)
        body_alpha = int(alpha * self._body_alpha)
        renderer.draw_round_rect(rect, character.color, self._radius, alpha=body_alpha)
        renderer.draw_round_frame(rect, dim(character.color, 0.55), self._radius,
                                  width=self._outline, alpha=alpha)

        # 一条竖线示意“人形”，避免整块纯色
        inner = rect.inset(rect.w * 0.28, height * 0.04)
        renderer.draw_round_rect(inner, dim(character.color, 0.82), self._radius // 2,
                                 alpha=int(alpha * 0.35))

        # 名字（上）与占位标记（名字下方，避免脚底被对话框裁掉后看不到）
        if not label:
            return
        name = character.name
        font = self._font_name
        text_w, text_h = renderer.measure_text(name, font)
        renderer.draw_text(name, (rect.centerx - text_w / 2, rect.y + self._name_offset),
                           font, dim(character.color, 0.22), alpha=alpha)
        if self._tag_text:
            tag_font = self._font_tag
            tag_w, tag_h = renderer.measure_text(self._tag_text, tag_font)
            renderer.draw_text(self._tag_text,
                               (rect.centerx - tag_w / 2, rect.y + self._name_offset + text_h + 6),
                               tag_font, dim(character.color, 0.3), alpha=int(alpha * 0.8))
