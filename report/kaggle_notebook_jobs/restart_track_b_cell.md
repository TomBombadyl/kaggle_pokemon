# Restart Kaggle Notebook With Repo Track B Training

Use this if the open Kaggle notebook is the downloaded
`reinforcement-learning-and-mcts-sample-code.ipynb`, but the goal is training our
repo Track B submission policy.

Status note: the GitHub repo has been made public for this Kaggle run, so the
plain `git clone` path should work as long as Kaggle notebook Internet is enabled.

## Kaggle UI

Open the notebook settings panel and set:

- Accelerator: `GPU`
- Internet: `On`
- Input: add the Simulation competition data if `scripts/kaggle_setup.py` cannot
  find `pokemon-tcg-ai-battle`

The resource panel should say `GPU T4 x2` or similar.

## Cell 1 - Clone Public Repo

```python
import os, shutil, subprocess, sys, zipfile, urllib.request
from pathlib import Path

REPO_URL = "https://github.com/TomBombadyl/kaggle_pokemon.git"
REPO = Path("/kaggle/working/kaggle_pokemon")

if REPO.exists():
    shutil.rmtree(REPO)

def run(cmd):
    print("$", " ".join(map(str, cmd)))
    p = subprocess.run(cmd, text=True, capture_output=True)
    print(p.stdout)
    print(p.stderr, file=sys.stderr)
    return p

probe = run(["git", "ls-remote", REPO_URL, "HEAD"])
if probe.returncode != 0:
    raise SystemExit(
        "GitHub is not reachable from this Kaggle session. "
        "Turn Internet On in notebook settings, save/restart the session, then rerun this cell."
    )

clone = run(["git", "clone", "--depth", "1", REPO_URL, str(REPO)])
if clone.returncode != 0:
    print("git clone failed; trying GitHub zip fallback")
    zip_path = Path("/kaggle/working/kaggle_pokemon.zip")
    urllib.request.urlretrieve("https://github.com/TomBombadyl/kaggle_pokemon/archive/refs/heads/main.zip", zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall("/kaggle/working")
    extracted = next(Path("/kaggle/working").glob("kaggle_pokemon-*"))
    extracted.rename(REPO)

os.chdir(REPO)
run(["git", "log", "--oneline", "-1"])
```

## Cell 2 - Install Dependencies And Verify CUDA

```python
import subprocess, sys, torch

subprocess.check_call([
    sys.executable, "-m", "pip", "install", "-q",
    "gymnasium>=0.29", "stable-baselines3>=2.3", "sb3-contrib>=2.3"
])

print("torch", torch.__version__)
print("cuda", torch.cuda.is_available())
print("device_count", torch.cuda.device_count())
print("gpu0", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu")
```

Stop here if `cuda` is `False`.

## Cell 3 - Wire CABT Engine

```python
import subprocess, sys
subprocess.check_call([sys.executable, "scripts/kaggle_setup.py"])
```

## Cell 4 - Train, Distill, Gate, Package

```python
import subprocess, sys

cmd = [
    sys.executable, "scripts/train_track_b_deck.py",
    "--deck", "report/rl_deck_campaign/best_deck.csv",
    "--slug", "rl_deck",
    "--timesteps", "100000",
    "--n-envs", "4",
    "--opponents", "benchmark",
    "--holdout", "a2_kyogre",
    "--gate-games", "40",
    "--package",
    "--promote",
]
print(" ".join(cmd))
subprocess.check_call(cmd)
```

## Cell 5 - Collect Outputs

```python
import glob, shutil
from pathlib import Path

out = Path("/kaggle/working/out")
out.mkdir(exist_ok=True)

patterns = [
    "agent/models/rl_policy.zip",
    "agent/models/distilled_rl_deck_v1.npz",
    "agent/models/distilled_v1.npz",
    "dist/candidates/track_b_learned_rl_deck.tar.gz",
    "report/rl_train/checkpoint.json",
    "report/track_b_runs/*.json",
    "report/track_b_gates/*rl_deck*gate.md",
    "report/rl_train/eval_*.json",
]

for pattern in patterns:
    for src in glob.glob(pattern):
        dst = out / Path(src).name
        shutil.copy2(src, dst)
        print("saved", src, "->", dst)

print("Output folder:", out)
```

## Required Proof

