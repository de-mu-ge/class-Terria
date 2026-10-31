"""文字排版：中文折行、打字机可见字符。

折行规则：按测量宽度折，不在收尾标点前断行，不拆开连续的西文单词。
"""

from __future__ import annotations

from typing import Callable

Measure = Callable[[str], int]

NO_BREAK_BEFORE = "」』）】》〉、，。！？；：…—"
NO_BREAK_AFTER = "「『（【《〈"


def wrap_text(measure: Measure, text: str, max_width: int) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if ch == "\n":
            lines.append(current)
            current = ""
            i += 1
            continue

        # 西文单词/数字整体作为 token
        if ch.isascii() and (ch.isalnum() or ch in "'-"):
            j = i
            while j < length and text[j].isascii() and (text[j].isalnum() or text[j] in "'-."):
                j += 1
            token = text[i:j]
        else:
            token = ch
            j = i + 1

        candidate = current + token
        if not current or measure(candidate) <= max_width:
            current = candidate
            i = j
            continue

        # 行首禁用标点：允许溢出到本行末尾
        if token and token[0] in NO_BREAK_BEFORE:
            current = candidate
            i = j
            lines.append(current)
            current = ""
            continue

        # 行尾不留在开引号后
        if current and current[-1] in NO_BREAK_AFTER:
            current = candidate
            i = j
            continue

        lines.append(current)
        current = ""
    if current:
        lines.append(current)
    return lines


def visible_count(text: str, typed_chars: float) -> int:
    return max(0, min(len(text), int(typed_chars)))


def slice_visible(text: str, typed_chars: float) -> str:
    return text[: visible_count(text, typed_chars)]
