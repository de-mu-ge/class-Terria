"""玩家：陆地行走 / 下蹲 / 跳跃，水下游泳 / 上浮 / 下潜 / 浮力 / 阻力。

陆地与水下是两套手感：水下有拖拽感和浮力，出水会自然跃起再落回。
"""

from __future__ import annotations

from dataclasses import dataclass

from .world import CoastWorld


@dataclass
class CoastPhysics:
    # 陆地
    gravity: float = 1200.0
    max_fall: float = 820.0
    walk_speed: float = 148.0
    walk_accel: float = 1500.0
    friction: float = 1700.0
    jump_velocity: float = 400.0
    crouch_speed: float = 62.0
    step_up: float = 16.0
    # 水下
    water_speed: float = 112.0
    water_accel: float = 760.0
    water_gravity: float = 88.0
    water_buoyancy: float = 210.0
    swim_up: float = 430.0
    swim_down: float = 330.0
    water_drag: float = 2.6
    max_swim_up: float = 190.0
    max_swim_down: float = 170.0
    # 体型
    width: float = 13.0
    height: float = 44.0
    reach: float = 3.2


class CoastPlayer:
    def __init__(self, world: CoastWorld, physics: CoastPhysics | None = None) -> None:
        self.world = world
        self.physics = physics or CoastPhysics()
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.in_water = False
        self.facing = 1
        self.crouching = False
        self.walk_time = 0.0
        self.swim_time = 0.0
        self.pose = "idle"

    # --- 位置 ---------------------------------------------------------
    @property
    def tile_size(self) -> int:
        return self.world.tile_size

    def spawn(self, tx: int, ty: int) -> None:
        self.x = (tx + 0.5) * self.tile_size
        self.y = ty * self.tile_size
        self.vx = self.vy = 0.0
        self.on_ground = False

    def box(self) -> tuple[float, float, float, float]:
        half = self.physics.width / 2
        height = self.physics.height * (0.72 if self.crouching else 1.0)
        return (self.x - half, self.y - height, self.x + half, self.y)

    def center(self) -> tuple[float, float]:
        left, top, right, bottom = self.box()
        return ((left + right) / 2, (top + bottom) / 2)

    def tile_center(self) -> tuple[int, int]:
        cx, cy = self.center()
        return int(cx // self.tile_size), int(cy // self.tile_size)

    def in_reach(self, wx: float, wy: float, extra: float = 0.0) -> bool:
        cx, cy = self.center()
        limit = self.physics.reach * self.tile_size + extra
        return (wx - cx) ** 2 + (wy - cy) ** 2 <= limit * limit

    # --- 物理 ---------------------------------------------------------
    def update(self, dt: float, move_dir: int, jump_held: bool, down_held: bool) -> None:
        world = self.world
        water_y = world.sea_level_y

        # 入水判定带迟滞，避免在水面反复切换
        if not self.in_water and self.y > water_y + 9:
            self.in_water = True
        elif self.in_water and self.y < water_y + 2:
            self.in_water = False

        if self.in_water:
            self._update_water(dt, move_dir, jump_held, down_held, water_y)
        else:
            self._update_land(dt, move_dir, jump_held, down_held)

        self._move_x(self.vx * dt)
        self._move_y(self.vy * dt)
        self._update_pose(dt, move_dir)

    def _update_land(self, dt: float, move_dir: int, jump_held: bool, down_held: bool) -> None:
        physics = self.physics
        self.crouching = down_held and self.on_ground
        speed = physics.crouch_speed if self.crouching else physics.walk_speed
        target = move_dir * speed
        if move_dir != 0:
            self.facing = 1 if move_dir > 0 else -1
            if self.vx < target:
                self.vx = min(target, self.vx + physics.walk_accel * dt)
            else:
                self.vx = max(target, self.vx - physics.walk_accel * dt)
        else:
            if self.vx > 0:
                self.vx = max(0.0, self.vx - physics.friction * dt)
            else:
                self.vx = min(0.0, self.vx + physics.friction * dt)

        if jump_held and self.on_ground and not self.crouching:
            self.vy = -physics.jump_velocity
            self.on_ground = False

        self.vy = min(physics.max_fall, self.vy + physics.gravity * dt)

    def _update_water(self, dt: float, move_dir: int, jump_held: bool, down_held: bool,
                      water_y: float) -> None:
        physics = self.physics
        self.crouching = False
        _ = physics
        target = move_dir * physics.water_speed
        if move_dir != 0:
            self.facing = 1 if move_dir > 0 else -1
            if self.vx < target:
                self.vx = min(target, self.vx + physics.water_accel * dt)
            else:
                self.vx = max(target, self.vx - physics.water_accel * dt)
        else:
            self.vx -= self.vx * min(1.0, physics.water_drag * dt)

        if jump_held:
            self.vy -= physics.swim_up * dt
        elif down_held:
            self.vy += physics.swim_down * dt
        else:
            head = self.y - physics.height
            submersion = max(0.0, min(1.0, (water_y - head) / max(1.0, physics.height)))
            self.vy -= physics.water_buoyancy * submersion * dt
            self.vy += physics.water_gravity * dt

        self.vy = max(-physics.max_swim_up, min(physics.max_swim_down, self.vy))
        self.swim_time += dt

    def _update_pose(self, dt: float, move_dir: int) -> None:
        if self.in_water:
            self.pose = "swim"
            return
        if self.crouching:
            self.pose = "crouch"
        elif not self.on_ground:
            self.pose = "jump"
        elif abs(self.vx) > 10:
            self.walk_time += dt
            self.pose = "walk_1" if int(self.walk_time * 9) % 2 == 0 else "walk_2"
        else:
            self.walk_time = 0.0
            self.pose = "idle"

    # --- 碰撞 ---------------------------------------------------------
    def _collides(self, box: tuple[float, float, float, float]) -> bool:
        left, top, right, bottom = box
        ts = self.tile_size
        x0 = int(left // ts)
        x1 = int((right - 0.01) // ts)
        y0 = int(top // ts)
        y1 = int((bottom - 0.01) // ts)
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                if self.world.is_solid(tx, ty):
                    return True
        return False

    def _move_x(self, dx: float) -> None:
        if dx == 0:
            return
        steps = max(1, int(abs(dx) / 6) + 1)
        step = dx / steps
        for _ in range(steps):
            self.x += step
            if not self._collides(self.box()):
                continue
            if self.on_ground and not self.crouching:
                lifted_y = self.y - self.physics.step_up
                left, top, right, bottom = self.box()
                if not self._collides((left, top - self.physics.step_up, right,
                                       lifted_y)):
                    self.y = lifted_y
                    continue
            if step > 0:
                self.x = int(self.box()[2] // self.tile_size) * self.tile_size - \
                    self.physics.width / 2 - 0.01
            else:
                self.x = (int(self.box()[0] // self.tile_size) + 1) * self.tile_size + \
                    self.physics.width / 2 + 0.01
            self.vx = 0.0
            return

    def _move_y(self, dy: float) -> None:
        if dy == 0:
            self.on_ground = self._collides((self.box()[0], self.box()[1],
                                             self.box()[2], self.box()[3] + 1))
            return
        steps = max(1, int(abs(dy) / 6) + 1)
        step = dy / steps
        self.on_ground = False
        for _ in range(steps):
            self.y += step
            if not self._collides(self.box()):
                continue
            box = self.box()
            if step > 0:
                self.y = int(box[3] // self.tile_size) * self.tile_size - 0.01
                self.on_ground = True
            else:
                self.y = (int(box[1] // self.tile_size) + 1) * self.tile_size + \
                    self.physics.height + 0.01
            self.vy = 0.0
            return
