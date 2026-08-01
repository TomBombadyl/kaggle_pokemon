import os, subprocess, sys, time
from pathlib import Path
from datetime import datetime, timezone
ROOT = Path(r"E:\PTCG_AI_Battle_Challenge\kaggle_pokemon")
PY = Path(r"E:\PTCG_AI_Battle_Challenge\.venv\Scripts\python.exe")
LOG = ROOT / "report" / "aggressive" / "mainline_supervisor.log"
LOG.parent.mkdir(parents=True, exist_ok=True)
os.chdir(ROOT)
env = os.environ.copy()
env["PYTHONUNBUFFERED"] = "1"
env["PYTHONUTF8"] = "1"
env["PYTHONIOENCODING"] = "utf-8"
# Prefer CUDA
try:
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
except Exception:
    device = "cpu"

CMDS = {
    "aggressive_loop": [str(PY), "-u", "scripts/aggressive_loop.py", "--poll-seconds", "90"],
    "continuous_focus": [str(PY), "-u", "scripts/continuous_focus_gates.py"],
    "train_mcts": [str(PY), "-u", "scripts/train_lucario_field_mcts.py", "--device", device, "--auto-resume"],
    "status": [str(PY), "-u", "scripts/factory_cycle_status.py", "--interval", "90"],
    # Director stack: CAP/dayroll board + post-dayroll ship watch (never auto Dra/Alak)
    "director_dashboard": [str(PY), "-u", "scripts/director_dashboard.py", "--poll-seconds", "120"],
    "quota_ship_monitor": [str(PY), "-u", "scripts/quota_reset_ship_monitor.py", "--poll-seconds", "120"],
}

def log(m):
    line = f"[{datetime.now(timezone.utc).isoformat()}] {m}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

procs = {}
outs = {}
for name, cmd in CMDS.items():
    outp = open(ROOT / "dist" / f"{name}.sup.out.log", "a", encoding="utf-8")
    errp = open(ROOT / "dist" / f"{name}.sup.err.log", "a", encoding="utf-8")
    outp.write(f"\n--- spawn {datetime.now(timezone.utc).isoformat()} ---\n"); outp.flush()
    p = subprocess.Popen(cmd, cwd=str(ROOT), stdout=outp, stderr=errp, env=env)
    procs[name] = p
    outs[name] = (outp, errp)
    log(f"spawn {name} pid={p.pid}")

# Also clear stale aggressive lock if our loop is the owner later
while True:
    time.sleep(30)
    for name, cmd in CMDS.items():
        p = procs[name]
        if p.poll() is not None:
            log(f"dead {name} code={p.returncode} — restart")
            outp, errp = outs[name]
            outp.write(f"\n--- respawn {datetime.now(timezone.utc).isoformat()} ---\n"); outp.flush()
            # clear stale lock for loop
            if name == "aggressive_loop":
                lock = ROOT / "dist" / "aggressive_loop.lock"
                try:
                    if lock.exists():
                        lock.unlink()
                except Exception:
                    pass
            p2 = subprocess.Popen(cmd, cwd=str(ROOT), stdout=outp, stderr=errp, env=env)
            procs[name] = p2
            log(f"spawn {name} pid={p2.pid}")
