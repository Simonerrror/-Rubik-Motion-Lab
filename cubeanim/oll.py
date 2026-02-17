from __future__ import annotations

from dataclasses import dataclass

from cubeanim.state import state_slots_metadata

_VALID_FACE_COLORS = set("URFDLB")
_SIDE_FACES = {"F", "R", "B", "L"}


@dataclass(frozen=True)
class OLLTopViewData:
    u_grid: tuple[tuple[bool, bool, bool], tuple[bool, bool, bool], tuple[bool, bool, bool]]
    top_b: tuple[bool, bool, bool]
    right_r: tuple[bool, bool, bool]
    bottom_f: tuple[bool, bool, bool]
    left_l: tuple[bool, bool, bool]


@dataclass(frozen=True)
class _FaceletState:
    index: int
    position: tuple[int, int, int]
    face: str
    color: str


def _facelets_from_state(state: str) -> list[_FaceletState]:
    if len(state) != 54:
        raise ValueError(f"State must contain exactly 54 facelets, got {len(state)}")
    if not set(state) <= _VALID_FACE_COLORS:
        raise ValueError(
            "State must contain only face colors URFDLB "
            f"(got: {''.join(sorted(set(state)))})"
        )

    slots = state_slots_metadata()
    if len(slots) != 54:
        raise ValueError("Internal state slot metadata is invalid")

    return [
        _FaceletState(index=index, position=slot[0], face=slot[1], color=color)
        for index, (slot, color) in enumerate(zip(slots, state, strict=True))
    ]


def validate_oll_f2l_start_state(state: str) -> None:
    facelets = _facelets_from_state(state)

    for facelet in facelets:
        x, y, z = facelet.position
        if facelet.face == "D" and facelet.color != "D":
            raise ValueError(
                "Invalid OLL start state: D face must be solved, "
                f"but index {facelet.index} at (x={x}, y={y}, z={z}) is {facelet.color}"
            )

        if facelet.face in _SIDE_FACES and z != 1 and facelet.color != facelet.face:
            raise ValueError(
                "Invalid OLL start state: F2L must be solved, "
                f"but {facelet.face} face index {facelet.index} "
                f"at (x={x}, y={y}, z={z}) is {facelet.color}"
            )


def build_oll_top_view_data(state: str) -> OLLTopViewData:
    facelets = _facelets_from_state(state)
    color_by_face_and_pos = {(facelet.face, facelet.position): facelet.color for facelet in facelets}

    def is_yellow(face: str, pos: tuple[int, int, int]) -> bool:
        return color_by_face_and_pos[(face, pos)] == "U"

    x_order = (1, 0, -1)  # B -> F for B-top/F-bottom orientation.
    y_order = (1, 0, -1)  # L -> R for left-to-right orientation.

    u_grid = tuple(
        tuple(is_yellow("U", (x, y, 1)) for y in y_order)
        for x in x_order
    )
    top_b = tuple(is_yellow("B", (1, y, 1)) for y in y_order)
    right_r = tuple(is_yellow("R", (x, -1, 1)) for x in x_order)
    bottom_f = tuple(is_yellow("F", (-1, y, 1)) for y in y_order)
    left_l = tuple(is_yellow("L", (x, 1, 1)) for x in x_order)

    return OLLTopViewData(
        u_grid=u_grid,
        top_b=top_b,
        right_r=right_r,
        bottom_f=bottom_f,
        left_l=left_l,
    )
