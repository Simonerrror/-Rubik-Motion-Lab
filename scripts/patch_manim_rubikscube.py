from __future__ import annotations

from pathlib import Path
import site
import sys

OLD = "from manim.mobject.geometry import Square"
NEW = "from manim.mobject.geometry.polygram import Square"
TARGET = Path("manim_rubikscube/cubie.py")


def candidate_site_packages() -> list[Path]:
    paths: list[Path] = []
    for p in site.getsitepackages():
        paths.append(Path(p))
    usersite = site.getusersitepackages()
    if usersite:
        paths.append(Path(usersite))
    for p in sys.path:
        if "site-packages" in p:
            paths.append(Path(p))
    # Preserve order and drop duplicates
    seen = set()
    unique: list[Path] = []
    for p in paths:
        if p in seen:
            continue
        seen.add(p)
        unique.append(p)
    return unique


def patch() -> int:
    for sp in candidate_site_packages():
        file_path = sp / TARGET
        if not file_path.exists():
            continue

        content = file_path.read_text(encoding="utf-8")
        if NEW in content:
            print(f"Already patched: {file_path}")
            return 0
        if OLD not in content:
            print(f"Pattern not found in: {file_path}")
            return 1

        file_path.write_text(content.replace(OLD, NEW), encoding="utf-8")
        print(f"Patched: {file_path}")
        return 0

    print("manim_rubikscube/cubie.py not found in site-packages")
    return 1


if __name__ == "__main__":
    raise SystemExit(patch())
