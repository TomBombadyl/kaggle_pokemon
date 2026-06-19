#!/usr/bin/env bash
# Bootstrap the nightly run environment. Safe to re-run.
# Translate Z:\kaggle\pokemon to the bash mount before running.
set -euo pipefail

PROJECT_DIR="${1:-$(pwd)}"
cd "$PROJECT_DIR"

echo "==> Installing Python deps"
pip install --break-system-packages -r requirements.txt

echo "==> Configuring Kaggle auth (new KGAT_ token format)"
# Preferred: project-local .kaggle/access_token (gitignored). Also honor env.
if [[ -f ".kaggle/access_token" ]]; then
  mkdir -p "$HOME/.kaggle"
  cp ".kaggle/access_token" "$HOME/.kaggle/access_token"
  chmod 600 "$HOME/.kaggle/access_token"
  export KAGGLE_API_TOKEN="$(cat .kaggle/access_token)"
  echo "    access_token found; KAGGLE_API_TOKEN exported."
elif [[ -n "${KAGGLE_API_TOKEN:-}" ]]; then
  echo "    Using KAGGLE_API_TOKEN from environment."
elif [[ -f ".kaggle/kaggle.json" ]]; then
  mkdir -p "$HOME/.kaggle"; cp ".kaggle/kaggle.json" "$HOME/.kaggle/kaggle.json"
  chmod 600 "$HOME/.kaggle/kaggle.json"
  echo "    Legacy kaggle.json found and installed."
else
  echo "    [BLOCKED] No Kaggle credentials — skipping download/submit steps."
  exit 0
fi

echo "==> Downloading competition files into data/"
mkdir -p data
# NOTE: the sandbox proxy currently BLOCKS api.kaggle.com / www.kaggle.com (403).
# kagglehub uses the bearer token and api.kaggle.com; both tools fail behind the
# proxy. If egress to kaggle.com is allowed in this environment, this will work:
if python3 - <<'PY'
import os, sys
os.environ.setdefault("KAGGLE_API_TOKEN", open(".kaggle/access_token").read().strip() if os.path.exists(".kaggle/access_token") else os.environ.get("KAGGLE_API_TOKEN",""))
try:
    import kagglehub
    p = kagglehub.competition_download("pokemon-tcg-ai-battle-challenge-strategy")
    print("Downloaded to:", p)
    # Mirror into ./data for the rest of the pipeline.
    import shutil
    shutil.copytree(p, "data/cabt", dirs_exist_ok=True)
    sys.exit(0)
except Exception as e:
    print("    [BLOCKED] download failed:", type(e).__name__, str(e)[:200])
    sys.exit(3)
PY
then
  echo "==> Download OK"
else
  echo "    Log this blocker in PROGRESS.md and continue with offline tasks."
fi

echo "==> Setup complete"
