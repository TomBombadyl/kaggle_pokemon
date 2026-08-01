"""INTEL: decode a notebook's embedded PAYLOAD_B64 dict into a runnable agent dir.

Several high-LB public notebooks (e.g. the mu-1208 Azumarill loader) ship their whole
submission as a base64 dict literal instead of writefile cells, so
extract_notebook_agents.py classifies them "analysis_only". This pulls the payload out.

  python scripts/intel_extract_b64_payload.py --src extracted_agents/pub_1208_loader/_notebook_code.py \
      --out extracted_agents/pub_1208_azumarill
"""

from __future__ import annotations

import argparse
import ast
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def find_payload(src: Path, var: str) -> dict[str, str]:
    tree = ast.parse(src.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if var in names and isinstance(node.value, (ast.Dict,)):
            return ast.literal_eval(node.value)
    raise SystemExit(f"no dict assignment named {var} in {src}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--var", default="PAYLOAD_B64")
    args = ap.parse_args(argv)

    src = Path(args.src)
    if not src.is_absolute():
        src = ROOT / src
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    payload = find_payload(src, args.var)
    for name, b64 in payload.items():
        data = base64.b64decode(b64)
        dest = out / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        print(f"[wrote] {dest.relative_to(ROOT)}  {len(data)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
