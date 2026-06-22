"""Build agent/lucario_mcts_runtime.py fresh from the official RL+MCTS notebook.

Run once after cloning or when refreshing from upstream sample:
  python scripts/bootstrap_lucario_mcts_runtime.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "reinforcement-learning-and-mcts-sample-code.ipynb"
OUT = ROOT / "agent" / "lucario_mcts_runtime.py"

HEADER = '''"""Mega Lucario ex RL+MCTS runtime (fresh build from official sample).

Built by scripts/bootstrap_lucario_mcts_runtime.py — do not hand-edit the
mechanical sample block; re-run bootstrap after sample updates, then re-apply
patches in PATCH markers below.

Fixes vs Kaggle sample:
  - Real opponent deck in search_begin (not Snorlax 1072)
  - d128 training defaults; draw terminal value 0
  - Champion-gated eval helpers for field training
"""

from __future__ import annotations

import csv
import glob
import json
import math
import os
import random
import sys
import time
from pathlib import Path

import torch
import torch.nn
import torch.nn.functional
import torch.optim


def _bootstrap_cg_path() -> str:
    """Return directory added to sys.path (parent of the cg package)."""
    root = Path(__file__).resolve().parents[1]
    env = os.environ.get("CG_LIB", "").strip()
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env))
    candidates.extend([
        root / "cg-lib",
        root / "data" / "sim" / "sample_submission",
    ])
    for hit in glob.glob("/kaggle/input/**/cg-lib", recursive=True):
        candidates.append(Path(hit))
    for p in candidates:
        if (p / "cg" / "game.py").exists():
            sys.path.insert(0, str(p))
            return str(p)
        if p.name == "cg" and (p / "game.py").exists():
            sys.path.insert(0, str(p.parent))
            return str(p.parent)
    raise FileNotFoundError(
        "cg engine not found. Set CG_LIB or run scripts/fetch_sim_engine.py "
        "(Windows cg.dll) or place cg-lib/ with cg/ next to this repo."
    )


_BOOT = _bootstrap_cg_path()

'''

CONFIG = '''
# --- training profile (d128 basic; override via env LUC_*) --------------------
def _ei(name, default):
    return int(os.environ.get(name, default))


def _ef(name, default):
    return float(os.environ.get(name, default))


SEED = _ei("LUC_SEED", 42)
SEARCH_COUNT = _ei("LUC_SEARCH_COUNT", 12)
BATCH_SIZE = _ei("LUC_BATCH", 128)
LR = _ef("LUC_LR", 3e-4)
GRAD_CLIP = _ef("LUC_GRAD_CLIP", 1.0)
GATE_GAMES = _ei("LUC_GATE_GAMES", 20)
GATE_WINRATE = _ef("LUC_GATE_WINRATE", 0.55)
SELFPLAY_GAMES = _ei("LUC_SELFPLAY_GAMES", 40)
EVAL_GAMES = _ei("LUC_EVAL_GAMES", 20)
REPLAY_ITERS = _ei("LUC_REPLAY_ITERS", 2)
TEMP_PLIES = _ei("LUC_TEMP_PLIES", 8)
VALUE_LAMBDA = _ef("LUC_VALUE_LAMBDA", 0.9)
TIME_BUDGET = _ef("LUC_TIME_BUDGET_SEC", 6.0 * 3600)

D_MODEL = _ei("LUC_D_MODEL", 128)
NUM_HEADS = _ei("LUC_HEADS", 2)
D_FF = _ei("LUC_D_FF", 256)
ENC_LAYERS = _ei("LUC_ENC_LAYERS", 1)
DEC_LAYERS = _ei("LUC_DEC_LAYERS", 1)

WORK = os.environ.get("LUC_WORK", "rl_mcts_field/lucarioex_v1")

'''

MCTS_PATCH = '''
# === PATCH: field-aware MCTS (Fix #3) ========================================

def _sample_hidden(deck: list[int], n: int) -> list[int]:
    if n <= 0:
        return []
    if n <= len(deck):
        return random.sample(deck, n)
    return (deck * (n // len(deck) + 1))[:n]


def _stub_pokemon_id(deck: list[int]) -> int:
    for cid in deck:
        data = card_table.get(cid)
        if data is not None and data.cardType == CardType.POKEMON:
            return cid
    return deck[0] if deck else 677


def _stub_energy_id(deck: list[int]) -> int:
    for cid in deck:
        data = card_table.get(cid)
        if data is not None and data.cardType in (CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY):
            return cid
    return 6


def mcts_agent(
    obs_dict,
    your_deck: list[int],
    model,
    *,
    opp_deck: list[int] | None = None,
    add_noise: bool = False,
    temperature: float = 0.0,
):
    """MCTS with legal-option children only; opponent belief from real deck list."""
    opp_deck = opp_deck or your_deck
    obs = to_observation_class(obs_dict)
    your_index = obs.current.yourIndex
    state = obs.current
    opp_ps = state.players[1 - your_index]
    active = opp_ps.active

    search_state = search_begin(
        obs,
        your_deck=_sample_hidden(your_deck, state.players[your_index].deckCount),
        your_prize=_sample_hidden(your_deck, len(state.players[your_index].prize)),
        opponent_deck=_sample_hidden(opp_deck, opp_ps.deckCount),
        opponent_prize=_sample_hidden(opp_deck, len(opp_ps.prize)),
        opponent_hand=[_stub_energy_id(opp_deck)] * opp_ps.handCount,
        opponent_active=[_stub_pokemon_id(opp_deck)] if len(active) > 0 and active[0] is None else [],
    )
    root, sample = create_node(None, search_state, your_index, your_deck, model)

    for _ in range(SEARCH_COUNT):
        current = root
        nxt = None
        while True:
            value = -1e9
            c = 0.4 * math.sqrt(current.visit)
            for child in current.children:
                visit = 0
                if child.node is None:
                    v = current.total / current.visit
                else:
                    v = child.node.total / child.node.visit
                    visit = child.node.visit
                if current.state.observation.current.yourIndex != your_index:
                    v = -v
                v += c * child.prob / (1 + visit)
                if value < v:
                    value = v
                    nxt = child
            if nxt is None:
                break
            if nxt.node is None:
                ss = search_step(current.state.searchId, nxt.select)
                nxt.node, _ = create_node(current, ss, your_index, your_deck, model)
                break
            current = nxt.node
            if current.state.observation.current.result >= 0:
                current.backprop(current.value)
                break

    visited = [(c, c.node.visit) for c in root.children if c.node is not None]
    if visited:
        if temperature > 0.0 and len(visited) > 1:
            weights = [v ** (1.0 / temperature) for _, v in visited]
            tot = sum(weights) or 1.0
            r = random.random() * tot
            acc, max_child = 0.0, visited[-1][0]
            for (child, _), w in zip(visited, weights):
                acc += w
                if r <= acc:
                    max_child = child
                    break
        else:
            max_child = max(visited, key=lambda t: t[1])[0]
    else:
        max_child = root.children[0] if root.children else Child(
            random.sample(list(range(len(obs.select.option))), obs.select.maxCount), 1.0
        )

    min_value = 10.0
    for child in root.children:
        if child.node is not None:
            v = child.node.total / child.node.visit
            if min_value > v:
                min_value = v
    if sample is not None:
        sample.value = root.total / root.visit
        for i, child in enumerate(root.children):
            base = sample.value
            if child.node is None:
                v = min_value - base - 0.03
            else:
                v = child.node.total / child.node.visit - base
            sample.policy[i] = max(-1.0, min(1.0, v))

    search_end()
    return max_child.select, sample


def load_lucario_deck(path: str | Path | None = None) -> list[int]:
    p = Path(path) if path else Path(__file__).resolve().parents[1] / "agent_decks" / "real_mega_lucario_ex.csv"
    ids = [int(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    if len(ids) != 60:
        raise ValueError(f"{p} has {len(ids)} cards, expected 60")
    return ids


LUCARIO_DECK = load_lucario_deck()


def label_samples(samples, terminal_result: int, your_index: int, sink: list) -> None:
    """terminal_result: winner index, or 2 for draw (simulator simultaneous KO)."""
    if terminal_result == 2:
        value = 0.0
    elif terminal_result == your_index:
        value = 1.0
    else:
        value = -1.0
    for sample in reversed(samples):
        if sample is None:
            continue
        sample.value = (value + sample.value) * 0.5
        value = value * VALUE_LAMBDA + sample.value * (1.0 - VALUE_LAMBDA)
        sink.append(sample)


def train_on_samples(model, optimizer, scheduler, scaler, device, loss_fn_enc, loss_fn_dec, sample_list):
    if not sample_list:
        return 0.0
    model.train()
    random.shuffle(sample_list)
    batch_count = len(sample_list) // BATCH_SIZE
    if batch_count == 0:
        return 0.0
    total_loss = 0.0
    use_amp = device.type == "cuda"
    for i in range(batch_count):
        input_enc = LearnInput()
        input_dec = LearnInput()
        mask, label_enc, label_dec = [], [], []
        start = BATCH_SIZE * i
        for j in range(start, start + BATCH_SIZE):
            sample = sample_list[j]
            input_enc.add(sample.sv_enc)
            input_dec.add(sample.sv_dec)
            label_enc.append(sample.value)
            label_dec.extend(sample.policy)
            for _ in range(len(sample.policy)):
                mask.append(1.0)
            for _ in range(64 - len(sample.policy)):
                mask.append(0.0)
                label_dec.append(0.0)
                input_dec.offset.append(len(input_dec.index))

        mask_t = torch.tensor(mask, dtype=torch.float32, device=device).view(BATCH_SIZE, -1)
        le_t = torch.tensor(label_enc, dtype=torch.float32, device=device).view(BATCH_SIZE, -1)
        ld_t = torch.tensor(label_dec, dtype=torch.float32, device=device).view(BATCH_SIZE, -1)

        optimizer.zero_grad()
        with torch.autocast(device_type="cuda", enabled=use_amp):
            out_enc, out_dec = model(
                torch.tensor(input_enc.index, dtype=torch.int32, device=device),
                torch.tensor(input_enc.value, dtype=torch.float32, device=device),
                torch.tensor(input_enc.offset, dtype=torch.int32, device=device),
                torch.tensor(input_dec.index, dtype=torch.int32, device=device),
                torch.tensor(input_dec.value, dtype=torch.float32, device=device),
                torch.tensor(input_dec.offset, dtype=torch.int32, device=device),
            )
            loss_enc = loss_fn_enc(out_enc, le_t)
            loss_dec = (loss_fn_dec(out_dec, ld_t) * mask_t).sum() / float(BATCH_SIZE)
            loss = loss_enc + loss_dec

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
        scaler.step(optimizer)
        scaler.update()
        total_loss += float(loss.detach())
    if scheduler is not None:
        scheduler.step()
    return total_loss / batch_count


def selfplay_game(model, deck: list[int]) -> list:
    out: list = []
    obs, start = battle_start(deck, deck)
    if start.errorPlayer >= 0:
        raise ValueError(f"deck error type={start.errorType}")
    samples: list[list] = [[], []]
    ply = 0
    while obs["current"]["result"] < 0:
        yi = obs["current"]["yourIndex"]
        temp = 1.0 if ply < TEMP_PLIES else 0.0
        selected, sample = mcts_agent(
            obs, deck, model, opp_deck=deck, add_noise=True, temperature=temp,
        )
        samples[yi].append(sample)
        obs = battle_select(selected)
        ply += 1
    battle_finish()
    result = obs["current"]["result"]
    for i in range(2):
        label_samples(samples[i], result, i, out)
    return out


def eval_vs_random(model, deck: list[int], games: int) -> float:
    wins = 0
    model.eval()
    with torch.inference_mode():
        for i in range(games):
            your_index = i % 2
            decks = (deck, deck) if your_index == 0 else (deck, deck)
            obs, start = battle_start(*decks)
            if start.errorPlayer >= 0:
                raise ValueError(f"deck error type={start.errorType}")
            while obs["current"]["result"] < 0:
                if obs["current"]["yourIndex"] == your_index:
                    selected, _ = mcts_agent(obs, deck, model, opp_deck=deck)
                else:
                    selected = random_agent(obs)
                obs = battle_select(selected)
            battle_finish()
            if obs["current"]["result"] == your_index:
                wins += 1
    denom = max(1, games)
    return wins / denom


def eval_vs_model(candidate, champion, deck: list[int], games: int) -> float:
    wins = 0
    candidate.eval()
    champion.eval()
    with torch.inference_mode():
        for i in range(games):
            your_index = i % 2
            obs, start = battle_start(deck, deck)
            if start.errorPlayer >= 0:
                raise ValueError(f"deck error type={start.errorType}")
            while obs["current"]["result"] < 0:
                if obs["current"]["yourIndex"] == your_index:
                    selected, _ = mcts_agent(obs, deck, candidate, opp_deck=deck)
                else:
                    selected, _ = mcts_agent(obs, deck, champion, opp_deck=deck)
                obs = battle_select(selected)
            battle_finish()
            if obs["current"]["result"] == your_index:
                wins += 1
    return wins / max(1, games)

'''

TRAILER = '''
if __name__ == "__main__":
    print("lucario_mcts_runtime loaded; use scripts/train_lucario_field_mcts.py to train.")
'''


def main() -> int:
    if not NOTEBOOK.exists():
        raise FileNotFoundError(NOTEBOOK)
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    src = "".join(nb["cells"][1]["source"])

    # Drop notebook kaggle cg path and inline training loop.
    src = re.sub(r"sys\.path\.append\(glob\.glob\('/kaggle/input/\*\*/cg-lib'.*?\)\[0\]\)\n", "", src)
    cut_markers = [
        "\n# A sample deck for training.",
        "\ndevice = torch.device",
        "\n# The main training loop.",
    ]
    for m in cut_markers:
        if m in src:
            src = src.split(m)[0]

    # Remove original mcts_agent (replaced by PATCH).
    src = re.sub(
        r"# We will perform exploration using MCTS.*?return \(max_child\.select, sample\)\n",
        "",
        src,
        flags=re.DOTALL,
    )

    # Sample SEARCH_COUNT=10 -> use module SEARCH_COUNT from CONFIG (remove duplicate).
    src = re.sub(r"^SEARCH_COUNT = 10.*\n", "", src, flags=re.MULTILINE)

    out = HEADER + CONFIG + src + MCTS_PATCH + TRAILER
    OUT.write_text(out, encoding="utf-8")
    print(f"wrote {OUT} ({len(out.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
