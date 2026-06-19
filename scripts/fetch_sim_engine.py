"""Fetch the Simulation competition's engine + sample_submission into data/sim/.

The cabt engine, starter agent (main.py / agent.py) and a sample deck ship with
the *Simulation* competition (pokemon-tcg-ai-battle), NOT the Strategy one. This
downloads that competition via kagglehub and copies everything EXCEPT the large
reference PDFs into data/sim/, so we get the engine/code without 275MB of PDFs.

Run on a machine with internet:  python scripts/fetch_sim_engine.py
"""
import glob
import os
import shutil

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMP = "pokemon-tcg-ai-battle"


def main() -> int:
    tok = os.path.join(PROJ, ".kaggle", "access_token")
    if os.path.exists(tok) and not os.environ.get("KAGGLE_API_TOKEN"):
        os.environ["KAGGLE_API_TOKEN"] = open(tok).read().strip()
    if not os.environ.get("KAGGLE_API_TOKEN"):
        print("[ERROR] No Kaggle token (.kaggle/access_token or KAGGLE_API_TOKEN).")
        return 2
    try:
        import kagglehub
    except ImportError:
        print("[ERROR] kagglehub missing: python -m pip install kagglehub")
        return 3

    print(f"Downloading '{COMP}' (all files, ~324MB incl. PDFs)...")
    src = kagglehub.competition_download(COMP)
    print("Cached at:", src)

    dst = os.path.join(PROJ, "data", "sim")
    os.makedirs(dst, exist_ok=True)
    copied = 0
    for path in glob.glob(os.path.join(src, "**", "*"), recursive=True):
        if os.path.isdir(path):
            continue
        if path.lower().endswith(".pdf"):
            continue  # skip the 137MB reference PDFs
        rel = os.path.relpath(path, src)
        out = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.copy(path, out)
        copied += 1
    print(f"Copied {copied} non-PDF files into data/sim/")
    # Show the tree so the next step can locate the engine + starter agent.
    for root, _, files in os.walk(dst):
        for f in sorted(files):
            print("  ", os.path.relpath(os.path.join(root, f), dst))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
