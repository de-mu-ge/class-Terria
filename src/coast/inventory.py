"""极简背包：定长槽位 + 计数。"""

from __future__ import annotations

from dataclasses import dataclass

from .defs import CoastDefs


@dataclass
class Stack:
    item_id: str
    count: int


class CoastInventory:
    def __init__(self, defs: CoastDefs, slots: int = 24) -> None:
        self._defs = defs
        self.slots: list[Stack | None] = [None] * slots

    def __len__(self) -> int:
        return len(self.slots)

    def get(self, index: int) -> Stack | None:
        if 0 <= index < len(self.slots):
            return self.slots[index]
        return None

    def set(self, index: int, stack: Stack | None) -> None:
        if 0 <= index < len(self.slots):
            self.slots[index] = stack

    def count(self, item_id: str) -> int:
        return sum(slot.count for slot in self.slots if slot and slot.item_id == item_id)

    def add(self, item_id: str, count: int = 1) -> int:
        if count <= 0:
            return 0
        item = self._defs.item(item_id)
        remaining = count
        for slot in self.slots:
            if slot and slot.item_id == item_id and slot.count < item.stack:
                moved = min(item.stack - slot.count, remaining)
                slot.count += moved
                remaining -= moved
                if remaining == 0:
                    return 0
        for index, slot in enumerate(self.slots):
            if slot is None:
                moved = min(item.stack, remaining)
                self.slots[index] = Stack(item_id, moved)
                remaining -= moved
                if remaining == 0:
                    return 0
        return remaining

    def remove(self, item_id: str, count: int = 1) -> bool:
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
            if remaining == 0:
                return True
        return remaining == 0

    def first_slot_of(self, item_id: str) -> int | None:
        for index, slot in enumerate(self.slots):
            if slot and slot.item_id == item_id:
                return index
        return None
