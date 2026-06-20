# Deep Kaggle Track B Training Cell

Paste this into Kaggle when you want to step away for a longer run.

Best use: run it in the **same Kaggle session** that already produced the 100k
`rl_policy.zip`. It will resume if that checkpoint is present; otherwise it will
clone and start fresh.

Default: 12M timesteps in 12 chunks of 1M, `n-envs=4`, benchmark opponents,
Kyogre held out, checkpoint zip after each chunk, then one final distill/gate/
package. The cell prints a heartbeat while the subprocess is running so Kaggle
does not look idle.

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

# ---- knobs ----
CHUNKS = 12                    # 12 * 1M = 12M total timesteps.
TIMESTEPS_PER_CHUNK = 1_000_000
N_ENVS = 4                     # Safe for Kaggle T4 x2 CPU allocation.
GATE_GAMES = 40
SLUG = "rl_deck_deep"
DECK = "report/rl_deck_campaign/best_deck.csv"
OPPONENTS = "benchmark"
HOLDOUT = "a2_kyogre"

REPO_URL = "https://github.com/TomBombadyl/kaggle_pokemon.git"
ZIP_URL = "https://github.com/TomBombadyl/kaggle_pokemon/archive/refs/heads/main.zip"
REPO = Path("/kaggle/working/kaggle_pokemon")
OUT = Path("/kaggle/working/out_deep")
ARCHIVE = Path("/kaggle/working/track_b_deep_outputs")
PROGRESS = Path("/kaggle/working/deep_track_b_progress.json")

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
            mins = (time.time() - start) / 60
            print(f"[heartbeat] still running after {mins:.1f} min", flush=True)
            last = time.time()
        else:
            time.sleep(1)
    rc = p.wait()
    if check and rc != 0:
        raise RuntimeError(f"command failed ({rc}): {' '.join(map(str, cmd))}")
    return rc

def collect_and_zip(tag):
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
    saved = []
    for pattern in patterns:
        for src in glob.glob(pattern):
            dst = OUT / Path(src).name
            shutil.copy2(src, dst)
            saved.append(str(dst))
            print("saved", src, "->", dst, flush=True)
    zip_file = shutil.make_archive(str(ARCHIVE), "zip", str(OUT))
    print(f"[checkpoint] {tag}: zipped outputs -> {zip_file}", flush=True)
    return saved, zip_file

def print_existing_state(label):
    print(f"\n=== existing state: {label} ===", flush=True)
    checks = [
        Path("agent/models/rl_policy.zip"),
        Path("report/rl_train/checkpoint.json"),
        Path("agent/models/distilled_v1.npz"),
        Path(f"agent/models/distilled_{SLUG}_v1.npz"),
        Path(f"dist/candidates/track_b_learned_{SLUG}.tar.gz"),
        Path(f"report/track_b_gates/track_b_learned_{SLUG}_gate.md"),
        OUT,
        ARCHIVE.with_suffix(".zip"),
        PROGRESS,
    ]
    for p in checks:
        if p.exists():
            if p.is_file():
                print(f"exists file {p} size={p.stat().st_size}", flush=True)
            else:
                print(f"exists dir  {p}", flush=True)
        else:
            print(f"missing     {p}", flush=True)

    ckpt = Path("report/rl_train/checkpoint.json")
    if ckpt.exists():
        try:
            data = json.loads(ckpt.read_text())
            summary = {
                "status": data.get("status"),
                "timesteps": data.get("timesteps"),
                "device": data.get("device"),
                "deck_slug": data.get("deck_slug"),
                "opponents": data.get("opponents"),
                "holdout": data.get("holdout"),
            }
            print("checkpoint_summary", json.dumps(summary, indent=2), flush=True)
        except Exception as exc:
            print("checkpoint_read_error", repr(exc), flush=True)

    if PROGRESS.exists():
        try:
            print("deep_progress", PROGRESS.read_text(), flush=True)
        except Exception as exc:
            print("progress_read_error", repr(exc), flush=True)

started = time.time()

