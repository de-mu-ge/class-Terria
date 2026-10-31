"""沙盒 UI：快捷栏、背包面板、合成面板、鼠标拖拽物品与提示。

与序章 HUD 分开：这里的槽位更小（40px），只服务玩法原型。
"""

from __future__ import annotations

from ..core.types import Rect, dim
from ..sandbox.defs import Recipe
from ..sandbox.inventory import Inventory, Stack
from ..sandbox.textures import ItemIcons
from .panels import draw_plain_panel


class SandboxUI:
    def __init__(self, ctx, defs, inventory: Inventory, icons: ItemIcons) -> None:
        self._ctx = ctx
        self._defs = defs
        self._inventory = inventory
        self._icons = icons
        cfg = ctx.config.section("sandbox")
        self._slot = float(cfg.get("slot_size", 40))
        self._gap = float(cfg.get("slot_gap", 4))
        self._icon_scale = int(cfg.get("icon_scale", 2))
        hotbar = cfg.get("hotbar", {})
        self._hotbar_y = float(hotbar.get("y", 492))
        self._hotbar_slots = int(hotbar.get("slots", 8))
        inv = cfg.get("inventory", {})
        self._inv_panel = Rect.from_sequence(inv.get("panel", [300, 240, 360, 220]))
        self._inv_cols = int(inv.get("cols", 8))
        self._inv_rows = int(inv.get("rows", 4))
        craft = cfg.get("crafting", {})
        self._craft_panel = Rect.from_sequence(craft.get("panel", [566, 60, 370, 430]))
        self._craft_row = float(craft.get("row_height", 34))
        self._font = ctx.resources.font("sandbox_ui")
        self._font_small = ctx.resources.font("sandbox_small")

    # --- 布局 ---------------------------------------------------------
    def hotbar_rect(self, index: int) -> Rect:
        total = self._hotbar_slots * self._slot + (self._hotbar_slots - 1) * self._gap
        x0 = (self._ctx.renderer.width - total) / 2
        return Rect(x0 + index * (self._slot + self._gap), self._hotbar_y, self._slot, self._slot)

    def inventory_rect(self, index: int) -> Rect:
        col = index % self._inv_cols
        row = index // self._inv_cols
        x = self._inv_panel.x + 8 + col * (self._slot + self._gap)
        y = self._inv_panel.y + 36 + row * (self._slot + self._gap)
        return Rect(x, y, self._slot, self._slot)

    def recipe_rect(self, index: int, panel_rect: Rect | None = None) -> Rect:
        panel = panel_rect or self._craft_panel
        return Rect(panel.x + 6, panel.y + 40 + index * self._craft_row,
                    panel.w - 12, self._craft_row - 4)

    def hotbar_index_at(self, pos) -> int | None:
        for index in range(self._hotbar_slots):
            if self.hotbar_rect(index).contains(*pos):
                return index
        return None

    def inventory_index_at(self, pos) -> int | None:
        for index in range(self._inv_cols * self._inv_rows):
            if self.inventory_rect(index).contains(*pos):
                return index
        return None

    def recipe_index_at(self, pos, panel_rect: Rect | None = None) -> int | None:
        panel = panel_rect or self._craft_panel
        if not panel.contains(*pos):
            return None
        for index in range(16):
            if self.recipe_rect(index, panel).contains(*pos):
                return index
        return None

    # --- 绘制 ---------------------------------------------------------
    def _draw_slot(self, rect: Rect, stack: Stack | None, selected: bool = False,
                   highlight: bool = False) -> None:
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        bg = cfg.color("mid") if selected else cfg.color("void")
        renderer.draw_rect(rect, bg, alpha=225)
        border = cfg.color("dialog_border") if selected else dim(cfg.color("dialog_border"), 0.45)
        renderer.draw_frame(rect, border, width=2 if selected else 1)
        if highlight:
            renderer.draw_frame(rect, cfg.color("warm_core"), width=1, alpha=170)
        if stack is None:
            return
        self._draw_item_in_rect(rect, stack)

    def _draw_item_in_rect(self, rect: Rect, stack: Stack) -> None:
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        texture = self._icons.get(stack.item_id)
        icon_size = 16 * self._icon_scale
        if texture is not None:
            size = min(icon_size, rect.w - 6, rect.h - 6)
            renderer.draw_texture(
                texture,
                Rect(rect.centerx - size / 2, rect.centery - size / 2 - 2, size, size),
            )
        if stack.count > 1:
            text = str(stack.count)
            width, height = renderer.measure_text(text, self._font_small)
            renderer.draw_text(text, (rect.right - width - 3, rect.bottom - height - 1),
                               self._font_small, cfg.color("text"))

    def draw_hotbar(self, selected: int) -> None:
        for index in range(self._hotbar_slots):
            rect = self.hotbar_rect(index)
            stack = self._inventory.get(index)
            self._draw_slot(rect, stack, selected=index == selected)

    def draw_inventory(self, hover: int | None) -> None:
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        panel = self._inv_panel
        draw_plain_panel(renderer, panel, cfg.color("dialog_bg"), cfg.alpha("panel_bg"),
                         border=cfg.color("dialog_border"), border_width=2)
        title = cfg.text("ui_text", "sandbox_inventory_title", default="背包")
        renderer.draw_text(title, (panel.x + 10, panel.y + 8), self._font, cfg.color("warm_core"))
        for index in range(self._inv_cols * self._inv_rows):
            rect = self.inventory_rect(index)
            self._draw_slot(rect, self._inventory.get(index),
                            selected=index < self._inventory.hotbar_slots,
                            highlight=hover == index)

    def draw_crafting(self, recipes: list[Recipe], stations: set[str],
                      can_craft: list[bool], hover: int | None) -> None:
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        panel = self._craft_panel
        draw_plain_panel(renderer, panel, cfg.color("dialog_bg"), cfg.alpha("panel_bg"),
                         border=cfg.color("dialog_border"), border_width=2)
        title = cfg.text("ui_text", "sandbox_crafting_title", default="合成")
        renderer.draw_text(title, (panel.x + 10, panel.y + 8), self._font, cfg.color("warm_core"))
        station_text = cfg.text("ui_text", "sandbox_station_ok", default="")
        if "workbench" in stations and station_text:
            width, _ = renderer.measure_text(station_text, self._font_small)
            renderer.draw_text(station_text, (panel.right - width - 10, panel.y + 12),
                               self._font_small, cfg.color("cold_white"))

        for index, recipe in enumerate(recipes):
            rect = self.recipe_rect(index, panel)
            if rect.bottom > panel.bottom - 4:
                break
            ok = can_craft[index]
            bg = cfg.color("mid") if hover == index and ok else cfg.color("void")
            renderer.draw_rect(rect, bg, alpha=200 if ok else 140)
            if hover == index:
                renderer.draw_frame(rect, cfg.color("warm_core"), width=1, alpha=150)

            output = self._defs.item(recipe.output)
            texture = self._icons.get(recipe.output)
            if texture is not None:
                renderer.draw_texture(texture, Rect(rect.x + 6, rect.centery - 12, 24, 24))
            label = f"{output.name}" + (f" ×{recipe.count}" if recipe.count > 1 else "")
            color = cfg.color("text") if ok else cfg.color("text_dim")
            renderer.draw_text(label, (rect.x + 36, rect.y + 2), self._font_small, color)

            parts = []
            for item_id, need in recipe.ingredients:
                have = self._inventory.count(item_id)
                name = self._defs.item(item_id).name
                parts.append(f"{name}{have}/{need}")
            detail = "  ".join(parts)
            if recipe.station and recipe.station not in stations:
                need_station = cfg.text("ui_text", "sandbox_need_station", default="需要工作台")
                detail = f"{need_station}　{detail}"
            renderer.draw_text(detail, (rect.x + 36, rect.y + 16), self._font_small,
                               cfg.color("text_dim") if ok else dim(cfg.color("danger"), 0.9))

    def draw_cursor(self, stack: Stack | None, pos) -> None:
        if stack is None or pos is None:
            return
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        rect = Rect(pos[0] - 14, pos[1] - 14, 28, 28)
        self._draw_item_in_rect(rect, stack)
        width, _ = renderer.measure_text(str(stack.count), self._font_small)
        renderer.draw_text(str(stack.count), (rect.right - width, rect.bottom),
                           self._font_small, cfg.color("warm_core"))

    def draw_tooltip(self, text: str, pos) -> None:
        if not text or pos is None:
            return
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        width, height = renderer.measure_text(text, self._font_small)
        rect = Rect(pos[0] + 14, pos[1] - height - 8, width + 12, height + 8)
        if rect.right > renderer.width - 4:
            rect = rect.move_to(x=pos[0] - width - 20)
        draw_plain_panel(renderer, rect, cfg.color("dialog_bg"), 235,
                         border=dim(cfg.color("dialog_border"), 0.8), border_width=1)
        renderer.draw_text(text, (rect.x + 6, rect.y + 4), self._font_small, cfg.color("text"))

    def draw_hint(self, text: str) -> None:
        if not text:
            return
        renderer = self._ctx.renderer
        cfg = self._ctx.config
        width, _ = renderer.measure_text(text, self._font_small)
        draw_plain_panel(renderer, Rect(8, 8, width + 16, 22), cfg.color("dialog_bg"), 190)
        renderer.draw_text(text, (16, 12), self._font_small, cfg.color("text_dim"))

    @property
    def inventory_panel_rect(self) -> Rect:
        return self._inv_panel

    @property
    def crafting_panel_rect(self) -> Rect:
        return self._craft_panel
