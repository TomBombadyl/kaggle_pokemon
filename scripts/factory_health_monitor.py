import json, re, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(r"E:\PTCG_AI_Battle_Challenge\kaggle_pokemon")
LOG = ROOT / "report" / "aggressive" / "factory_monitor.log"
LOG.parent.mkdir(parents=True, exist_ok=True)
PY_VENV = Path(r"E:\PTCG_AI_Battle_Challenge\.venv\Scripts\python.exe")
PATS = {
    "supervisor": re.compile(r"mainline_supervisor\.py"),
    "loop": re.compile(r"aggressive_loop\.py"),
    "focus": re.compile(r"continuous_focus_gates\.py"),
    "mcts": re.compile(r"train_lucario_field_mcts\.py"),
}

def log(msg):
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def python_cmds():
    out = []
    try:
        import psutil
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = (p.info.get("name") or "").lower()
                if "python" not in name:
                    continue
                cmd = " ".join(p.info.get("cmdline") or [])
                out.append((p.info["pid"], cmd))
            except Exception:
                pass
    except ImportError:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python' } | ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }"],
            capture_output=True, text=True, timeout=60,
        )
        for line in (r.stdout or "").splitlines():
            if "|" in line:
                pid, cmd = line.split("|", 1)
                try:
                    out.append((int(pid), cmd))
                except ValueError:
                    pass
    return out

def roles_up():
    found = {k: [] for k in PATS}
    for pid, cmd in python_cmds():
        for k, pat in PATS.items():
            if pat.search(cmd or ""):
                found[k].append(pid)
    return found

def ensure_supervisor():
    found = roles_up()
    if found["supervisor"]:
        return found
    log(f"DEAD supervisor; roles={ {k:v for k,v in found.items()} } — respawn mainline_supervisor")
    lock = ROOT / "dist" / "aggressive_loop.lock"
    if lock.exists():
        try:
            lock.unlink()
        except Exception:
            pass
    subprocess.Popen(
        [str(PY_VENV), "-u", "scripts/mainline_supervisor.py"],
        cwd=str(ROOT),
        stdout=open(ROOT / "dist" / "mainline_supervisor.out.log", "a"),
        stderr=open(ROOT / "dist" / "mainline_supervisor.err.log", "a"),
    )
    time.sleep(8)
    return roles_up()

def ab_status():
    p = ROOT / "recordings" / "metrics" / "iono_ab_latest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def focus_status():
    p = ROOT / "recordings" / "metrics" / "focus_latest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def main():
    log("factory_monitor START (restart supervisor only if dead; never kill workers)")
    while True:
        found = ensure_supervisor()
        foc = focus_status()
        ab = ab_status()
        ab_s = ""
        if ab and ab.get("rows"):
            ab_s = " | AB " + ", ".join(f"{r.get('lever')}={r.get('iono_wr')}" for r in ab["rows"])
        log(
            f"roles loop={found['loop']} focus={found['focus']} mcts={found['mcts']} sup={found['supervisor']} | "
            f"focus_c={foc.get('cycle')} iono={foc.get('iono_wr')} majkel={foc.get('majkel_wr')} "
            f"flg={foc.get('flg_wr')} dual={foc.get('dual_overall')}{ab_s}"
        )
        # promote note only — never auto-change default lever here
        if ab and ab.get("rows"):
            by = {r.get("lever"): r.get("iono_wr") for r in ab["rows"] if r.get("iono_wr") is not None}
            if "r14n" in by and "r14v" in by:
                d = by["r14v"] - by["r14n"]
                if d >= 3.0:
                    log(f"SIGNAL r14v +{d:.1f}pp vs r14n — confirm n400 before default switch")
                elif by.get("r14v") is not None:
                    log(f"AB delta r14v-r14n={d:.1f}pp (need +3pp to promote)")
        time.sleep(120)

if __name__ == "__main__":
    main()
