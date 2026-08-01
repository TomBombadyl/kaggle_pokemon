import os, subprocess, sys
from pathlib import Path
ROOT = Path(r"E:\PTCG_AI_Battle_Challenge\kaggle_pokemon")
py = r"E:\PTCG_AI_Battle_Challenge\.venv\Scripts\python.exe"
out_dir = ROOT / "report" / "aggressive"
out_dir.mkdir(parents=True, exist_ok=True)

def run(label, lever, games=48):
    env = os.environ.copy()
    env["ARCH_IONO_LEVER"] = lever
    env["PYTHONIOENCODING"] = "utf-8"
    out = out_dir / f"iono_ab_{label}.out"
    err = out_dir / f"iono_ab_{label}.err"
    print(f"start {label} lever={lever}", flush=True)
    with open(out, "w", encoding="utf-8") as fo, open(err, "w", encoding="utf-8") as fe:
        p = subprocess.run(
            [py, "-u", str(ROOT / "scripts" / "gate_archaludon.py"), "--games", str(games), "--opponents", "real_iono"],
            cwd=str(ROOT), env=env, stdout=fo, stderr=fe,
        )
    print(f"done {label} rc={p.returncode}", flush=True)
    print(out.read_text(encoding="utf-8", errors="replace")[-800:], flush=True)

# sequential to avoid thrashing with focus gates — still one at a time
run("none", "none", 40)
run("r14m", "r14m", 40)
