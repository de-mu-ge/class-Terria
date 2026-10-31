"""海岸玩法 UI：时间/潮汐 HUD、交互提示、浮动文字、背包、合成、储物箱。"""

from __future__ import annotations

from dataclasses import dataclass

from ..coast.defs import CoastDefs, Recipe
from ..coast.inventory import CoastInventory, Stack
from ..coast.textures import ItemIcons
from ..core.types import Rect, dim
from .panels import draw_plain_panel


@dataclass
class FloatingText:
    text: str
    x: float
    y: float
    life: float = 1.4


class CoastUI:
    SLOT = 40.0
    GAP = 4.0

    def __init__(self, ctx, defs: CoastDefs, inventory: CoastInventory,
                 icons: ItemIcons) -> None:
        self._ctx = ctx
        self._defs = defs
        self._inventory = inventory
        self._icons = icons
        self._font = ctx.resources.font("hud")
        self._font_small = ctx.resources.font("task")
        self._font_big = ctx.resources.font("hud_big")
        self.floating: list[FloatingText] = []
        self.hotbar_y = 492.0
        self.selected = 0

    @property
    def font_small(self):
        return self._font_small

    @property
    def font(self):
        return self._font

    # --- 布局 ---------------------------------------------------------
    def hotbar_rect(self, index: int) -> Rect:
        total = 8 * self.SLOT + 7 * self.GAP
        x0 = (self._ctx.renderer.width - total) / 2
        return Rect(x0 + index * (self.SLOT + self.GAP), self.hotbar_y, self.SLOT, self.SLOT)

    def panel_rect(self) -> Rect:
        return Rect(268, 196, 424, 286)

    def grid_rect(self, index: int) -> Rect:
        panel = self.panel_rect()
        col = index % 8
        row = index // 8
        return Rect(panel.x + 16 + col * (self.SLOT + self.GAP),
                    panel.y + 48 + row * (self.SLOT + self.GAP),
                    self.SLOT, self.SLOT)

    def craft_rect(self, index: int) -> Rect:
        panel = Rect(556, 120, 372, 250)
        return Rect(panel.x + 10, panel.y + 52 + index * 44, panel.w - 20, 38)

    def chest_rect(self, index: int) -> Rect:
        panel = Rect(300, 320, 360, 140)
        return Rect(panel.x + 16 + index * (self.SLOT + self.GAP), panel.y + 48,
                    self.SLOT, self.SLOT)

    def hotbar_index_at(self, pos) -> int | None:
        for index in range(8):
            if self.hotbar_rect(index).contains(*pos):
                return index
        return None

    def grid_index_at(self, pos) -> int | None:
        for index in range(len(self._inventory)):
            if self.grid_rect(index).contains(*pos):
                return index
        return None

    def craft_index_at(self, pos, recipes: list[Recipe]) -> int | None:
        for index in range(len(recipes)):
            if self.craft_rect(index).contains(*pos):
                return index
        return None

    def chest_index_at(self, pos, chest_slots: int) -> int | None:
        for index in range(chest_slots):
            if self.chest_rect(index).contains(*pos):
                return index
        return None

    # --- 浮动文字 -----------------------------------------------------
    def add_floating(self, text: str, x: float, y: float) -> None:
        self.floating.append(FloatingText(text=text, x=x, y=y))

    def update(self, dt: float) -> None:
        for item in list(self.floating):
            item.life -= dt
            item.y -= dt * 22
            if item.life <= 0:
                self.floating.remove(item)

    # --- 基础绘制 -----------------------------------------------------
    def _slot(self, rect: Rect, stack: Stack | None, selected: bool = False,
              highlight: bool = False) -> None:
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        renderer.draw_rect(rect, cfg.color("mid") if selected else cfg.color("void"),
                           alpha=205)
        border = cfg.color("dialog_border") if selected else dim(cfg.color("dialog_border"), 0.4)
        renderer.draw_frame(rect, border, width=2 if selected else 1)
        if highlight:
            renderer.draw_frame(rect, cfg.color("warm_core"), width=1, alpha=160)
        if stack is None:
            return
        texture = self._icons.get(stack.item_id)
        if texture is not None:
            size = 28
            renderer.draw_texture(texture, Rect(rect.centerx - size / 2,
                                                rect.centery - size / 2 - 1, size, size))
        if stack.count > 1:
            text = str(stack.count)
            width, height = renderer.measure_text(text, self._font_small)
            renderer.draw_text(text, (rect.right - width - 3, rect.bottom - height - 1),
                               self._font_small, cfg.color("text"))

    def draw_hotbar(self, selected: int, hover: int | None) -> None:
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        for index in range(8):
            rect = self.hotbar_rect(index)
            self._slot(rect, self._inventory.get(index), selected=index == selected,
                       highlight=hover == index)
        stack = self._inventory.get(selected)
        if stack is not None:
            name = self._defs.item(stack.item_id).name
            width, _ = renderer.measure_text(name, self._font)
            renderer.draw_text(name, (renderer.width / 2 - width / 2,
                                      self.hotbar_y - 18),
                               self._font, cfg.color("text_dim"))

    def draw_inventory(self, hover: int | None) -> None:
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        panel = self.panel_rect()
        draw_plain_panel(renderer, panel, cfg.color("dialog_bg"), 232,
                         border=cfg.color("dialog_border"), border_width=2)
        renderer.draw_text(cfg.text("ui_text", "coast_inventory", default="行囊"),
                           (panel.x + 14, panel.y + 10), self._font_big,
                           cfg.color("warm_core"))
        renderer.draw_text(cfg.text("ui_text", "coast_inventory_hint", default=""),
                           (panel.x + 120, panel.y + 18), self._font_small,
                           cfg.color("text_dim"))
        for index in range(len(self._inventory)):
            self._slot(self.grid_rect(index), self._inventory.get(index),
                       selected=index < 8, highlight=hover == index)

    def draw_crafting(self, recipes: list[Recipe], can: list[bool], hover: int | None) -> None:
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        panel = Rect(556, 120, 372, 250)
        draw_plain_panel(renderer, panel, cfg.color("dialog_bg"), 232,
                         border=cfg.color("dialog_border"), border_width=2)
        renderer.draw_text(cfg.text("ui_text", "coast_craft", default="制作"),
                           (panel.x + 14, panel.y + 10), self._font_big,
                           cfg.color("warm_core"))
        for index, recipe in enumerate(recipes):
            rect = self.craft_rect(index)
            ok = can[index]
            if hover == index:
                renderer.draw_rect(rect, cfg.color("mid"), alpha=190)
            output = self._defs.item(recipe.output)
            texture = self._icons.get(recipe.output)
            if texture is not None:
                renderer.draw_texture(texture, Rect(rect.x + 4, rect.centery - 12, 24, 24))
            label = output.name + (f" ×{recipe.count}" if recipe.count > 1 else "")
            renderer.draw_text(label, (rect.x + 34, rect.y + 1), self._font_small,
                               cfg.color("text") if ok else cfg.color("text_dim"))
            parts = []
            for item_id, need in recipe.ingredients:
                have = self._inventory.count(item_id)
                parts.append(f"{self._defs.item(item_id).name} {have}/{need}")
            renderer.draw_text("  ".join(parts), (rect.x + 34, rect.y + 16),
                               self._font_small,
                               cfg.color("text_dim") if ok else dim(cfg.color("danger"), 0.9))

    def draw_chest(self, chest: list[Stack | None], hover: int | None,
                   hover_inventory: int | None) -> None:
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        panel = Rect(300, 320, 360, 140)
        draw_plain_panel(renderer, panel, cfg.color("dialog_bg"), 235,
                         border=cfg.color("dialog_border"), border_width=2)
        renderer.draw_text(cfg.text("ui_text", "coast_chest", default="储物箱"),
                           (panel.x + 14, panel.y + 10), self._font_big,
                           cfg.color("warm_core"))
        for index in range(len(chest)):
            self._slot(self.chest_rect(index), chest[index], highlight=hover == index)
        # 下方直接显示玩家行囊前 8 格，方便拖放
        for index in range(8):
            rect = Rect(panel.x + 16 + index * (self.SLOT + self.GAP), panel.y + 96,
                        self.SLOT, self.SLOT)
            self._slot(rect, self._inventory.get(index), highlight=hover_inventory == index)

    # --- HUD ----------------------------------------------------------
    def draw_hud(self, time_label: str, zone_label: str, tide_label: str,
                 underwater: bool) -> None:
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        panel = Rect(12, 10, 232, 54)
        draw_plain_panel(renderer, panel, cfg.color("dialog_bg"), 190,
                         border=dim(cfg.color("dialog_border"), 0.55), border_width=1)
        renderer.draw_text(time_label, (panel.x + 10, panel.y + 6), self._font,
                           cfg.color("warm_core"))
        renderer.draw_text(tide_label, (panel.x + 10, panel.y + 26), self._font_small,
                           cfg.color("cold_white"))
        zone_color = cfg.color("cold_white") if not underwater else cfg.color("sky")
        renderer.draw_text(zone_label, (panel.x + 108, panel.y + 26), self._font_small,
                           zone_color)

    def draw_prompt(self, text: str) -> None:
        if not text:
            return
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        width, height = renderer.measure_text(text, self._font)
        rect = Rect(renderer.width / 2 - width / 2 - 12, self.hotbar_y - 62,
                    width + 24, height + 12)
        draw_plain_panel(renderer, rect, cfg.color("dialog_bg"), 220,
                         border=cfg.color("dialog_border"), border_width=1)
        renderer.draw_text(text, (rect.centerx - width / 2, rect.y + 6),
                           self._font, cfg.color("text"))

    def draw_floating(self, cam: tuple[float, float]) -> None:
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        for item in self.floating:
            alpha = int(255 * max(0.0, min(1.0, item.life / 1.4)))
            width, _ = renderer.measure_text(item.text, self._font_small)
            renderer.draw_text(item.text, (item.x + cam[0] - width / 2, item.y + cam[1]),
                               self._font_small, cfg.color("warm_core"), alpha=alpha)

    def draw_dive_hint(self, depth: float) -> None:
        """水下深度提示：给第一次下潜的玩家一个方向感。"""
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        text = f"水深 {depth:.0f} m"
        width, _ = renderer.measure_text(text, self._font_small)
        renderer.draw_text(text, (renderer.width - width - 20, 16), self._font_small,
                           cfg.color("cold_white"), alpha=200)

    def draw_controls(self, text: str) -> None:
        if not text:
            return
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        width, _ = renderer.measure_text(text, self._font_small)
        draw_plain_panel(renderer, Rect(8, 74, width + 16, 22), cfg.color("dialog_bg"), 150)
        renderer.draw_text(text, (16, 78), self._font_small, cfg.color("text_dim"), alpha=210)
