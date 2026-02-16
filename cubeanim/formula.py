from __future__ import annotations

from dataclasses import dataclass


class FormulaSyntaxError(ValueError):
    def __init__(self, message: str, position: int) -> None:
        super().__init__(f"{message} at index {position}")
        self.position = position


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str
    start: int


class FormulaConverter:
    """One-shot baseline parser: face/slice/wide/rotations + repeats."""

    _WIDE_MOVE_BASE = set("frblud")
    _VALID_FACE_MOVES = set("URFDLB")
    _VALID_SLICE_MOVES = set("MES")
    _VALID_ROTATIONS = set("xyz")

    @classmethod
    def convert(cls, formula: str, repeat: int = 1) -> list[str]:
        steps = cls.convert_steps(formula, repeat=repeat)
        return [move for step in steps for move in step]

    @classmethod
    def convert_steps(cls, formula: str, repeat: int = 1) -> list[list[str]]:
        if repeat < 1:
            raise ValueError("repeat must be >= 1")

        tokens = cls._tokenize(formula)
        parser = _FormulaParser(tokens=tokens, formula=formula, converter=cls)
        steps = parser.parse_sequence()

        if parser.has_more():
            token = parser.peek()
            raise FormulaSyntaxError(f"Unexpected token '{token.value}'", token.start)

        repeated: list[list[str]] = []
        for _ in range(repeat):
            repeated.extend([step[:] for step in steps])
        return repeated

    @classmethod
    def invert_move(cls, move: str) -> str:
        base, modifier = cls._split_move_modifier(move)
        if not base:
            raise ValueError("Move must be non-empty")
        if modifier == "":
            return f"{base}'"
        if modifier == "'":
            return base
        if modifier == "2":
            return move
        raise ValueError(f"Unsupported move modifier in '{move}'")

    @classmethod
    def invert_moves(cls, moves: list[str]) -> list[str]:
        return [cls.invert_move(move) for move in reversed(moves)]

    @classmethod
    def invert_steps(cls, steps: list[list[str]]) -> list[list[str]]:
        return [[cls.invert_move(move) for move in step] for step in reversed(steps)]

    @classmethod
    def _tokenize(cls, formula: str) -> list[_Token]:
        tokens: list[_Token] = []
        i = 0
        length = len(formula)

        while i < length:
            char = formula[i]

            if char.isspace():
                i += 1
                continue

            if char in "()^":
                kind = {"(": "LPAREN", ")": "RPAREN", "^": "CARET"}[char]
                tokens.append(_Token(kind=kind, value=char, start=i))
                i += 1
                continue

            if char.isdigit():
                start = i
                while i < length and formula[i].isdigit():
                    i += 1
                tokens.append(_Token(kind="INT", value=formula[start:i], start=start))
                continue

            if char.isalpha():
                start = i
                i += 1
                if i < length and formula[i] in "wW" and formula[start].upper() in cls._VALID_FACE_MOVES:
                    i += 1
                if i < length and formula[i] in "'2":
                    i += 1
                tokens.append(_Token(kind="MOVE", value=formula[start:i], start=start))
                continue

            raise FormulaSyntaxError(f"Unsupported character '{char}'", i)

        return tokens

    @staticmethod
    def _split_move_modifier(move: str) -> tuple[str, str]:
        if move.endswith("2"):
            return move[:-1], "2"
        if move.endswith("'"):
            return move[:-1], "'"
        return move, ""

    @classmethod
    def expand_move(cls, token: _Token) -> list[str]:
        raw_move = token.value
        base, modifier = cls._split_move_modifier(raw_move)

        if len(base) == 1 and base in cls._WIDE_MOVE_BASE:
            return [f"{base}{modifier}"]
        if len(base) == 2 and base[1] in "wW" and base[0].lower() in cls._WIDE_MOVE_BASE:
            return [f"{base[0].lower()}{modifier}"]
        if len(base) == 1 and base in cls._VALID_FACE_MOVES:
            return [f"{base}{modifier}"]
        if len(base) == 1 and base in cls._VALID_SLICE_MOVES:
            return [f"{base}{modifier}"]
        if len(base) == 1 and base.lower() in cls._VALID_ROTATIONS:
            return [f"{base.lower()}{modifier}"]

        raise FormulaSyntaxError(f"Unknown move token '{raw_move}'", token.start)


@dataclass
class _FormulaParser:
    tokens: list[_Token]
    formula: str
    converter: type[FormulaConverter]
    index: int = 0

    def has_more(self) -> bool:
        return self.index < len(self.tokens)

    def peek(self) -> _Token:
        return self.tokens[self.index]

    def consume(self) -> _Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def parse_sequence(self, stop_at_rparen: bool = False) -> list[list[str]]:
        steps: list[list[str]] = []

        while self.has_more():
            token = self.peek()
            if token.kind == "RPAREN":
                if stop_at_rparen:
                    break
                raise FormulaSyntaxError("Unexpected ')'", token.start)

            atom_steps, is_group = self.parse_atom()
            repeat = self.parse_repeat(is_group=is_group)
            for _ in range(repeat):
                steps.extend([step[:] for step in atom_steps])

        if stop_at_rparen:
            if not self.has_more() or self.peek().kind != "RPAREN":
                raise FormulaSyntaxError("Missing closing ')'", len(self.formula))
            self.consume()

        return steps

    def parse_atom(self) -> tuple[list[list[str]], bool]:
        token = self.consume()

        if token.kind == "LPAREN":
            inner_steps = self.parse_sequence(stop_at_rparen=True)
            return inner_steps, True

        if token.kind == "MOVE":
            expanded = self.converter.expand_move(token)
            return [[expanded[0]]], False

        raise FormulaSyntaxError(
            f"Expected move or '(' but got '{token.value}'",
            token.start,
        )

    def parse_repeat(self, is_group: bool) -> int:
        if not self.has_more():
            return 1

        token = self.peek()

        if token.kind == "CARET":
            self.consume()
            if not self.has_more() or self.peek().kind != "INT":
                raise FormulaSyntaxError("Expected integer after '^'", token.start)
            int_token = self.consume()
            repeat = int(int_token.value)
            if repeat < 1:
                raise FormulaSyntaxError("Repeat must be >= 1", int_token.start)
            return repeat

        if is_group and token.kind == "INT":
            int_token = self.consume()
            repeat = int(int_token.value)
            if repeat < 1:
                raise FormulaSyntaxError("Repeat must be >= 1", int_token.start)
            return repeat

        return 1
