"""Fetch the competition card data into ./data using the stored Kaggle token.

Reads the new-format token from .kaggle/access_token (or KAGGLE_API_TOKEN env),
downloads the Strategy-competition dataset via kagglehub, and copies just the
CSV card data into data/ (leaves the 137MB PDFs in kagglehub's cache to keep the
project lean). Idempotent: re-running overwrites the CSVs in place.

Run on a machine with internet:  python scripts/fetch_card_data.py
"""
import glob
import os
import shutil
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMP = "pokemon-tcg-ai-battle-challenge-strategy"


def main() -> int:
    tok_file = os.path.join(PROJ, ".kaggle", "access_token")
    if os.path.exists(tok_file) and not os.environ.get("KAGGLE_API_TOKEN"):
        os.environ["KAGGLE_API_TOKEN"] = open(tok_file).read().strip()
    if not os.environ.get("KAGGLE_API_TOKEN"):
        print("[ERROR] No Kaggle token. Put it in .kaggle/access_token or "
              "set KAGGLE_API_TOKEN.")
        return 2
    try:
        import kagglehub
    except ImportError:
        print("[ERROR] kagglehub missing. Run: python -m pip install kagglehub")
        return 3

    print(f"Downloading '{COMP}' (signed in via token)...")
    path = kagglehub.competition_download(COMP)
    print("Cached at:", path)

    data_dir = os.path.join(PROJ, "data")
    os.makedirs(data_dir, exist_ok=True)
    copied = []
    for csv in glob.glob(os.path.join(path, "**", "*.csv"), recursive=True):
        dest = os.path.join(data_dir, os.path.basename(csv))
        shutil.copy(csv, dest)
        copied.append(os.path.basename(csv))
    if not copied:
        print("[WARN] No CSVs found in the download:", os.listdir(path))
        return 4
    print("Copied into data/:", ", ".join(sorted(copied)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
