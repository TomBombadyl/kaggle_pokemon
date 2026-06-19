"""T3: parse the competition card database and emit data/CARDS_SUMMARY.md.

Input  : data/EN_Card_Data.csv  (Strategy competition Data tab; 17 columns)
Output : data/CARDS_SUMMARY.md

Run:  python3 scripts/summarize_cards.py [path/to/EN_Card_Data.csv]
"""
from __future__ import annotations

import os
import sys
from collections import Counter

import pandas as pd

DEFAULT_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "EN_Card_Data.csv")
OUT_MD = os.path.join(os.path.dirname(__file__), "..", "data", "CARDS_SUMMARY.md")


def _find_col(cols, *needles):
    for c in cols:
        lc = c.lower()
        if all(n in lc for n in needles):
            return c
    return None


def summarize(csv_path):
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    cols = list(df.columns)
    n = len(df)
    out = ["# Card Database Summary (T3)", ""]
    out.append(f"Source: `{os.path.basename(csv_path)}` - **{n} cards**, {len(cols)} columns.")
    out.append("")
    out.append("## Columns")
    out.append(", ".join(f"`{c}`" for c in cols))
    out.append("")

    # Card supertype lives in "Stage (Pokemon)/Type (Energy and Trainer)".
    supertype = _find_col(cols, "stage") or _find_col(cols, "type", "energy")
    # Pokemon energy type ({G},{R},...) is the standalone "Type" column.
    ptype = next((c for c in cols if c.strip().lower() == "type"), None)
    # "Category" holds mechanics/subtypes (Ancient, Future, Tera, Trainer's Pokemon).
    cat = _find_col(cols, "category")
    hp = _find_col(cols, "hp")
    retreat = _find_col(cols, "retreat")
    rule = _find_col(cols, "rule")

    def breakdown(title, col, top=None, drop=("n/a", "")):
        if not col:
            return
        counts = Counter(v for v in df[col] if str(v).strip() and v not in drop)
        out.append(f"## {title} (`{col}`)")
        items = counts.most_common(top) if top else sorted(
            counts.items(), key=lambda kv: -kv[1])
        for k, v in items:
            out.append(f"- {k}: {v}")
        out.append("")

    breakdown("Card supertype", supertype)
    breakdown("Pokemon energy type", ptype, top=20)
    breakdown("Special subtype / mechanic", cat)

    if hp:
        nums = pd.to_numeric(df[hp], errors="coerce").dropna()
        if len(nums):
            out.append("## HP distribution (Pokemon)")
            out.append(f"- count {len(nums)}, min {int(nums.min())}, "
                       f"median {int(nums.median())}, max {int(nums.max())}")
            out.append("")
    if retreat:
        nums = pd.to_numeric(df[retreat], errors="coerce").dropna()
        if len(nums):
            out.append("## Retreat cost")
            out.append("- " + ", ".join(f"{int(k)}:{v}" for k, v in
                                        sorted(Counter(nums.astype(int)).items())))
            out.append("")
    if rule:
        ex = sum(1 for v in df[rule] if "ex" in str(v).lower())
        out.append(f"## Rule box\n- cards with a Rule entry (ex / Rule Box etc.): {ex}")
        out.append("")

    out.append("## Sample rows")
    show = [c for c in [_find_col(cols, "card", "id"), _find_col(cols, "card", "name"),
                        supertype, hp, ptype] if c]
    if show:
        out.append("```")
        out.append(df[show].head(10).to_string(index=False))
        out.append("```")
    return "\n".join(out) + "\n"


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV
    if not os.path.exists(csv_path):
        print("[BLOCKED] " + csv_path + " not found. Run scripts/fetch_card_data.py first.")
        return 2
    md = summarize(csv_path)
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(md)
    print("Wrote " + OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
