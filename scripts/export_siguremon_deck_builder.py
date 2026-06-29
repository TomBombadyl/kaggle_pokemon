"""Extract static deck-builder files from siguremon Kaggle notebook."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB_DIR = ROOT / "notebooks" / "siguremon_deck_builder"
NB_PATH = NB_DIR / "deck-builder-tool.ipynb"


def main() -> None:
    nb = json.loads(NB_PATH.read_text(encoding="utf-8"))
    for cell in nb["cells"]:
        src = "".join(cell.get("source", []))
        match = re.match(r"%%writefile\s+(\S+)\s*\n(.*)", src, re.S)
        if not match:
            continue
        out = NB_DIR / match.group(1)
        out.write_text(match.group(2), encoding="utf-8")
        print(f"wrote {out.name}")

    index = NB_DIR / "index.html"
    text = index.read_text(encoding="utf-8")
    fixed = text.replace('href="styles.css"', 'href="style.css"')
    if fixed != text:
        index.write_text(fixed, encoding="utf-8")
        print("fixed styles.css -> style.css in index.html")


if __name__ == "__main__":
    main()