print("=== 1/7: ensure repo ===", flush=True)
if not REPO.exists():
    probe = run(["git", "ls-remote", REPO_URL, "HEAD"], check=False)
    if probe.returncode != 0:
        raise SystemExit("GitHub unreachable. Turn Kaggle Internet On, restart session, rerun this cell.")
    clone = run(["git", "clone", "--depth", "1", REPO_URL, str(REPO)], check=False)
    if clone.returncode != 0:
        print("git clone failed; trying zip fallback", flush=True)
        zip_path = Path("/kaggle/working/kaggle_pokemon.zip")
        urllib.request.urlretrieve(ZIP_URL, zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall("/kaggle/working")
        extracted = next(Path("/kaggle/working").glob("kaggle_pokemon-*"))
        extracted.rename(REPO)

os.chdir(REPO)
run(["git", "log", "--oneline", "-1"], check=False)
print_existing_state("before setup")

print("=== 2/7: install deps ===", flush=True)
run([
    sys.executable, "-m", "pip", "install", "-q",
    "gymnasium>=0.29", "stable-baselines3>=2.3", "sb3-contrib>=2.3"
])

print("=== 3/7: verify CUDA ===", flush=True)
import torch
print("torch", torch.__version__, flush=True)
print("cuda", torch.cuda.is_available(), flush=True)
print("device_count", torch.cuda.device_count(), flush=True)
print("gpu0", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu", flush=True)
if not torch.cuda.is_available():
    raise SystemExit("CUDA is false. Set Kaggle Accelerator=GPU, restart session, rerun this cell.")

print("=== 4/7: wire CABT engine ===", flush=True)
run([sys.executable, "scripts/kaggle_setup.py"])

print("=== 5/7: big chunked train; final distill/gate/package ===", flush=True)
resume = Path("agent/models/rl_policy.zip").exists() and Path("report/rl_train/checkpoint.json").exists()
print("resume", resume, flush=True)
print_existing_state("before training")

all_saved = []
for chunk in range(1, CHUNKS + 1):
    chunk_slug = SLUG
    print(f"\n=== chunk {chunk}/{CHUNKS}: {TIMESTEPS_PER_CHUNK} timesteps ===", flush=True)
    cmd = [
        sys.executable, "scripts/train_track_b_deck.py",
        "--deck", DECK,
        "--slug", chunk_slug,
        "--timesteps", str(TIMESTEPS_PER_CHUNK),
        "--n-envs", str(N_ENVS),
        "--opponents", OPPONENTS,
        "--holdout", HOLDOUT,
        "--skip-distill",
        "--skip-gate",
        "--resume",
    ]
    run_with_heartbeat(cmd, every_sec=60)
    saved, zip_file = collect_and_zip(f"chunk {chunk}/{CHUNKS}")
    all_saved.extend(saved)
    progress_data = {
        "chunks_completed": chunk,
        "chunks_total": CHUNKS,
        "timesteps_per_chunk": TIMESTEPS_PER_CHUNK,
        "total_requested_timesteps": CHUNKS * TIMESTEPS_PER_CHUNK,
        "last_zip": zip_file,
        "updated_at_epoch": time.time(),
    }
    PROGRESS.write_text(json.dumps(progress_data, indent=2))
    shutil.copy2(PROGRESS, OUT / PROGRESS.name)
    shutil.make_archive(str(ARCHIVE), "zip", str(OUT))
    print_existing_state(f"after chunk {chunk}/{CHUNKS}")

print("=== 6/7: final distill -> gate -> package ===", flush=True)
final_cmd = [
    sys.executable, "scripts/train_track_b_deck.py",
    "--deck", DECK,
    "--slug", SLUG,
    "--timesteps", "0",
    "--n-envs", str(N_ENVS),
    "--opponents", OPPONENTS,
    "--holdout", HOLDOUT,
    "--gate-games", str(GATE_GAMES),
    "--skip-train",
    "--package",
    "--promote",
]
run_with_heartbeat(final_cmd, every_sec=60)
saved, zip_file = collect_and_zip("final package")
all_saved.extend(saved)

print("=== 7/7: final outputs collected ===", flush=True)
elapsed_min = (time.time() - started) / 60
print("\nDONE", flush=True)
print("elapsed_minutes", round(elapsed_min, 1), flush=True)
print("download", zip_file, flush=True)
print("\n".join(sorted(set(all_saved))), flush=True)

ckpt = Path("report/rl_train/checkpoint.json")
if ckpt.exists():
    print("\n=== checkpoint ===", flush=True)
    print(json.dumps(json.loads(ckpt.read_text()), indent=2), flush=True)
```

Expected download:

```text
/kaggle/working/track_b_deep_outputs.zip
```
