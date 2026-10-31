"""背包与物品堆。"""

from __future__ import annotations

from dataclasses import dataclass

from .defs import ItemDef


@dataclass
class Stack:
    item_id: str
    count: int

    def copy(self) -> "Stack":
        return Stack(self.item_id, self.count)


class Inventory:
    """定长槽位背包；前 hotbar_slots 个槽位同时是快捷栏。"""

    def __init__(self, defs, slot_count: int = 32, hotbar_slots: int = 8) -> None:
        self._defs = defs
        self.slots: list[Stack | None] = [None] * slot_count
        self.hotbar_slots = hotbar_slots

    # --- 查询 ---------------------------------------------------------
    def __len__(self) -> int:
        return len(self.slots)

    def get(self, index: int) -> Stack | None:
        if 0 <= index < len(self.slots):
            return self.slots[index]
        return None

    def set(self, index: int, stack: Stack | None) -> None:
        if 0 <= index < len(self.slots):
            self.slots[index] = stack

    def item_def(self, item_id: str) -> ItemDef:
        return self._defs.item(item_id)

    def count(self, item_id: str) -> int:
        return sum(slot.count for slot in self.slots if slot and slot.item_id == item_id)

    # --- 增删 ---------------------------------------------------------
    def add(self, item_id: str, count: int) -> int:
        """加入物品，返回装不下的剩余数量。"""
        if count <= 0:
            return 0
        item = self._defs.item(item_id)
        remaining = count
        # 先合并已有堆
        for slot in self.slots:
            if slot and slot.item_id == item_id and slot.count < item.stack:
                space = item.stack - slot.count
                moved = min(space, remaining)
                slot.count += moved
                remaining -= moved
                if remaining <= 0:
                    return 0
        # 再找空槽
        for index, slot in enumerate(self.slots):
            if slot is None:
                moved = min(item.stack, remaining)
                self.slots[index] = Stack(item_id, moved)
                remaining -= moved
                if remaining <= 0:
                    return 0
        return remaining

    def remove(self, item_id: str, count: int) -> bool:
        if self.count(item_id) < count:
            return False
        remaining = count
        for index in range(len(self.slots) - 1, -1, -1):
            slot = self.slots[index]
            if not slot or slot.item_id != item_id:
                continue
            taken = min(slot.count, remaining)
            slot.count -= taken
            remaining -= taken
            if slot.count <= 0:
                self.slots[index] = None
            if remaining <= 0:
                return True
        return remaining <= 0

    def has_all(self, ingredients) -> bool:
        return all(self.count(item_id) >= need for item_id, need in ingredients)

    def first_empty(self) -> int | None:
        for index, slot in enumerate(self.slots):
            if slot is None:
                return index
        return None

    def hotbar(self) -> list[Stack | None]:
        return self.slots[: self.hotbar_slots]
