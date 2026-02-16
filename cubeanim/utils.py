from __future__ import annotations

import re


def slugify_formula(formula: str, max_len: int = 80) -> str:
    text = formula.strip().lower()
    text = text.replace("'", "p")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-_")

    if not text:
        return "formula"
    if len(text) > max_len:
        return text[:max_len].rstrip("-_")
    return text


def normalize_formula_text(formula: str) -> str:
    return " ".join(formula.split())


def _consume_parenthesized_chunk(text: str, start: int) -> tuple[str, int]:
    depth = 0
    i = start
    length = len(text)

    while i < length:
        char = text[i]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                i += 1
                break
        i += 1

    # Keep group repeat suffix with the same chunk: (...)2 or (...)^3
    if i < length and text[i] == "^":
        j = i + 1
        while j < length and text[j].isdigit():
            j += 1
        if j > i + 1:
            i = j
    else:
        j = i
        while j < length and text[j].isdigit():
            j += 1
        if j > i:
            i = j

    return normalize_formula_text(text[start:i]), i


def formula_display_chunks(formula: str) -> list[str]:
    text = normalize_formula_text(formula)
    chunks: list[str] = []
    i = 0
    length = len(text)

    while i < length:
        if text[i].isspace():
            i += 1
            continue

        if text[i] == "(":
            chunk, i = _consume_parenthesized_chunk(text, i)
            if chunk:
                chunks.append(chunk)
            continue

        start = i
        while i < length and (not text[i].isspace()) and text[i] != "(":
            i += 1
        token = text[start:i].strip()
        if token:
            chunks.append(token)

    return chunks


def wrap_formula_for_overlay(
    formula: str,
    max_chars_per_line: int = 54,
    max_lines: int = 2,
) -> str:
    if max_lines < 1:
        raise ValueError("max_lines must be >= 1")
    if max_chars_per_line < 1:
        raise ValueError("max_chars_per_line must be >= 1")

    chunks = formula_display_chunks(formula)
    if not chunks:
        return ""

    lines: list[str] = []
    current = ""

    for chunk in chunks:
        candidate = chunk if not current else f"{current} {chunk}"
        if len(candidate) <= max_chars_per_line or not current:
            current = candidate
            continue

        lines.append(current)
        current = chunk

    if current:
        lines.append(current)

    if len(lines) <= max_lines:
        return "\n".join(lines)

    head = lines[: max_lines - 1]
    tail = " ".join(lines[max_lines - 1 :])
    return "\n".join([*head, tail])
