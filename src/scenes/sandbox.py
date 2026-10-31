"""沙盒玩法场景（类 Terraria 原型）：挖矿、砍树、合成、放置、装备。

这一版是「试验田」：验证交互手感与数据结构，不接存档、不做战斗与生存数值。
"""

from __future__ import annotations

import logging

from ..core.context import SceneContext
from ..core.events import InputEvent, InputKind
from ..core.scene import Scene
from ..core.types import Rect, dim
from ..sandbox.crafting import Crafting
from ..sandbox.defs import Defs
from ..sandbox.inventory import Inventory, Stack
from ..sandbox.player import PhysicsConfig, Player
from ..sandbox.textures import ItemIcons, TileTextures
from ..sandbox.world import World, load_world_params
from ..ui.menu import ConfirmDialog
from ..ui.panels import build_vertical_gradient
from ..ui.sandbox_ui import SandboxUI
from .stage import PixelActor

log = logging.getLogger(__name__)

PANEL_NONE = None
PANEL_INVENTORY = "inventory"
PANEL_CRAFTING = "crafting"


class SandboxScene(Scene):
    scene_id = "sandbox"

    def __init__(self, ctx: SceneContext) -> None:
        super().__init__(ctx)
        cfg = ctx.config.section("sandbox")
        physics_cfg = cfg.get("physics", {})
        self._physics = PhysicsConfig(
            gravity=float(physics_cfg.get("gravity", 1000.0)),
            max_fall=float(physics_cfg.get("max_fall", 900.0)),
            move_speed=float(physics_cfg.get("move_speed", 148.0)),
            move_accel=float(physics_cfg.get("move_accel", 1500.0)),
            friction=float(physics_cfg.get("friction", 1900.0)),
            jump_velocity=float(physics_cfg.get("jump_velocity", 342.0)),
            reach_tiles=float(physics_cfg.get("reach_tiles", 5.5)),
        )
        self._inv_slots = int(cfg.get("inventory_slots", 32))
        self._hotbar_slots = int(cfg.get("hotbar_slots", 8))
        self._camera_lerp = float(cfg.get("camera_lerp", 8.0))
        self._darkness = float(cfg.get("darkness_alpha", 0.88))
        light_cfg = cfg.get("player_light", {})
        self._player_light_radius = float(light_cfg.get("radius_tiles", 7.5))
        self._player_light_strength = float(light_cfg.get("strength", 14))
        self._hint_text = str(cfg.get("hint", ""))

        self._defs = None
        self._world: World | None = None
        self._player: Player | None = None
        self._inventory: Inventory | None = None
        self._crafting: Crafting | None = None
        self._tiles: TileTextures | None = None
        self._icons: ItemIcons | None = None
        self._ui: SandboxUI | None = None
        self._sprite: PixelActor | None = None
        self._sky = None
        self._darkness_tex: list = []
        self._camera = [0.0, 0.0]
        self._panel = PANEL_NONE
        self._confirm: ConfirmDialog | None = None
        self._cursor: Stack | None = None
        self._selected = 0
        self._move_dir = 0
        self._jump = False
        self._dig_progress = 0.0
        self._dig_tile: tuple[int, int] | None = None
        self._dig_sound = 0.0
        self._mouse_world = (0.0, 0.0)
        self._hover_slot: int | None = None
        self._hover_recipe: int | None = None
        self._tooltip = ""
        self._elapsed = 0.0

    # --- 生命周期 -----------------------------------------------------
    def enter(self) -> None:
        ctx = self.ctx
        self.ctx.state.current_scene_id = self.scene_id
        self._defs = Defs.load(ctx.paths.data_root)
        params = load_world_params(ctx.paths.data_root)
        self._world = World(self._defs, params)
        self._world.generate()

        self._inventory = Inventory(self._defs, self._inv_slots, self._hotbar_slots)
        for entry in params.get("player", {}).get("start_items", []):
            self._inventory.add(str(entry.get("item")), int(entry.get("count", 1)))
        self._crafting = Crafting(self._defs, self._inventory)
        self._player = Player(self._defs, self._world, self._inventory, self._physics)

        spawn_ratio = float(params.get("player", {}).get("spawn_x_ratio", 0.5))
        tx = int(self._world.width * spawn_ratio)
        ty = self._world.surface_y(tx)
        self._player.spawn(tx, ty - 1)

        self._tiles = TileTextures()
        self._tiles.build(ctx, self._defs)
        self._icons = ItemIcons()
        self._icons.build(ctx, self._defs, self._tiles)
        self._ui = SandboxUI(ctx, self._defs, self._inventory, self._icons)

        character = ctx.data.character("anon")
        self._sprite = PixelActor(ctx, character)
        self._sprite.scale = 1.0
        self._sprite.ground_y = 0.0

        self._sky = build_vertical_gradient(
            ctx.renderer,
            ctx.config.color("sky_day_top"),
            ctx.config.color("sky_day_bottom"),
            255,
            255,
            540,
        )
        self._build_darkness_levels()
        self._snap_camera()
        ctx.audio.play_ambience("wind")
        ctx.audio.play_music("unknown_world")
        log.info("沙盒世界就绪：%dx%d 格，出生点 (%d,%d)", self._world.width,
                 self._world.height, tx, ty)

    def exit(self) -> None:
        self._confirm = None
        self._cursor = None

    # --- 相机 / 光照 --------------------------------------------------
    def _viewport(self) -> tuple[int, int]:
        return self.ctx.renderer.size

    def _snap_camera(self) -> None:
        if self._player is None or self._world is None:
            return
        view_w, view_h = self._viewport()
        world_w = self._world.width * self._world.tile_size
        world_h = self._world.height * self._world.tile_size
        self._camera[0] = max(0.0, min(world_w - view_w, self._player.x - view_w / 2))
        self._camera[1] = max(0.0, min(world_h - view_h, self._player.y - view_h / 2))

    def _follow_camera(self, dt: float) -> None:
        if self._player is None or self._world is None:
            return
        view_w, view_h = self._viewport()
        world_w = self._world.width * self._world.tile_size
        world_h = self._world.height * self._world.tile_size
        target_x = self._player.x - view_w / 2
        target_y = self._player.y - self._physics.height / 2 - view_h / 2
        target_x = max(0.0, min(world_w - view_w, target_x))
        target_y = max(0.0, min(world_h - view_h, target_y))
        factor = min(1.0, self._camera_lerp * dt)
        self._camera[0] += (target_x - self._camera[0]) * factor
        self._camera[1] += (target_y - self._camera[1]) * factor

    def _build_darkness_levels(self) -> None:
        """预生成 16 档黑暗贴图：按光照档位直接贴，避免每帧算 alpha。"""
        renderer = self.ctx.renderer
        ts = self._world.tile_size
        self._darkness_tex = []
        for level in range(16):
            darkness = 1.0 - level / 15.0
            alpha = int((darkness ** 1.35) * 255 * self._darkness)
            data = bytes((0, 0, 0, alpha)) * (ts * ts)
            self._darkness_tex.append(renderer.create_texture(ts, ts, data))

    def _rebuild_light(self) -> None:
        if self._world is not None:
            self._world.rebuild_light()

    # --- 每帧 ---------------------------------------------------------
    def update(self, dt: float) -> None:
        self._elapsed += dt
        if self._world is None or self._player is None:
            return
        if self._confirm is not None:
            return

        self._player.update(dt, self._move_dir, self._jump)
        self._jump = False
        self._follow_camera(dt)
        self._sprite.ground_y = self._player.y
        self._sprite.x = self._player.x
        self._sprite.set_pose(self._player.pose)
        self._sprite.flip = self._player.facing < 0
        self._sprite.update(dt)

        if self._world.light_dirty:
            self._rebuild_light()

        self._update_pointer()
        if self._panel is PANEL_NONE:
            self._update_mining(dt)
        else:
            self._dig_tile = None
            self._dig_progress = 0.0

    def _mouse_position(self):
        return self.ctx.mouse.pos

    def _update_pointer(self) -> None:
        pos = self._mouse_position()
        if pos is None:
            return
        cam_x, cam_y = self._camera
        self._mouse_world = (pos[0] + cam_x, pos[1] + cam_y)
        self._hover_slot = None
        self._hover_recipe = None
        self._tooltip = ""
        if self._ui is None or self._inventory is None or self._defs is None:
            return
        if self._panel == PANEL_INVENTORY:
            index = self._ui.inventory_index_at(pos)
            self._hover_slot = index
            if index is not None:
                stack = self._inventory.get(index)
                if stack:
                    self._tooltip = self._defs.item(stack.item_id).name
        elif self._panel == PANEL_CRAFTING:
            self._hover_recipe = self._ui.recipe_index_at(pos)
        else:
            hit = self._ui.hotbar_index_at(pos)
            if hit is not None:
                self._hover_slot = hit
                stack = self._inventory.get(hit)
                if stack:
                    self._tooltip = self._defs.item(stack.item_id).name

    # --- 挖掘 ---------------------------------------------------------
    def _target_tile(self) -> tuple[int, int] | None:
        if self._world is None:
            return None
        ts = self._world.tile_size
        tx = int(self._mouse_world[0] // ts)
        ty = int(self._mouse_world[1] // ts)
        if not self._world.in_bounds(tx, ty):
            return None
        return (tx, ty)

    def _selected_item(self):
        if self._inventory is None or self._defs is None:
            return None
        stack = self._inventory.get(self._selected)
        if stack is None:
            return None
        return self._defs.item(stack.item_id)

    def _update_mining(self, dt: float) -> None:
        if not self.ctx.mouse.left or self._player is None or self._world is None:
            self._dig_progress = 0.0
            self._dig_tile = None
            return
        if self._cursor is not None:
            return
        target = self._target_tile()
        if target is None:
            return
        tx, ty = target
        tile = self._world.tile_at(tx, ty)
        if tile.is_air:
            self._dig_progress = 0.0
            self._dig_tile = None
            return
        if not self._player.in_reach(tx, ty):
            self._dig_tile = None
            self._dig_progress = 0.0
            return
        item = self._selected_item()
        tool = item.tool if item and item.tool else None
        if tile.tool != "any" and tool != tile.tool:
            self._dig_tile = None
            self._dig_progress = 0.0
            self._hint_need(tile.tool)
            return
        if self._dig_tile != target:
            self._dig_tile = target
            self._dig_progress = 0.0
        power = item.power if item and item.tool else 0.45
        self._dig_progress += dt * power / max(0.05, tile.hardness)
        self._dig_sound -= dt
        if self._dig_sound <= 0:
            self._dig_sound = 0.22
            self.ctx.audio.play_sfx("dig_hard" if tile.hardness > 0.9 else "dig_soft")
        if self._dig_progress >= 1.0:
            self._break_tile(tx, ty)

    def _hint_need(self, tool: str) -> None:
        if self._defs is None:
            return
        key = "sandbox_need_pickaxe" if tool == "pickaxe" else "sandbox_need_axe"
        self._hint = self.ctx.config.text("ui_text", key, default="")

    def _break_tile(self, tx: int, ty: int) -> None:
        world = self._world
        inventory = self._inventory
        if world is None or inventory is None or self._defs is None:
            return
        tile = world.tile_at(tx, ty)
        world.set_tile(tx, ty, "air")
        if tile.drop:
            leftover = inventory.add(tile.drop, 1)
            if leftover == 0:
                self.ctx.audio.play_sfx("pickup")
        if tile.key == "trunk":
            self.ctx.audio.play_sfx("chop")
            self._decay_leaves(tx, ty)
        self._dig_progress = 0.0
        self._dig_tile = None

    def _decay_leaves(self, tx: int, ty: int) -> None:
        world = self._world
        if world is None or self._defs is None:
            return
        leaves_id = self._defs.tile_by_key("leaves").id
        trunk_id = self._defs.tile_by_key("trunk").id
        for oy in range(ty - 5, ty + 1):
            for ox in range(tx - 2, tx + 3):
                if world.id_at(ox, oy) != leaves_id:
                    continue
                supported = any(
                    world.id_at(ox + dx, oy + dy) == trunk_id
                    for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                )
                if not supported:
                    world.set_tile(ox, oy, "air")

    # --- 放置 ---------------------------------------------------------
    def _try_place(self, tx: int, ty: int) -> None:
        world = self._world
        inventory = self._inventory
        player = self._player
        if world is None or inventory is None or player is None or self._defs is None:
            return
        item = self._selected_item()
        if item is None or not item.is_placeable:
            return
        if world.id_at(tx, ty) != self._defs.air_id():
            return
        if not player.in_reach(tx, ty):
            return
        ts = world.tile_size
        tile_rect = (tx * ts, ty * ts, tx * ts + ts, ty * ts + ts)
        left, top, right, bottom = player.box()
        if not (tile_rect[2] <= left or tile_rect[0] >= right or
                tile_rect[3] <= top or tile_rect[1] >= bottom):
            return
        supported = any(world.is_solid(tx + dx, ty + dy)
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if not supported:
            return
        world.set_tile(tx, ty, item.tile)
        stack = inventory.get(self._selected)
        if stack is not None:
            stack.count -= 1
            if stack.count <= 0:
                inventory.set(self._selected, None)
        self.ctx.audio.play_sfx("place")

    # --- 输入 ---------------------------------------------------------
    def handle_event(self, event: InputEvent) -> None:
        if self._confirm is not None:
            self._confirm.handle_event(event)
            if not self._confirm.active:
                if self._confirm.result == "yes":
                    self.ctx.router.goto_title()
                self._confirm = None
            return

        if event.kind == InputKind.CANCEL:
            if self._panel is not PANEL_NONE:
                self._close_panel()
            else:
                self._open_confirm()
            return
        if event.kind == InputKind.KEY:
            self._handle_key(event.key)
            return
        if event.kind == InputKind.MOVE_LEFT:
            self._move_dir = -1
            return
        if event.kind == InputKind.MOVE_RIGHT:
            self._move_dir = 1
            return
        if event.kind == InputKind.MOVE_STOP:
            self._move_dir = 0
            return
        if event.kind == InputKind.ADVANCE:
            self._jump = True
            return
        if event.kind == InputKind.CLICK:
            self._handle_click(event.pos)
            return
        if event.kind == InputKind.CLICK_RIGHT:
            self._handle_right_click()
            return

    def _handle_key(self, key: str | None) -> None:
        if not key:
            return
        if key in ("e", "tab"):
            self._toggle_panel(PANEL_INVENTORY)
            return
        if key == "c":
            self._toggle_panel(PANEL_CRAFTING)
            return
        if key.isdigit():
            index = int(key)
            if 1 <= index <= self._hotbar_slots:
                self._selected = index - 1
                self.ctx.audio.play_sfx("ui_click")

    def _toggle_panel(self, panel: str) -> None:
        self._panel = PANEL_NONE if self._panel == panel else panel
        self.ctx.audio.play_sfx("ui_click")

    def _close_panel(self) -> None:
        self._panel = PANEL_NONE
        if self._cursor is not None:
            self._return_cursor()
        self.ctx.audio.play_sfx("ui_click")

    def _return_cursor(self) -> None:
        if self._cursor is not None and self._inventory is not None:
            leftover = self._inventory.add(self._cursor.item_id, self._cursor.count)
            if leftover > 0:
                self._cursor.count = leftover
            else:
                self._cursor = None

    def _handle_click(self, pos) -> None:
        if self._ui is None or self._inventory is None:
            return
        if self._panel == PANEL_INVENTORY:
            index = self._ui.inventory_index_at(pos)
            if index is not None:
                self._slot_click(index)
            return
        if self._panel == PANEL_CRAFTING:
            recipe_index = self._ui.recipe_index_at(pos)
            if recipe_index is not None:
                self._craft_at(recipe_index)
            return
        hit = self._ui.hotbar_index_at(pos)
        if hit is not None:
            self._selected = hit
            self.ctx.audio.play_sfx("ui_click")
            return
        target = self._target_tile()
        if target is not None:
            self._update_dig_instant(target)

    def _update_dig_instant(self, target: tuple[int, int]) -> None:
        """单击给一点进度，避免「按住才生效」的手感门槛。"""
        if self._dig_tile != target:
            self._dig_tile = target
            self._dig_progress = 0.0
        self._dig_progress += 0.04

    def _handle_right_click(self) -> None:
        if self._panel is not PANEL_NONE or self._confirm is not None:
            return
        target = self._target_tile()
        if target is not None:
            self._try_place(*target)

    def _slot_click(self, index: int) -> None:
        if self._inventory is None:
            return
        slot = self._inventory.get(index)
        if self._cursor is None:
            if slot is not None:
                self._cursor = slot
                self._inventory.set(index, None)
                self.ctx.audio.play_sfx("ui_click")
            return
        if slot is None:
            self._inventory.set(index, self._cursor)
            self._cursor = None
            self.ctx.audio.play_sfx("place")
            return
        if slot.item_id == self._cursor.item_id:
            max_stack = self._defs.item(slot.item_id).stack
            space = max_stack - slot.count
            moved = min(space, self._cursor.count)
            slot.count += moved
            self._cursor.count -= moved
            if self._cursor.count <= 0:
                self._cursor = None
            self.ctx.audio.play_sfx("ui_click")
            return
        self._inventory.set(index, self._cursor)
        self._cursor = slot
        self.ctx.audio.play_sfx("ui_click")

    def _craft_at(self, recipe_index: int) -> None:
        if self._defs is None or self._crafting is None or self._world is None or self._player is None:
            return
        recipes = self._defs.recipes
        if recipe_index >= len(recipes):
            return
        stations = self._crafting.stations_near(self._world, self._player)
        if self._crafting.craft(recipes[recipe_index], stations):
            self.ctx.audio.play_sfx("craft")
        else:
            self.ctx.audio.play_sfx("ui_cancel")

    def _open_confirm(self) -> None:
        cfg = self.ctx.config
        self._confirm = ConfirmDialog(
            self.ctx,
            title=cfg.text("ui_text", "confirm_title", default=""),
            body=cfg.text("ui_text", "confirm_body", default=""),
            yes=cfg.text("ui_text", "confirm_yes", default="是"),
            no=cfg.text("ui_text", "confirm_no", default="否"),
        )

    # --- 绘制 ---------------------------------------------------------
    def draw(self) -> None:
        renderer = self.ctx.renderer
        cfg = self.ctx.config
        renderer.clear(cfg.color("void"))
        if self._world is None or self._player is None or self._defs is None:
            return
        renderer.draw_texture(self._sky, Rect(0, 0, *renderer.size))
        cam_x, cam_y = int(self._camera[0]), int(self._camera[1])

        self._draw_parallax(cam_x, cam_y)
        self._draw_tiles(cam_x, cam_y)
        self._draw_mining(cam_x, cam_y)
        self._draw_player(cam_x, cam_y)
        self._draw_light(cam_x, cam_y)
        self._draw_ui()
        if self._confirm is not None:
            self._confirm.draw()

    def _draw_parallax(self, cam_x: int, cam_y: int) -> None:
        renderer = self.ctx.renderer
        cfg = self.ctx.config
        width, height = renderer.size
        import math

        for index, (parallax, base_y, color) in enumerate((
            (0.25, 300.0, dim(cfg.color("mid"), 1.0)),
            (0.45, 360.0, cfg.color("dark")),
        )):
            points = [(0.0, float(height))]
            offset = cam_x * parallax
            for step in range(0, 9):
                x = step * width / 8
                wave = math.sin((x + offset) * 0.006 + index * 2.1) * 26
                wave += math.sin((x + offset) * 0.013 + index) * 12
                points.append((x, base_y + wave - cam_y * parallax * 0.15))
            points.append((float(width), float(height)))
            renderer.draw_polygon(points, color, alpha=255 if index else 235)

    def _draw_tiles(self, cam_x: int, cam_y: int) -> None:
        world = self._world
        renderer = self.ctx.renderer
        view_w, view_h = renderer.size
        ts = world.tile_size
        x0 = max(0, cam_x // ts)
        y0 = max(0, cam_y // ts)
        x1 = min(world.width - 1, (cam_x + view_w) // ts + 1)
        y1 = min(world.height - 1, (cam_y + view_h) // ts + 1)
        textures = self._tiles
        for ty in range(y0, y1 + 1):
            row = ty * world.width
            for tx in range(x0, x1 + 1):
                tile_id = world.tiles[row + tx]
                if tile_id == 0:
                    continue
                tile = self._defs.tile_by_id(tile_id)
                texture = textures.get(tile.key)
                if texture is None:
                    continue
                renderer.draw_texture(texture, Rect(tx * ts - cam_x, ty * ts - cam_y, ts, ts))

    def _draw_mining(self, cam_x: int, cam_y: int) -> None:
        if self._dig_tile is None or self._dig_progress <= 0.0:
            return
        world = self._world
        ts = world.tile_size
        tx, ty = self._dig_tile
        rect = Rect(tx * ts - cam_x, ty * ts - cam_y, ts, ts)
        renderer = self.ctx.renderer
        cfg = self.ctx.config
        renderer.draw_rect(rect, cfg.color("void"), alpha=int(140 * min(1.0, self._dig_progress)))
        renderer.draw_frame(rect, cfg.color("warm_core"), width=1,
                            alpha=int(90 + 120 * min(1.0, self._dig_progress)))

    def _draw_player(self, cam_x: int, cam_y: int) -> None:
        if self._sprite is None:
            return
        self._sprite.draw(self.ctx.renderer, offset=(-float(cam_x), -float(cam_y)))

    def _draw_light(self, cam_x: int, cam_y: int) -> None:
        """按地块贴黑暗档位：全局光照 + 玩家自带的灯光。"""
        if not self._darkness_tex or self._world is None or self._player is None:
            return
        renderer = self.ctx.renderer
        world = self._world
        ts = world.tile_size
        view_w, view_h = renderer.size
        x0 = max(0, cam_x // ts)
        y0 = max(0, cam_y // ts)
        x1 = min(world.width - 1, (cam_x + view_w) // ts + 1)
        y1 = min(world.height - 1, (cam_y + view_h) // ts + 1)
        px = self._player.x / ts
        py = (self._player.y - self._physics.height / 2) / ts
        radius = self._player_light_radius
        strength = self._player_light_strength
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                light = world.light_at(tx, ty)
                dx = tx + 0.5 - px
                dy = ty + 0.5 - py
                dist = (dx * dx + dy * dy) ** 0.5
                if dist < radius:
                    local = int(strength * (1.0 - dist / radius))
                    if local > light:
                        light = local
                if light >= world.light_max:
                    continue
                texture = self._darkness_tex[light]
                renderer.draw_texture(texture, Rect(tx * ts - cam_x, ty * ts - cam_y, ts, ts))

    def _draw_ui(self) -> None:
        if self._ui is None or self._inventory is None or self._defs is None:
            return
        ui = self._ui
        ui.draw_hotbar(self._selected)
        if self._panel == PANEL_INVENTORY:
            ui.draw_inventory(self._hover_slot)
        elif self._panel == PANEL_CRAFTING:
            stations = self._crafting.stations_near(self._world, self._player)
            can = [self._crafting.available(recipe, stations) for recipe in self._defs.recipes]
            ui.draw_crafting(self._defs.recipes, stations, can, self._hover_recipe)
        ui.draw_hint(self._hint_text)
        selected = self._selected_item()
        if selected is not None:
            name = selected.name
            renderer = self.ctx.renderer
            width, _ = renderer.measure_text(name, ui._font_small)  # noqa: SLF001
            renderer.draw_text(name, (renderer.width / 2 - width / 2, ui._hotbar_y - 20),
                               ui._font_small, self.ctx.config.color("text_dim"))  # noqa: SLF001
        ui.draw_tooltip(self._tooltip, self._mouse_position())
        ui.draw_cursor(self._cursor, self._mouse_position())
