from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MANUAL_JSON = REPO_ROOT / "apps" / "trainer" / "data" / "manual-content.json"
OUTPUT_MD = REPO_ROOT / "docs" / "TRAINER_MANUAL.md"


def build_manual_markdown(payload: dict) -> str:
    lines: list[str] = [
        "# Trainer Manual",
        "",
        "_Generated from `apps/trainer/data/manual-content.json`._",
        "",
    ]

    for language, heading in (("ru", "RU"), ("en", "EN")):
        lines.extend([f"## {heading}", ""])
        for section in payload.get("sections", []):
            title = str(section.get("title", {}).get(language) or section.get("id") or "Section").strip()
            lead = str(section.get("lead", {}).get(language) or "").strip()
            items = section.get("items", {}).get(language) or []
            lines.append(f"### {title}")
            lines.append("")
            if lead:
                lines.append(lead)
                lines.append("")
            for item in items:
                lines.append(f"- {str(item).strip()}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    payload = json.loads(MANUAL_JSON.read_text(encoding="utf-8"))
    OUTPUT_MD.write_text(build_manual_markdown(payload), encoding="utf-8")
    print(f"Manual written to {OUTPUT_MD}")


if __name__ == "__main__":
    main()
