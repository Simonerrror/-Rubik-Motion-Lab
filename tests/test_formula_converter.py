from __future__ import annotations

import pytest

from cubeanim.formula import FormulaConverter, FormulaSyntaxError


def test_wide_short_and_long_moves_are_normalized() -> None:
    assert FormulaConverter.convert("r") == ["r"]
    assert FormulaConverter.convert("Rw") == ["r"]
    assert FormulaConverter.convert("f2") == ["f2"]
    assert FormulaConverter.convert("Uw'") == ["u'"]


def test_formula_repeat_argument_applies_after_parse() -> None:
    moves = FormulaConverter.convert("R U", repeat=3)
    assert moves == ["R", "U", "R", "U", "R", "U"]


def test_inverse_moves_are_built_in_reverse_order() -> None:
    moves = FormulaConverter.convert("R U2 F'")
    inverse = FormulaConverter.invert_moves(moves)
    assert inverse == ["F", "U2", "R'"]


def test_inverse_of_repeated_formula_keeps_repeat_count() -> None:
    moves = FormulaConverter.convert("(R U)2")
    inverse = FormulaConverter.invert_moves(moves)
    assert inverse == ["U'", "R'", "U'", "R'"]


def test_group_repeat_and_power_repeat() -> None:
    assert FormulaConverter.convert("(R U)3") == ["R", "U", "R", "U", "R", "U"]
    assert FormulaConverter.convert("R^3") == ["R", "R", "R"]


def test_fail_fast_on_unknown_token() -> None:
    with pytest.raises(FormulaSyntaxError):
        FormulaConverter.convert("R Q")


def test_fail_fast_on_unbalanced_parentheses() -> None:
    with pytest.raises(FormulaSyntaxError):
        FormulaConverter.convert("(R U")


def test_fail_fast_on_invalid_repeat() -> None:
    with pytest.raises(FormulaSyntaxError):
        FormulaConverter.convert("R^0")

    with pytest.raises(ValueError):
        FormulaConverter.convert("R U", repeat=0)
