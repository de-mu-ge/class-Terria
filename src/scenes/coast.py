"""海岸世界场景：天空 / 远海 / 地形 / 海水 / 生态对象 / 生物 / 洞穴 / 交互。

分层绘制顺序（从远到近）：
天空 → 星月 → 远海 → 海岬剪影 → 云 → 地形 → 生态对象 → 生物 → 海水
→ 玩家 → 水面高光与光束 → 昼夜环境光 → 洞穴黑暗 → UI
"""

from __future__ import annotations

import logging
import math
import random

from ..coast.daycycle import DayCycle
from ..coast.defs import CoastDefs
from ..coast.entities import Bird, Crab, FishSchool, Prop, PropWorld, draw_prop
from ..coast.inventory import CoastInventory, Stack
from ..coast.player import CoastPhysics, CoastPlayer
from ..coast.textures import ItemIcons, TileTextures
from ..coast.world import CoastWorld
from ..core.context import SceneContext
from ..core.events import InputEvent, InputKind
from ..core.scene import Scene
from ..core.types import Color, Rect, mix
from ..ui.coast_ui import CoastUI
from ..ui.menu import ConfirmDialog
from .stage import PixelActor

log = logging.getLogger(__name__)

PANEL_NONE = None
PANEL_INVENTORY = "inventory"
PANEL_CRAFT = "craft"
PANEL_CHEST = "chest"

_POSE_MAP = {
    "idle": "idle",
    "walk_1": "walk_1",
    "walk_2": "walk_2",
    "jump": "idle",
    "crouch": "sitting",
    "swim": "lying",
}


