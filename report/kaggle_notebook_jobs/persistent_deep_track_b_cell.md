# Persistent Deep Kaggle Track B Cell

Use this for long runs. It writes outputs to `/kaggle/working/out_deep` like the
previous cell, but after each chunk it also tries to publish a private Kaggle
Dataset version so checkpoints survive session restarts.

Before running, add Kaggle notebook secrets:

- `KAGGLE_USERNAME`
- `KAGGLE_KEY`

Then paste this whole code block into Kaggle.

```python
import glob
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
import urllib.request
from pathlib import Path

from kaggle_secrets import UserSecretsClient

# ---- knobs ----
CHUNKS = 8
TIMESTEPS_PER_CHUNK = 500_000
N_ENVS = 4
GATE_GAMES = 40
SLUG = "rl_deck_deep"
DECK = "report/rl_deck_campaign/best_deck.csv"
OPPONENTS = "benchmark"
HOLDOUT = "a2_kyogre"

DATASET_SLUG = "ptcg-track-b-deep-checkpoints"
DATASET_TITLE = "PTCG Track B Deep Checkpoints"

REPO_URL = "https://github.com/TomBombadyl/kaggle_pokemon.git"
ZIP_URL = "https://github.com/TomBombadyl/kaggle_pokemon/archive/refs/heads/main.zip"
REPO = Path("/kaggle/working/kaggle_pokemon")
OUT = Path("/kaggle/working/out_deep")
ARCHIVE = Path("/kaggle/working/track_b_deep_outputs")
PROGRESS = Path("/kaggle/working/deep_track_b_progress.json")
KAGGLE_DIR = Path("/root/.kaggle")

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

def run_with_heartbeat(cmd, *, cwd=None, check=True, every_sec=60):
    print("\n$", " ".join(map(str, cmd)), flush=True)
    p = subprocess.Popen(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    last = time.time()
    start = time.time()
    while True:
        line = p.stdout.readline()
        if line:
            print(line, end="", flush=True)
            last = time.time()
        elif p.poll() is not None:
            break
        elif time.time() - last >= every_sec:
            print(f"[heartbeat] still running after {(time.time() - start) / 60:.1f} min", flush=True)
            last = time.time()
        else:
            time.sleep(1)
    rc = p.wait()
    if check and rc != 0:
        raise RuntimeError(f"command failed ({rc}): {' '.join(map(str, cmd))}")
    return rc

def setup_kaggle_api():
    user = UserSecretsClient()
    username = user.get_secret("KAGGLE_USERNAME")
    key = user.get_secret("KAGGLE_KEY")
    KAGGLE_DIR.mkdir(parents=True, exist_ok=True)
    cred = KAGGLE_DIR / "kaggle.json"
    cred.write_text(json.dumps({"username": username, "key": key}))
    os.chmod(cred, 0o600)
    run([sys.executable, "-m", "pip", "install", "-q", "kaggle"])
    print("Kaggle API configured for durable checkpoint dataset", flush=True)

def ensure_dataset_metadata():
    OUT.mkdir(exist_ok=True)
    metadata = OUT / "dataset-metadata.json"
    if not metadata.exists():
        metadata.write_text(json.dumps({
            "title": DATASET_TITLE,
            "id": f"{os.environ.get('KAGGLE_USERNAME', 'tobin1dr')}/{DATASET_SLUG}",
            "licenses": [{"name": "CC0-1.0"}],
        }, indent=2))

def publish_dataset(tag):
    ensure_dataset_metadata()
    # Create once if needed; then version. Both are allowed to fail harmlessly if already created/no change.
    create = run(["kaggle", "datasets", "create", "-p", str(OUT), "--dir-mode", "zip", "-q"], check=False)
    version = run([
        "kaggle", "datasets", "version",
        "-p", str(OUT),
        "-m", f"{tag}",
        "--dir-mode", "zip",
        "-q",
    ], check=False)
    if create.returncode == 0 or version.returncode == 0:
        print(f"[persisted] Kaggle Dataset version attempted for {tag}", flush=True)
    else:
        print("[WARN] Dataset persistence failed; outputs still exist in /kaggle/working for now", flush=True)

def collect_outputs(tag):
    OUT.mkdir(exist_ok=True)
    patterns = [
        "agent/models/rl_policy.zip",
        f"agent/models/distilled_{SLUG}_v1.npz",
        "agent/models/distilled_v1.npz",
        f"dist/candidates/track_b_learned_{SLUG}.tar.gz",
        "report/rl_train/checkpoint.json",
        "report/track_b_runs/*.json",
        f"report/track_b_gates/*{SLUG}*gate.md",
        "report/rl_train/eval_*.json",
    ]
    for pattern in patterns:
        for src in glob.glob(pattern):
            shutil.copy2(src, OUT / Path(src).name)
            print("saved", src, "->", OUT / Path(src).name, flush=True)
    zip_file = shutil.make_archive(str(ARCHIVE), "zip", str(OUT))
    shutil.copy2(zip_file, OUT / Path(zip_file).name)
    PROGRESS.write_text(json.dumps({
        "tag": tag,
        "updated_at_epoch": time.time(),
        "zip": zip_file,
    }, indent=2))
    shutil.copy2(PROGRESS, OUT / PROGRESS.name)
    print(f"[checkpoint] {tag}: {zip_file}", flush=True)
    return zip_file

started = time.time()

print("=== configure durable Kaggle API ===", flush=True)
setup_kaggle_api()

print("=== ensure repo ===", flush=True)
if not REPO.exists():
    if run(["git", "ls-remote", REPO_URL, "HEAD"], check=False).returncode != 0:
        raise SystemExit("GitHub unreachable. Turn Internet On and rerun.")
    if run(["git", "clone", "--depth", "1", REPO_URL, str(REPO)], check=False).returncode != 0:
        zip_path = Path("/kaggle/working/kaggle_pokemon.zip")
        urllib.request.urlretrieve(ZIP_URL, zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall("/kaggle/working")
        next(Path("/kaggle/working").glob("kaggle_pokemon-*")).rename(REPO)

os.chdir(REPO)
run(["git", "log", "--oneline", "-1"], check=False)

print("=== install deps ===", flush=True)
run([sys.executable, "-m", "pip", "install", "-q", "gymnasium>=0.29", "stable-baselines3>=2.3", "sb3-contrib>=2.3"])

print("=== verify CUDA ===", flush=True)
import torch
print("torch", torch.__version__)
print("cuda", torch.cuda.is_available())
print("device_count", torch.cuda.device_count())
print("gpu0", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu")
if not torch.cuda.is_available():
    raise SystemExit("CUDA false; set Accelerator=GPU and restart.")

print("=== wire CABT engine ===", flush=True)
run([sys.executable, "scripts/kaggle_setup.py"])

for chunk in range(1, CHUNKS + 1):
    tag = f"chunk {chunk}/{CHUNKS}"
    print(f"\n=== {tag}: {TIMESTEPS_PER_CHUNK} timesteps ===", flush=True)
    cmd = [
        sys.executable, "scripts/train_track_b_deck.py",
        "--deck", DECK,
        "--slug", SLUG,
        "--timesteps", str(TIMESTEPS_PER_CHUNK),
        "--n-envs", str(N_ENVS),
        "--opponents", OPPONENTS,
        "--holdout", HOLDOUT,
        "--gate-games", str(GATE_GAMES),
        "--package",
        "--promote",
        "--resume",
    ]
    run_with_heartbeat(cmd, every_sec=60)
    progress_data = {
        "chunks_completed": chunk,
        "chunks_total": CHUNKS,
        "timesteps_per_chunk": TIMESTEPS_PER_CHUNK,
        "total_requested_timesteps": CHUNKS * TIMESTEPS_PER_CHUNK,
        "updated_at_epoch": time.time(),
    }
    PROGRESS.write_text(json.dumps(progress_data, indent=2))
    zip_file = collect_outputs(tag)
    publish_dataset(tag)

print("\nDONE", flush=True)
print("elapsed_minutes", round((time.time() - started) / 60, 1), flush=True)
print("local_zip", zip_file, flush=True)
print("persistent_dataset", DATASET_SLUG, flush=True)
```
