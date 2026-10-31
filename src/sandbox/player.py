"""玩家实体：AABB 物理、跳跃、自动上台阶；采集/放置由场景驱动。"""

from __future__ import annotations

from dataclasses import dataclass

from .defs import Defs
from .inventory import Inventory
from .world import World


@dataclass
class PhysicsConfig:
    gravity: float = 1000.0
    max_fall: float = 900.0
    move_speed: float = 148.0
    move_accel: float = 1500.0
    friction: float = 1900.0
    jump_velocity: float = 342.0
    step_up: float = 9.0
    reach_tiles: float = 5.5
    width: float = 13.0
    height: float = 54.0


class Player:
    def __init__(self, defs: Defs, world: World, inventory: Inventory,
                 physics: PhysicsConfig | None = None) -> None:
        self.defs = defs
        self.world = world
        self.inventory = inventory
        self.physics = physics or PhysicsConfig()
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.facing = 1
        self.walk_time = 0.0
        self.pose = "idle"
        self.invulnerable = 0.0

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
        return (self.x - half, self.y - self.physics.height, self.x + half, self.y)

    def center(self) -> tuple[float, float]:
        return (self.x, self.y - self.physics.height / 2)

    def tile_center(self) -> tuple[int, int]:
        return (int(self.x // self.tile_size), int(self.y // self.tile_size))

    def reach_px(self) -> float:
        return self.physics.reach_tiles * self.tile_size

    def in_reach(self, tx: int, ty: int) -> bool:
        cx = (tx + 0.5) * self.tile_size
        cy = (ty + 0.5) * self.tile_size
        px, py = self.center()
        dx = cx - px
        dy = cy - py
        return dx * dx + dy * dy <= self.reach_px() ** 2

    # --- 物理 ---------------------------------------------------------
    def update(self, dt: float, move_dir: int, jump: bool) -> None:
        phys = self.physics
        target = move_dir * phys.move_speed
        if move_dir != 0:
            self.facing = 1 if move_dir > 0 else -1
            if self.vx < target:
                self.vx = min(target, self.vx + phys.move_accel * dt)
            elif self.vx > target:
                self.vx = max(target, self.vx - phys.move_accel * dt)
        else:
            if self.vx > 0:
                self.vx = max(0.0, self.vx - phys.friction * dt)
            else:
                self.vx = min(0.0, self.vx + phys.friction * dt)

        if jump and self.on_ground:
            self.vy = -phys.jump_velocity
            self.on_ground = False

        self.vy = min(phys.max_fall, self.vy + phys.gravity * dt)

        self._move_x(self.vx * dt)
        was_ground = self.on_ground
        self._move_y(self.vy * dt)

        # 动画状态
        if not self.on_ground:
            self.pose = "idle" if abs(self.vy) < 1 else "idle"
        elif abs(self.vx) > 8:
            self.walk_time += dt
            self.pose = "walk_1" if int(self.walk_time * 8) % 2 == 0 else "walk_2"
        else:
            self.walk_time = 0.0
            self.pose = "idle"
        if self.on_ground and not was_ground and self.vy == 0.0:
            self.vy = 0.0

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
            # 尝试自动上台阶（1 格内的坎直接走上去）
            if self.on_ground:
                lifted = (self.x, self.y - self.physics.step_up)
                if not self._collides((self.box()[0], lifted[1] - self.physics.height,
                                       self.box()[2], lifted[1])):
                    self.y = lifted[1]
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
            if step > 0:  # 下落
                self.y = int((box[3]) // self.tile_size) * self.tile_size - 0.01
                self.on_ground = True
            else:  # 上升撞头
                self.y = (int(box[1] // self.tile_size) + 1) * self.tile_size + \
                    self.physics.height + 0.01
            self.vy = 0.0
            return