class CoastScene(Scene):
    scene_id = "coast"

    def __init__(self, ctx: SceneContext) -> None:
        super().__init__(ctx)
        cfg = ctx.config.section("coast")
        physics_cfg = cfg.get("physics", {})
        self._physics = CoastPhysics(
            gravity=float(physics_cfg.get("gravity", 1200.0)),
            max_fall=float(physics_cfg.get("max_fall", 820.0)),
            walk_speed=float(physics_cfg.get("walk_speed", 148.0)),
            walk_accel=float(physics_cfg.get("walk_accel", 1500.0)),
            friction=float(physics_cfg.get("friction", 1700.0)),
            jump_velocity=float(physics_cfg.get("jump_velocity", 400.0)),
            crouch_speed=float(physics_cfg.get("crouch_speed", 62.0)),
            water_speed=float(physics_cfg.get("water_speed", 112.0)),
            water_accel=float(physics_cfg.get("water_accel", 760.0)),
            water_gravity=float(physics_cfg.get("water_gravity", 88.0)),
            water_buoyancy=float(physics_cfg.get("water_buoyancy", 210.0)),
            swim_up=float(physics_cfg.get("swim_up", 430.0)),
            swim_down=float(physics_cfg.get("swim_down", 330.0)),
            water_drag=float(physics_cfg.get("water_drag", 2.6)),
            max_swim_up=float(physics_cfg.get("max_swim_up", 190.0)),
            max_swim_down=float(physics_cfg.get("max_swim_down", 170.0)),
        )
        water_cfg = cfg.get("water", {})
        self._surface_alpha = float(water_cfg.get("surface_alpha", 138))
        self._deep_alpha = float(water_cfg.get("deep_alpha", 238))
        self._shaft_alpha = int(water_cfg.get("shaft_alpha", 18))
        self._shaft_count = int(water_cfg.get("shaft_count", 4))
        self._snow_count = int(water_cfg.get("snow_count", 70))
        self._surface_color = ctx.config.color("snow")
        light_cfg = cfg.get("light", {})
        self._player_light = float(light_cfg.get("player_strength", 11))
        self._player_light_radius = float(light_cfg.get("player_radius_tiles", 6.5))
        self._cave_alpha = int(light_cfg.get("cave_alpha", 178))
        self._mouth_light = float(light_cfg.get("mouth_strength", 13))
        self._camera_lerp = float(cfg.get("camera_lerp", 5.0))
        self._controls_text = cfg.get("controls", "")
        texts = cfg.get("texts", {})
        self._texts = texts

        self._defs: CoastDefs | None = None
        self._world: CoastWorld | None = None
        self._player: CoastPlayer | None = None
        self._inventory: CoastInventory | None = None
        self._props: PropWorld | None = None
        self._cycle: DayCycle | None = None
        self._ui: CoastUI | None = None
        self._tiles: TileTextures | None = None
        self._icons: ItemIcons | None = None
        self._sprite: PixelActor | None = None
        self._fish: list[FishSchool] = []
        self._birds: list[Bird] = []
        self._crabs: list[Crab] = []
        self._snow: list[list[float]] = []
        self._stars: list[tuple[float, float, float, float]] = []
        self._clouds: list[list[float]] = []
        self._camera = [0.0, 0.0]
        self._elapsed = 0.0
        self._panel = PANEL_NONE
        self._confirm: ConfirmDialog | None = None
        self._focus: Prop | None = None
        self._chest: Prop | None = None
        self._cursor: Stack | None = None
        self._hover_slot: int | None = None
        self._hover_chest: int | None = None
        self._hover_craft: int | None = None
        self._sky_texture = None
        self._sky_key: tuple | None = None
        self._cave_mouth = (0.0, 0.0)
        self._tide_prev = 0.0
        self._tide_delta = 0.0

    # --- 生命周期 -----------------------------------------------------
    def enter(self) -> None:
        ctx = self.ctx
        self.ctx.state.current_scene_id = self.scene_id
        self._defs = CoastDefs.load(ctx.paths.data_root)
        self._world = CoastWorld(self._defs)
        self._world.generate()
        self._world.update_tide(0.0)

        self._tiles = TileTextures()
        self._tiles.build(ctx, self._defs)
        self._icons = ItemIcons()
        self._icons.build(ctx, self._defs)

        self._inventory = CoastInventory(self._defs, slots=24)
        for entry in self._defs.world.get("player", {}).get("start_items", []):
            self._inventory.add(str(entry.get("item")), int(entry.get("count", 1)))

        self._player = CoastPlayer(self._world, self._physics)
        spawn_x = self._find_spawn_x()
        spawn_y = self._world.surface_y(spawn_x)
        self._player.spawn(spawn_x, spawn_y)

        self._props = PropWorld(self._defs)
        self._populate_objects()
        self._seed_spawn_props()
        self._populate_creatures()

        day_cfg = self._defs.world.get("day", {})
        merged_day = dict(ctx.config.value("coast", "day", default={}))
        merged_day.update({k: v for k, v in day_cfg.items() if k not in merged_day})
        merged_day["start_time"] = day_cfg.get("start_time", merged_day.get("start_time", 0.27))
        merged_day["length_seconds"] = day_cfg.get(
            "length_seconds", merged_day.get("length_seconds", 420.0))
        self._cycle = DayCycle(merged_day)
        self._cycle.time = float(merged_day.get("start_time", 0.27))

        self._ui = CoastUI(ctx, self._defs, self._inventory, self._icons)

        character = ctx.data.character("anon")
        self._sprite = PixelActor(ctx, character)
        self._sprite.scale = 1.0

        cave_cfg = self._defs.world.get("cave", {})
        self._cave_mouth = (float(cave_cfg.get("mouth_x", 32) * self._defs.tile_size),
                            float(cave_cfg.get("mouth_y", 84) * self._defs.tile_size))

        self._build_stars_and_clouds()
        self._snap_camera()
        ctx.audio.play_ambience("waves")
        ctx.audio.play_music("unknown_world")
        log.info("海岸世界就绪：%dx%d 格，海平面 %.1f，对象 %d 个",
                 self._world.width, self._world.height, self._world.sea_level_base,
                 len(self._props.props))

    def exit(self) -> None:
        self._panel = PANEL_NONE
        self._confirm = None
        self._cursor = None

    # --- 初始化辅助 ---------------------------------------------------
    def _find_spawn_x(self) -> int:
        """出生点：水线往陆地一侧退 5 格，保证一进游戏就能看见海。"""
        world = self._world
        cfg_x = int(self._defs.world.get("player", {}).get("spawn_x_tiles", 0))
        beach_end = int(world.beach_cfg.get("end", 132))
        for tx in range(beach_end - 40, world.width - 2):
            if world.surface_y(tx) > world.sea_level_base:
                return max(beach_end - 40, tx - 5)
        return cfg_x or beach_end - 10

    def _populate_objects(self) -> None:
        world = self._world
        defs = self._defs
        rng = random.Random(int(defs.world.get("seed", 1)) + 17)
        ts = world.tile_size
        spec = defs.world.get("objects", {})
        cave_air = sorted(world.cave_air)
        for obj_id, cfg in spec.items():
            obj = defs.obj(obj_id)
            count = int(cfg.get("count", 0))
            if obj_id == "crystal":
                rng.shuffle(cave_air)
                placed = 0
                for idx in cave_air:
                    if placed >= count:
                        break
                    tx, ty = idx % world.width, idx // world.width
                    if world.is_solid(tx, ty) or not world.is_solid(tx, ty + 1):
                        continue
                    self._props.add(obj_id, (tx + 0.5) * ts, (ty + 1) * ts)
                    placed += 1
                continue
            placed = 0
            attempts = 0
            while placed < count and attempts < count * 120:
                attempts += 1
                tx = rng.randrange(2, world.width - 2)
                surface = world.surface_y(tx)
                ty = surface
                if ty - 1 < 0:
                    continue
                zone = world.zone_at(tx, ty - 1)
                if obj.zones and zone not in obj.zones:
                    continue
                if world.is_solid(tx, ty - 1):
                    continue
                x = (tx + 0.5) * ts + rng.uniform(-5.0, 5.0)
                y = ty * ts
                self._props.add(obj_id, x, y)
                placed += 1

    def _seed_spawn_props(self) -> None:
        """出生点附近固定放几件东西，保证一睁眼就有可做的事。"""
        world = self._world
        ts = world.tile_size
        base = int(self._player.x // ts)
        plan = (("driftwood", -6), ("shell", -3), ("stone_small", 3),
                ("beach_grass", -9), ("beach_grass", 6), ("shell", 9))
        for obj_id, offset in plan:
            tx = base + offset
            if not world.in_bounds(tx, 2):
                continue
            surface = world.surface_y(tx)
            self._props.add(obj_id, (tx + 0.5) * ts, surface * ts)

    def _populate_creatures(self) -> None:
        world = self._world
        rng = random.Random(int(self._defs.world.get("seed", 1)) + 91)
        ts = world.tile_size
        creatures = self._defs.world.get("creatures", {})
        for _ in range(int(creatures.get("fish_schools", 6))):
            tx = rng.randrange(int(world.beach_cfg.get("end", 132)) + 10, world.width - 10)
            depth = rng.uniform(4, 26)
            x = (tx + 0.5) * ts
            y = (world.sea_level_base + depth) * ts
            self._fish.append(FishSchool(x=x, y=y, radius=rng.uniform(30, 60),
                                         count=rng.randint(3, 6),
                                         speed=rng.uniform(16, 34),
                                         direction=rng.choice((-1, 1))))
        for _ in range(int(creatures.get("birds", 4))):
            self._birds.append(Bird(x=rng.uniform(0, 900),
                                    y=rng.uniform(60, 190),
                                    speed=rng.uniform(24, 46),
                                    phase=rng.uniform(0, 6.28),
                                    direction=rng.choice((-1, 1)),
                                    span=float(world.width * ts * 0.5)))
        for _ in range(int(creatures.get("crabs", 3))):
            tx = rng.randrange(int(world.beach_cfg.get("start", 46)) + 6,
                               int(world.beach_cfg.get("end", 132)) - 6)
            surface = world.surface_y(tx)
            self._crabs.append(Crab(x=(tx + 0.5) * ts, y=surface * ts,
                                    speed=rng.uniform(12, 26),
                                    direction=rng.choice((-1, 1))))

    def _build_stars_and_clouds(self) -> None:
        rng = random.Random(4242)
        self._stars = [(rng.uniform(0, 960), rng.uniform(0, 260),
                        rng.choice((1.0, 1.0, 2.0)), rng.uniform(0, 6.28))
                       for _ in range(70)]
        self._clouds = [[rng.uniform(-200, 1100), rng.uniform(40, 190),
                         rng.uniform(0.6, 1.4), rng.uniform(4, 12)]
                        for _ in range(5)]
        self._snow = [[rng.uniform(0, 960), rng.uniform(0, 540),
                       rng.uniform(6, 22), rng.uniform(0, 6.28)] for _ in range(self._snow_count)]

    # --- 相机 ---------------------------------------------------------
    def _snap_camera(self) -> None:
        view_w, view_h = self.ctx.renderer.size
        world = self._world
        self._camera[0] = max(0.0, min(world.width * world.tile_size - view_w,
                                       self._player.x - view_w / 2))
        self._camera[1] = max(0.0, min(world.height * world.tile_size - view_h,
                                       self._player.y - view_h * 0.6))

    def _follow_camera(self, dt: float) -> None:
        view_w, view_h = self.ctx.renderer.size
        world = self._world
        target_x = self._player.x - view_w / 2
        target_y = self._player.y - view_h * 0.6
        target_x = max(0.0, min(world.width * world.tile_size - view_w, target_x))
        target_y = max(0.0, min(world.height * world.tile_size - view_h, target_y))
        factor = min(1.0, self._camera_lerp * dt)
        self._camera[0] += (target_x - self._camera[0]) * factor
        self._camera[1] += (target_y - self._camera[1]) * factor

    # --- 每帧 ---------------------------------------------------------
    def update(self, dt: float) -> None:
        if self._confirm is not None:
            return
        self._elapsed += dt
        world = self._world
        world.update_tide(self._elapsed)
        self._cycle.update(dt)

        keys = self.ctx.keys
        move_dir = 0 if self._panel is not PANEL_NONE else keys.axis_x()
        jump_held = keys.down("jump") and self._panel is PANEL_NONE
        down_held = keys.down("down")
        self._player.update(dt, move_dir, jump_held, down_held)
        self._follow_camera(dt)

        self._sprite.ground_y = self._player.y
        self._sprite.x = self._player.x
        self._sprite.set_pose(_POSE_MAP.get(self._player.pose, "idle"))
        self._sprite.flip = self._player.facing < 0
        self._sprite.update(dt)

        player_x, player_y = self._player.center()
        for school in self._fish:
            school.update(dt, player_x, player_y)
        for bird in self._birds:
            bird.update(dt, world.width * world.tile_size)
        for crab in self._crabs:
            crab.update(dt, world)

        self._update_snow(dt)
        self._ui.update(dt)

        self._focus = None
        if self._panel is PANEL_NONE:
            reach = self._physics.reach * world.tile_size + 26
            self._focus = self._props.nearest(player_x, player_y, reach)

        self._tide_delta = world.sea_level - self._tide_prev
        self._tide_prev = world.sea_level
        self._update_hover()

    def _update_hover(self) -> None:
        pos = self.ctx.mouse.pos
        self._hover_slot = None
        self._hover_chest = None
        self._hover_craft = None
        if pos is None or self._ui is None:
            return
        if self._panel == PANEL_INVENTORY:
            self._hover_slot = self._ui.grid_index_at(pos)
        elif self._panel == PANEL_CRAFT:
            self._hover_craft = self._ui.craft_index_at(pos, self._defs.recipes)
        elif self._panel == PANEL_CHEST:
            self._hover_chest = self._ui.chest_index_at(pos, 8)
            self._hover_slot = self._ui.hotbar_index_at(pos)

    def _update_snow(self, dt: float) -> None:
        for particle in self._snow:
            particle[1] += particle[2] * dt
            particle[0] += math.sin(self._elapsed * 0.6 + particle[3]) * 6 * dt
            if particle[1] > 540 + 20:
                particle[1] = -20
                particle[0] = random.uniform(0, 960)
            if particle[0] < -20:
                particle[0] = 980
            elif particle[0] > 980:
                particle[0] = -20

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
            self._on_key(event.key)
            return
        if event.kind == InputKind.CLICK:
            self._on_click(event.pos)
            return
        if event.kind == InputKind.CLICK_RIGHT:
            if self._panel is PANEL_NONE:
                self._try_place()
            return

    def _on_key(self, key: str | None) -> None:
        if not key:
            return
        if key in ("i", "tab"):
            self._toggle_panel(PANEL_INVENTORY)
        elif key == "c":
            self._toggle_panel(PANEL_CRAFT)
        elif key == "e" and self._panel is PANEL_NONE:
            self._interact()
        elif key == "f" and self._panel is PANEL_NONE:
            self._try_place()
        elif key.isdigit():
            index = int(key) - 1
            if 0 <= index < 8:
                self._ui.selected = index
                self.ctx.audio.play_sfx("ui_click")

    def _toggle_panel(self, panel: str) -> None:
        if self._panel == panel:
            self._close_panel()
        else:
            self._panel = panel
            self._chest = None
            self.ctx.audio.play_sfx("ui_click")

    def _close_panel(self) -> None:
        self._panel = PANEL_NONE
        self._chest = None
        if self._cursor is not None:
            leftover = self._inventory.add(self._cursor.item_id, self._cursor.count)
            self._cursor = None if leftover == 0 else Stack(self._cursor.item_id, leftover)
        self.ctx.audio.play_sfx("ui_click")

    def _on_click(self, pos) -> None:
        if self._panel is PANEL_NONE:
            slot = self._ui.hotbar_index_at(pos)
            if slot is not None:
                self._ui.selected = slot
                self.ctx.audio.play_sfx("ui_click")
            return
        if self._panel == PANEL_INVENTORY:
            index = self._ui.grid_index_at(pos)
            if index is not None:
                self._slot_click(index)
            return
        if self._panel == PANEL_CRAFT:
            index = self._ui.craft_index_at(pos, self._defs.recipes)
            if index is not None:
                self._craft(index)
            return
        if self._panel == PANEL_CHEST and self._chest is not None:
            index = self._ui.chest_index_at(pos, 8)
            if index is not None:
                self._chest_click(index)
                return
            hot = self._ui.hotbar_index_at(pos)
            if hot is not None:
                self._chest_deposit(hot)

    # --- 交互 ---------------------------------------------------------
    def _interact(self) -> None:
        prop = self._focus
        if prop is None:
            return
        obj = self._defs.obj(prop.obj_id)
        if obj.kind == "harvestable":
            if obj.harvest:
                leftover = self._inventory.add(obj.harvest.item, obj.harvest.count)
                gained = obj.harvest.count - leftover
                item_name = self._defs.item(obj.harvest.item).name
                if gained > 0:
                    self._ui.add_floating(f"+{gained} {item_name}", prop.x, prop.y - 26)
                    self.ctx.audio.play_sfx("pickup")
            prop.harvested = True
            return
        if prop.obj_id == "campfire":
            prop.lit = not prop.lit
            self.ctx.audio.play_sfx("ui_click")
            return
        if prop.obj_id == "torch":
            self._inventory.add("torch", 1)
            prop.harvested = True
            self._ui.add_floating("收回火把", prop.x, prop.y - 26)
            self.ctx.audio.play_sfx("pickup")
            return
        if prop.obj_id == "chest":
            if not prop.storage:
                prop.storage = [None] * 8
            self._chest = prop
            self._panel = PANEL_CHEST
            self.ctx.audio.play_sfx("ui_confirm")

    def _try_place(self) -> None:
        stack = self._inventory.get(self._ui.selected)
        if stack is None:
            return
        item = self._defs.item(stack.item_id)
        if item.kind != "placeable" or not item.object:
            return
        world = self._world
        ts = world.tile_size
        tx = int(self._player.x // ts)
        ty = int(self._player.y // ts)
        ground = world.solid_surface_below(tx, ty)
        if ground is None or ground <= 0:
            return
        obj = self._defs.obj(item.object)
        x = (tx + 0.5) * ts
        y = ground * ts
        self._props.add(item.object, x, y)
        self._inventory.remove(item.id, 1)
        self._ui.add_floating(f"放置 {obj.name}", x, y - 26)
        self.ctx.audio.play_sfx("place")

    def _craft(self, index: int) -> None:
        recipe = self._defs.recipes[index]
        for item_id, need in recipe.ingredients:
            if self._inventory.count(item_id) < need:
                self.ctx.audio.play_sfx("ui_cancel")
                return
        for item_id, need in recipe.ingredients:
            self._inventory.remove(item_id, need)
        self._inventory.add(recipe.output, recipe.count)
        output = self._defs.item(recipe.output)
        self._ui.add_floating(f"制作 {output.name}", self._player.x, self._player.y - 40)
        self.ctx.audio.play_sfx("craft")

    # --- 物品拖拽 -----------------------------------------------------
    def _slot_click(self, index: int) -> None:
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
            moved = min(max_stack - slot.count, self._cursor.count)
            slot.count += moved
            self._cursor.count -= moved
            if self._cursor.count <= 0:
                self._cursor = None
            return
        self._inventory.set(index, self._cursor)
        self._cursor = slot
        self.ctx.audio.play_sfx("ui_click")

    def _chest_click(self, index: int) -> None:
        chest = self._chest
        if chest is None:
            return
        stack = chest.storage[index]
        if stack is None:
            return
        leftover = self._inventory.add(stack.item_id, stack.count)
        if leftover == 0:
            chest.storage[index] = None
        else:
            stack.count = leftover
        self.ctx.audio.play_sfx("ui_click")

    def _chest_deposit(self, index: int) -> None:
        chest = self._chest
        if chest is None:
            return
        stack = self._inventory.get(index)
        if stack is None:
            return
        for slot_index, slot in enumerate(chest.storage):
            if slot is None:
                chest.storage[slot_index] = stack
                self._inventory.set(index, None)
                self.ctx.audio.play_sfx("place")
                return
            if slot.item_id == stack.item_id:
                max_stack = self._defs.item(slot.item_id).stack
                moved = min(max_stack - slot.count, stack.count)
                slot.count += moved
                stack.count -= moved
                if stack.count <= 0:
                    self._inventory.set(index, None)
                return
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
        sample = self._cycle.sample()
        world = self._world
        world.update_tide(self._elapsed)
        cam = (int(-self._camera[0]), int(-self._camera[1]))

        self._draw_sky(sample)
        self._draw_stars(sample)
        self._draw_sun_moon(sample)
        self._draw_distant_sea(sample, cam)
        self._draw_headlands(sample, cam)
        self._draw_clouds(sample)
        self._draw_tiles(cam)
        self._draw_props(cam)
        self._draw_creatures(cam, sample)
        self._draw_water(cam, sample)
        self._draw_player(cam)
        self._draw_surface(cam, sample)
        self._draw_surf(cam, sample)
        self._draw_shafts(cam, sample)
        self._draw_snow(cam, sample)
        self._draw_ambient(sample)
        self._draw_glow()
        self._draw_cave(cam)
        self._draw_ui(sample)
        if self._confirm is not None:
            self._confirm.draw()

    # --- 天空层 -------------------------------------------------------
    def _draw_sky(self, sample) -> None:
        renderer = self.ctx.renderer
        key = (sample.sky_top, sample.sky_bottom)
        if key != self._sky_key:
            data = bytearray(4 * 540)
            for y in range(540):
                t = y / 539
                color = mix(sample.sky_top, sample.sky_bottom, t)
                offset = y * 4
                data[offset] = color[0]
                data[offset + 1] = color[1]
                data[offset + 2] = color[2]
                data[offset + 3] = 255
            self._sky_texture = renderer.create_texture(1, 540, bytes(data))
            self._sky_key = key
        renderer.draw_texture(self._sky_texture, Rect(0, 0, 960, 540))

    def _draw_stars(self, sample) -> None:
        if sample.light > 0.42:
            return
        renderer = self.ctx.renderer
        alpha = int((0.42 - sample.light) / 0.42 * 210)
        for x, y, size, phase in self._stars:
            twinkle = 0.7 + 0.3 * math.sin(self._elapsed * 2 + phase)
            renderer.draw_rect(Rect(x, y, size, size), self.ctx.config.color("snow"),
                               alpha=int(alpha * twinkle))

    def _draw_sun_moon(self, sample) -> None:
        renderer = self.ctx.renderer
        x = sample.sun_x * 960
        y = sample.sun_y * 540
        if sample.light > 0.5:
            renderer.draw_round_rect(Rect(x - 46, y - 46, 92, 92),
                                     self.ctx.config.color("warm_core"), 46, alpha=26)
            renderer.draw_round_rect(Rect(x - 18, y - 18, 36, 36), (255, 240, 210), 18,
                                     alpha=225)
        else:
            renderer.draw_round_rect(Rect(x - 26, y - 26, 52, 52), (200, 220, 240), 26,
                                     alpha=32)
            renderer.draw_round_rect(Rect(x - 12, y - 12, 24, 24), (226, 236, 246), 12,
                                     alpha=215)

    def _draw_distant_sea(self, sample, cam) -> None:
        """远处海面：只在水平线附近叠几道很淡的反光，不画整条色带。"""
        renderer = self.ctx.renderer
        world = self._world
        sea_screen = world.sea_level * world.tile_size + cam[1]
        if sea_screen < 20 or sea_screen > 620:
            return
        glint = mix(sample.sky_bottom, sample.water_tint, 0.35)
        for index in range(16):
            wx = (index * 131 + self._elapsed * 2.5) % 1060 - 50
            wy = sea_screen - 3 - (index % 3) * 3
            renderer.draw_rect(Rect(wx, wy, 10 + (index % 4) * 6, 1), glint, alpha=70)

    def _open_water_span(self, cam) -> tuple[float, float] | None:
        """屏幕上「地形低于海平面」的横向区间，用来判断远景海岬该不该出现。"""
        world = self._world
        ts = world.tile_size
        first: float | None = None
        last: float | None = None
        for sx in range(0, 961, 12):
            tx = int((sx - cam[0]) // ts)
            if not world.in_bounds(tx, 0):
                continue
            if world.surface_y(tx) > world.sea_level + 1.5:
                if first is None:
                    first = float(sx)
                last = float(sx)
        if first is None or last is None:
            return None
        if (last - first) < 960 * 0.62:
            return None
        return (first, last)

    def _draw_headlands(self, sample, cam) -> None:
        span = self._open_water_span(cam)
        if span is None:
            return
        renderer = self.ctx.renderer
        world = self._world
        sea_screen = world.sea_level * world.tile_size + cam[1]
        base = sea_screen - 26
        if base < -200:
            return
        left, right = span
        layers = ((0.18, 22, mix(sample.sky_bottom, (86, 104, 122), 0.42)),
                  (0.34, 10, mix(sample.sky_bottom, (58, 74, 92), 0.58)))
        for index, (parallax, height, color) in enumerate(layers):
            points = [(left, base + 40)]
            offset = self._camera[0] * parallax
            steps = max(2, int((right - left) / 96) + 1)
            for step in range(steps + 1):
                x = left + (right - left) * step / steps
                ridge = base - height - math.sin((x + offset) * 0.004 + index * 2.4) * height * 0.9
                ridge -= math.sin((x + offset) * 0.011 + index) * height * 0.45
                points.append((x, ridge))
            points.append((right, base + 40))
            renderer.draw_polygon(points, color, alpha=235)

    def _draw_clouds(self, sample) -> None:
        renderer = self.ctx.renderer
        alpha = int(150 - 70 * (1.0 - sample.light))
        color = mix((255, 255, 255), sample.sky_top, 0.25)
        for cloud in self._clouds:
            cloud[0] += cloud[3] * 0.016
            if cloud[0] > 1120:
                cloud[0] = -240
            x = cloud[0] - self._camera[0] * 0.12
            y = cloud[1]
            scale = cloud[2]
            renderer.draw_round_rect(Rect(x, y, 90 * scale, 22 * scale), color,
                                     int(11 * scale), alpha=alpha)
            renderer.draw_round_rect(Rect(x + 24 * scale, y - 10 * scale, 54 * scale,
                                          20 * scale), color, int(10 * scale), alpha=alpha)
            renderer.draw_round_rect(Rect(x + 58 * scale, y + 4 * scale, 46 * scale,
                                          16 * scale), color, int(8 * scale), alpha=alpha)

    # --- 地形 ---------------------------------------------------------
    def _draw_tiles(self, cam) -> None:
        renderer = self.ctx.renderer
        world = self._world
        ts = world.tile_size
        view_w, view_h = renderer.size
        x0 = max(0, (-cam[0]) // ts)
        y0 = max(0, (-cam[1]) // ts)
        x1 = min(world.width - 1, (-cam[0] + view_w) // ts + 1)
        y1 = min(world.height - 1, (-cam[1] + view_h) // ts + 1)
        sea = world.sea_level
        for ty in range(y0, y1 + 1):
            row = ty * world.width
            for tx in range(x0, x1 + 1):
                tile_id = world.tiles[row + tx]
                if tile_id == 0:
                    continue
                tile = self._defs.tile_by_id(tile_id)
                key = tile.key
                if key in ("sand", "seabed"):
                    wet = abs((ty + 0.5) - sea) <= 2.2 or (ty + 0.5) > sea
                    if wet:
                        key = f"{key}_wet"
                texture = (self._tiles.get(key, tx * 7 + ty * 13)
                           or self._tiles.get(tile.key, tx * 7 + ty * 13))
                if texture is None:
                    continue
                renderer.draw_texture(texture, Rect(tx * ts + cam[0], ty * ts + cam[1],
                                                    ts, ts))

    # --- 海水 ---------------------------------------------------------
    def _water_color(self, sample, depth: float) -> Color:
        deep = mix(sample.water_tint, self.ctx.config.color("void"), 0.72)
        return mix(sample.water_tint, deep, min(1.0, depth / 16.0))

    def _draw_water(self, cam, sample) -> None:
        renderer = self.ctx.renderer
        world = self._world
        ts = world.tile_size
        view_w, view_h = renderer.size
        x0 = max(0, (-cam[0]) // ts)
        y0 = max(0, (-cam[1]) // ts)
        x1 = min(world.width - 1, (-cam[0] + view_w) // ts + 1)
        y1 = min(world.height - 1, (-cam[1] + view_h) // ts + 1)
        sea = world.sea_level
        for ty in range(y0, y1 + 1):
            if (ty + 0.5) < sea:
                continue
            depth = (ty + 0.5) - sea
            factor = min(1.0, depth / 16.0)
            color = self._water_color(sample, depth)
            alpha = int(self._surface_alpha + (self._deep_alpha - self._surface_alpha) * factor)
            start = None
            for tx in range(x0, x1 + 2):
                wet = tx <= x1 and world.is_underwater(tx, ty)
                if wet and start is None:
                    start = tx
                elif not wet and start is not None:
                    renderer.draw_rect(Rect(start * ts + cam[0], ty * ts + cam[1],
                                            (tx - start) * ts, ts), color, alpha=alpha)
                    start = None

    def _draw_surface(self, cam, sample) -> None:
        renderer = self.ctx.renderer
        world = self._world
        ts = world.tile_size
        view_w, _ = renderer.size
        x0 = max(0, (-cam[0]) // ts)
        x1 = min(world.width - 1, (-cam[0] + view_w) // ts + 1)
        sea_row = int(math.floor(world.sea_level))
        highlight = mix(self._surface_color, sample.water_tint, 0.35)
        for tx in range(x0, x1 + 1):
            if not world.is_underwater(tx, sea_row):
                continue
            wave = math.sin(tx * 0.35 + self._elapsed * 1.7) * 2.0
            wave += math.sin(tx * 0.13 - self._elapsed * 0.9) * 1.4
            y = world.sea_level * ts + cam[1] + wave
            renderer.draw_rect(Rect(tx * ts + cam[0], y - 1, ts, 2), highlight, alpha=170)
            if (tx + int(self._elapsed * 1.5)) % 9 == 0:
                renderer.draw_rect(Rect(tx * ts + cam[0] + 3, y - 3, 6, 1), highlight,
                                   alpha=120)

    def _draw_surf(self, cam, sample) -> None:
        """水陆交界处的浪花：只在浅水边缘画一小段白线。"""
        renderer = self.ctx.renderer
        world = self._world
        ts = world.tile_size
        sea_row = int(math.floor(world.sea_level))
        view_w, _ = renderer.size
        x0 = max(1, (-cam[0]) // ts)
        x1 = min(world.width - 2, (-cam[0] + view_w) // ts + 1)
        foam = mix((255, 255, 255), sample.water_tint, 0.25)
        for tx in range(x0, x1 + 1):
            if not world.is_underwater(tx, sea_row):
                continue
            # 附近 2 格内有露出水面的地形 → 岸边
            shore = any(world.surface_y(tx + dx) <= world.sea_level + 0.5
                        for dx in (-2, -1, 1, 2))
            if not shore:
                continue
            wave = math.sin(tx * 0.6 + self._elapsed * 2.4) * 2.2
            y = world.sea_level * ts + cam[1] + wave
            renderer.draw_rect(Rect(tx * ts + cam[0], y - 2, ts, 2), foam, alpha=205)
            renderer.draw_rect(Rect(tx * ts + cam[0] + 2, y - 4, 5, 1), foam, alpha=130)

    def _draw_shafts(self, cam, sample) -> None:
        if sample.light < 0.35:
            return
        renderer = self.ctx.renderer
        world = self._world
        ts = world.tile_size
        sea_y = world.sea_level * ts + cam[1]
        alpha = int(self._shaft_alpha * (0.4 + sample.light * 0.6))
        for index in range(self._shaft_count):
            base_x = (index * 240 + self._elapsed * 9) % 1200 - 160
            tx = int((base_x - cam[0]) // ts)
            if not world.in_bounds(tx, int(world.sea_level) + 3):
                continue
            if not world.is_underwater(tx, int(world.sea_level) + 3):
                continue
            renderer.draw_polygon([(base_x, sea_y), (base_x + 42, sea_y),
                                   (base_x + 96, sea_y + 260), (base_x + 34, sea_y + 260)],
                                  (226, 244, 255), alpha=alpha)

    def _draw_snow(self, cam, sample) -> None:
        if not self._player.in_water:
            return
        renderer = self.ctx.renderer
        color = mix(self._surface_color, sample.water_tint, 0.3)
        for particle in self._snow:
            renderer.draw_rect(Rect(particle[0], particle[1], 2, 2), color, alpha=110)

    # --- 生态对象 / 生物 ---------------------------------------------
    def _draw_props(self, cam) -> None:
        renderer = self.ctx.renderer
        view_left = -cam[0] - 60
        view_right = -cam[0] + 1020
        for prop in self._props.props:
            if prop.harvested or not (view_left <= prop.x <= view_right):
                continue
            obj = self._defs.obj(prop.obj_id)
            draw_prop(renderer, prop, obj, self._elapsed, cam)

    def _draw_creatures(self, cam, sample) -> None:
        renderer = self.ctx.renderer
        world = self._world
        fish_color = mix((210, 226, 236), sample.water_tint, 0.35)
        for school in self._fish:
            tx = int(school.x // world.tile_size)
            ty = int(school.y // world.tile_size)
            if not world.is_underwater(tx, ty):
                continue
            school.draw(renderer, cam, fish_color, alpha=190)
        bird_color = mix(self.ctx.config.color("text_dim"), sample.sky_bottom, 0.4)
        for bird in self._birds:
            bird.draw(renderer, cam, bird_color)
        for crab in self._crabs:
            crab.draw(renderer, cam, (198, 96, 78))

    def _draw_player(self, cam) -> None:
        self._sprite.draw(self.ctx.renderer, offset=(cam[0], cam[1]))

    # --- 光 / 氛围 ----------------------------------------------------
    def _draw_ambient(self, sample) -> None:
        if sample.ambient_alpha <= 0:
            return
        self.ctx.renderer.draw_rect(Rect(0, 0, 960, 540), sample.ambient,
                                    alpha=sample.ambient_alpha)

    def _light_sources(self) -> list[tuple[float, float, float]]:
        lights = [(self._player.x, self._player.y - self._physics.height / 2,
                   self._player_light)]
        lights.append((self._cave_mouth[0], self._cave_mouth[1], self._mouth_light))
        lights.extend(self._props.lights())
        return lights

    def _draw_glow(self) -> None:
        """火把 / 篝火 / 晶簇的暖光：夜里能看见光源在发光。"""
        renderer = self.ctx.renderer
        cam = (-self._camera[0], -self._camera[1])
        for x, y, level in self._props.lights():
            sx = x + cam[0]
            sy = y + cam[1] - 6
            if not (-90 < sx < 1050 and -90 < sy < 630):
                continue
            radius = level * 7.0
            renderer.draw_round_rect(Rect(sx - radius, sy - radius, radius * 2, radius * 2),
                                     (255, 190, 116), int(radius), alpha=14)
            renderer.draw_round_rect(Rect(sx - radius * 0.55, sy - radius * 0.55,
                                          radius * 1.1, radius * 1.1),
                                     (255, 214, 152), int(radius * 0.55), alpha=24)

    def _draw_cave(self, cam) -> None:
        world = self._world
        if not world.cave_region:
            return
        renderer = self.ctx.renderer
        ts = world.tile_size
        view_w, view_h = renderer.size
        x0 = max(0, (-cam[0]) // ts)
        y0 = max(0, (-cam[1]) // ts)
        x1 = min(world.width - 1, (-cam[0] + view_w) // ts + 1)
        y1 = min(world.height - 1, (-cam[1] + view_h) // ts + 1)
        lights = self._light_sources()
        for ty in range(y0, y1 + 1):
            row = ty * world.width
            for tx in range(x0, x1 + 1):
                if (row + tx) not in world.cave_region:
                    continue
                cx = (tx + 0.5) * ts
                cy = (ty + 0.5) * ts
                best = 0.0
                for lx, ly, level in lights:
                    radius = level * 17.0
                    dx = cx - lx
                    dy = cy - ly
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist < radius:
                        value = 1.0 - dist / radius
                        if value > best:
                            best = value
                alpha = int((1.0 - best) * self._cave_alpha)
                if alpha > 6:
                    renderer.draw_rect(Rect(tx * ts + cam[0], ty * ts + cam[1], ts, ts),
                                       (6, 8, 12), alpha=alpha)

    # --- UI -----------------------------------------------------------
    def _draw_ui(self, sample) -> None:
        ui = self._ui
        renderer = self.ctx.renderer
        cfg = self.ctx.config
        ui.draw_hotbar(ui.selected, None)
        zone_key = self._world.zone_at(*self._player.tile_center())
        zone_label = self._texts.get(f"zone_{zone_key}", zone_key)
        tide_rising = self._tide_delta >= 0
        tide_label = self._texts.get("tide_rise" if tide_rising else "tide_fall", "")
        hours = self._cycle.hours
        time_label = f"{int(hours):02d}:{int((hours % 1) * 60):02d}  {sample.label}"
        ui.draw_hud(time_label, zone_label, tide_label, self._player.in_water)
        ui.draw_controls(self._controls_text)
        if self._player.in_water:
            depth = max(0.0, (self._world.sea_level_y - self._player.y) / self._world.tile_size)
            ui.draw_dive_hint(depth * 2.0)

        if self._focus is not None and self._panel is PANEL_NONE:
            obj = self._defs.obj(self._focus.obj_id)
            ui.draw_prompt(f"[E] {obj.prompt or obj.name}")

        if self._panel == PANEL_INVENTORY:
            ui.draw_inventory(self._hover_slot)
        elif self._panel == PANEL_CRAFT:
            can = [all(self._inventory.count(item) >= need for item, need in recipe.ingredients)
                   for recipe in self._defs.recipes]
            ui.draw_crafting(self._defs.recipes, can, self._hover_craft)
        elif self._panel == PANEL_CHEST and self._chest is not None:
            ui.draw_chest(self._chest.storage, self._hover_chest, self._hover_slot)

        ui.draw_floating((-self._camera[0], -self._camera[1]))
        if self._cursor is not None:
            pos = self.ctx.mouse.pos
            if pos is not None:
                texture = self._icons.get(self._cursor.item_id)
                if texture is not None:
                    renderer.draw_texture(texture, Rect(pos[0] - 14, pos[1] - 14, 28, 28))
                count = str(self._cursor.count)
                width, height = renderer.measure_text(count, ui.font_small)
                renderer.draw_text(count, (pos[0] + 4, pos[1] + 6), ui.font_small,
                                   cfg.color("warm_core"))