- Cell 2 prints `cuda True`.
- Training JSON says `"status": "ok"` and `"device": "cuda"`.
- Gate report passes.
- `/kaggle/working/out/track_b_learned_rl_deck.tar.gz` exists.

## One Cell Version

Paste this into a blank Kaggle notebook cell and run it. It does everything.

```python
import glob
import json
import os
import shutil
import subprocess
import sys
import zipfile
import urllib.request
from pathlib import Path

REPO_URL = "https://github.com/TomBombadyl/kaggle_pokemon.git"
ZIP_URL = "https://github.com/TomBombadyl/kaggle_pokemon/archive/refs/heads/main.zip"
REPO = Path("/kaggle/working/kaggle_pokemon")
OUT = Path("/kaggle/working/out")

def run(cmd, *, cwd=None, check=True):
    print("\n$", " ".join(map(str, cmd)), flush=True)
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if p.stdout:
        print(p.stdout, flush=True)
    if p.stderr:
        print(p.stderr, file=sys.stderr, flush=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(map(str, cmd))}")
    return p

print("=== 1/6: clone repo ===", flush=True)
if REPO.exists():
    shutil.rmtree(REPO)

probe = run(["git", "ls-remote", REPO_URL, "HEAD"], check=False)
if probe.returncode != 0:
    raise SystemExit(
        "GitHub is not reachable from this Kaggle session. "
        "Turn Internet On in notebook settings, restart the session, and rerun this cell."
    )

clone = run(["git", "clone", "--depth", "1", REPO_URL, str(REPO)], check=False)
if clone.returncode != 0:
    print("git clone failed; trying GitHub zip fallback", flush=True)
    zip_path = Path("/kaggle/working/kaggle_pokemon.zip")
    urllib.request.urlretrieve(ZIP_URL, zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall("/kaggle/working")
    extracted = next(Path("/kaggle/working").glob("kaggle_pokemon-*"))
    extracted.rename(REPO)

os.chdir(REPO)
run(["git", "log", "--oneline", "-1"], check=False)

print("=== 2/6: install training dependencies ===", flush=True)
run([
    sys.executable, "-m", "pip", "install", "-q",
    "gymnasium>=0.29", "stable-baselines3>=2.3", "sb3-contrib>=2.3"
])

print("=== 3/6: verify CUDA ===", flush=True)
import torch
print("torch", torch.__version__, flush=True)
print("cuda", torch.cuda.is_available(), flush=True)
print("device_count", torch.cuda.device_count(), flush=True)
print("gpu0", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu", flush=True)
if not torch.cuda.is_available():
    raise SystemExit("CUDA is false. Set Kaggle Accelerator=GPU, restart session, rerun this cell.")

print("=== 4/6: wire CABT engine ===", flush=True)
run([sys.executable, "scripts/kaggle_setup.py"])

print("=== 5/6: train -> distill -> gate -> package ===", flush=True)
train_cmd = [
    sys.executable, "scripts/train_track_b_deck.py",
    "--deck", "report/rl_deck_campaign/best_deck.csv",
    "--slug", "rl_deck",
    "--timesteps", "100000",
    "--n-envs", "4",
    "--opponents", "benchmark",
    "--holdout", "a2_kyogre",
    "--gate-games", "40",
    "--package",
    "--promote",
]
run(train_cmd)

print("=== 6/6: collect outputs ===", flush=True)
OUT.mkdir(exist_ok=True)
patterns = [
    "agent/models/rl_policy.zip",
    "agent/models/distilled_rl_deck_v1.npz",
    "agent/models/distilled_v1.npz",
    "dist/candidates/track_b_learned_rl_deck.tar.gz",
    "report/rl_train/checkpoint.json",
    "report/track_b_runs/*.json",
    "report/track_b_gates/*rl_deck*gate.md",
    "report/rl_train/eval_*.json",
]

saved = []
for pattern in patterns:
    for src in glob.glob(pattern):
        dst = OUT / Path(src).name
        shutil.copy2(src, dst)
        saved.append(str(dst))
        print("saved", src, "->", dst, flush=True)

ckpt = Path("report/rl_train/checkpoint.json")
if ckpt.exists():
    print("\n=== checkpoint ===", flush=True)
    print(json.dumps(json.loads(ckpt.read_text()), indent=2), flush=True)

print("\nDONE. Download this folder from Kaggle outputs:", OUT, flush=True)
print("\n".join(saved), flush=True)
```
