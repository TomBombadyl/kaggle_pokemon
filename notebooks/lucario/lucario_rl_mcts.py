"""
Mega Lucario ex — Reinforcement Learning + MCTS trainer.

Derived from the official PTCG "Reinforcement Learning and MCTS sample code"
(kiyotah). Same Search / Battle APIs and transformer policy-value model, but
the sample deck is swapped for the Mega Lucario ex deck and the training loop
is hardened for a long, robust GPU run.

WHAT CHANGED vs the sample (all knobs are env-overridable, see CONFIG):
  - Deck            : sample_deck  -> Mega Lucario ex 60-card list.
  - Model capacity  : d_model 128->256, heads 2->4, ff 256->512, enc/dec 1->2.
  - MCTS strength   : SEARCH_COUNT 10 -> 48 simulations per move.
  - Training length : 5 iters -> 40 iters, with a wall-clock TIME_BUDGET so the
                      kernel always saves cleanly before Kaggle stops it.
  - Checkpointing   : champion-gating. A new net only becomes the saved "best"
                      if it beats the current champion >= GATE_WINRATE in a head
                      to head match (proper AlphaZero-style promotion). This is
                      the single most important fix: it stops a late, weaker
                      net from overwriting a strong earlier one.
  - Replay buffer   : trains on the last REPLAY_ITERS of self-play, not just the
                      current iter -> smoother value targets, better sample use.
  - Exploration     : Dirichlet root noise + temperature move-sampling during
                      self-play only (greedy during evaluation).
  - Stability/speed : fixed seeds, grad-norm clipping, cosine LR, AMP autocast
                      on CUDA, per-iter metrics.csv, best/latest/iter checkpoints.

OUTPUTS (under WORK = /kaggle/working/lucario_rl):
  model_best.pth      - current champion weights (use this for inference).
  model_latest.pth    - most recent trained net.
  model_iter{N}.pth   - per-iteration snapshot.
  metrics.csv         - iter, vs_random, gate_winrate, promoted, n_samples,
                        loss, elapsed_s.
  run_meta.json       - final summary + config.

VERIFICATION (do this after a run):
  1. metrics.csv "vs_random" should trend up across iters (sample reached ~0.76).
  2. "promoted" should be 1 on the iters where gate_winrate >= GATE_WINRATE.
  3. Re-load model_best.pth and eval vs random for >= 100 games; expect a win
     rate clearly above the random-vs-random ~0.50 baseline.
"""

import csv
import glob
import json
import math
import os
import random
import sys
import time

import torch
import torch.nn
import torch.nn.functional
import torch.optim

# --- locate cg-lib (Kaggle competition input) or local engine -----------------
_cands = glob.glob('/kaggle/input/**/cg-lib', recursive=True)
if _cands:
    sys.path.append(_cands[0])
else:
    # local fallback: repo engine copy
    for p in ('data/sim/sample_submission',
              os.path.join(os.path.dirname(__file__), '..', 'data/sim/sample_submission')):
        if os.path.isdir(os.path.join(p, 'cg')):
            sys.path.append(p)
            break

from cg.api import (
    AreaType,
    Card,
    Observation,
    OptionType,
    PlayerState,
    Pokemon,
    SearchState,
    SelectContext,
    all_attack,
    all_card_data,
    search_begin,
    search_end,
    search_step,
    to_observation_class,
)
from cg.game import battle_start, battle_finish, battle_select


# =============================================================================
# CONFIG  (every value can be overridden with an environment variable)
# =============================================================================
def _ei(name, default):  # env int
    return int(os.environ.get(name, default))


def _ef(name, default):  # env float
    return float(os.environ.get(name, default))


SEED          = _ei("LUC_SEED", 42)
SEARCH_COUNT  = _ei("LUC_SEARCH_COUNT", 48)     # MCTS sims per move (was 10)
NUM_ITERS     = _ei("LUC_ITERS", 40)            # outer self-play/train iters
EVAL_GAMES    = _ei("LUC_EVAL_GAMES", 60)       # vs-random anchor games
GATE_GAMES    = _ei("LUC_GATE_GAMES", 40)       # candidate-vs-champion games
SELFPLAY_GAMES= _ei("LUC_SELFPLAY_GAMES", 120)  # self-play games per iter
GATE_WINRATE  = _ef("LUC_GATE_WINRATE", 0.55)   # promote champion if >= this
REPLAY_ITERS  = _ei("LUC_REPLAY_ITERS", 3)      # iters of samples kept for train
BATCH_SIZE    = _ei("LUC_BATCH", 128)
LR            = _ef("LUC_LR", 3e-4)
GRAD_CLIP     = _ef("LUC_GRAD_CLIP", 1.0)
TIME_BUDGET   = _ef("LUC_TIME_BUDGET_SEC", 8.0 * 3600)  # stop before Kaggle kills

# model size
D_MODEL       = _ei("LUC_D_MODEL", 256)
NUM_HEADS     = _ei("LUC_HEADS", 4)
D_FF          = _ei("LUC_D_FF", 512)
ENC_LAYERS    = _ei("LUC_ENC_LAYERS", 2)
DEC_LAYERS    = _ei("LUC_DEC_LAYERS", 2)

# exploration (self-play only)
DIRICHLET_ALPHA = _ef("LUC_DIR_ALPHA", 0.3)
DIRICHLET_FRAC  = _ef("LUC_DIR_FRAC", 0.25)
TEMP_PLIES      = _ei("LUC_TEMP_PLIES", 8)   # sample moves for first N plies

WORK = "/kaggle/working/lucario_rl" if os.path.isdir("/kaggle/working") else "out"
os.makedirs(WORK, exist_ok=True)

# --- Mega Lucario ex deck (60 cards) -----------------------------------------
# 4 Mega Lucario ex (678) + Riolu (677); Solrock/Lunatone (676/675) accel;
# Makuhita/Hariyama (673/674); 13 Fighting Energy (6); standard trainer engine.
LUCARIO_DECK = [
    678, 678, 678, 678,            # Mega Lucario ex
    677, 677, 677,                 # Riolu
    676, 676, 676,                 # Solrock
    675, 675,                      # Lunatone
    673, 673,                      # Makuhita
    674, 674,                      # Hariyama
    1102, 1102, 1102, 1102,        # Dusk Ball
    1141, 1141, 1141, 1141,        # Premium Power Pro
    1142, 1142, 1142, 1142,        # Fighting Gong
    1152, 1152, 1152, 1152,        # Poke Pad
    1123, 1123,                    # Switch
    1159,                          # Hero's Cape (tool)
    1192, 1192, 1192, 1192,        # Carmine
    1227, 1227, 1227, 1227,        # Lillie's Determination
    1182, 1182,                    # Boss's Orders
    1252, 1252,                    # Gravity Mountain (stadium)
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,  # 13 Basic Fighting Energy
]
assert len(LUCARIO_DECK) == 60, f"deck must be 60, got {len(LUCARIO_DECK)}"


# =============================================================================
# Card data / vocabulary sizes  (unchanged from sample)
# =============================================================================
all_card = all_card_data()
card_table = {c.cardId: c for c in all_card}
card_count = max(all_card, key=lambda c: c.cardId).cardId + 1
attack_count = max(all_attack(), key=lambda a: a.attackId).attackId + 1

num_words_encoder = 24
encoder_size = 22000

decoder_main_feature = 8
decoder_attack_offset = 14
decoder_card_offset = decoder_attack_offset + attack_count
decoder_size = decoder_card_offset + (1 + decoder_main_feature + SelectContext.RECOVER_SPECIAL_CONDITION) * card_count


# =============================================================================
# Model  (parameterized; identical math to the sample)
# =============================================================================
class DecoderLayer(torch.nn.Module):
    def __init__(self, d_model: int, num_heads: int, d_feedforward: int):
        super().__init__()
        self.attention = torch.nn.MultiheadAttention(d_model, num_heads)
        self.fc1 = torch.nn.Linear(d_model, d_feedforward)
        self.fc2 = torch.nn.Linear(d_feedforward, d_model)
        self.norm1 = torch.nn.LayerNorm(d_model)
        self.norm2 = torch.nn.LayerNorm(d_model)

    def forward(self, x, encoder_out):
        y, _ = self.attention(x, encoder_out, encoder_out, need_weights=False)
        res = self.norm1(x + y)
        y = self.fc1(res)
        y = torch.nn.functional.relu(y)
        y = self.fc2(y)
        return self.norm2(res + y)


class MyModel(torch.nn.Module):
    def __init__(self, d_model, num_heads, d_feedforward, num_layers_encoder, num_layers_decoder):
        super().__init__()
        self.d_model = d_model
        self.encoder_bag = torch.nn.EmbeddingBag(encoder_size, d_model, mode="sum")
        encoder_layer = torch.nn.TransformerEncoderLayer(d_model, num_heads, d_feedforward, 0)
        self.encoder = torch.nn.TransformerEncoder(encoder_layer, num_layers_encoder, enable_nested_tensor=False)
        self.encoder_fc = torch.nn.Linear(d_model, 1)
        self.decoder_bag = torch.nn.EmbeddingBag(decoder_size, d_model, mode="sum")
        self.decoder = torch.nn.ModuleList(DecoderLayer(d_model, num_heads, d_feedforward) for _ in range(num_layers_decoder))
        self.decoder_fc = torch.nn.Linear(d_model, 1)

    def forward(self, index_encoder, value_encoder, offset_encoder,
                index_decoder, value_decoder, offset_decoder):
        v = self.encoder_bag(index_encoder, offset_encoder, value_encoder)
        v = v.reshape(-1, num_words_encoder, self.d_model).transpose(0, 1)
        batch_size = v.size(1)
        encoder_out = self.encoder(v)
        v = self.encoder_fc(encoder_out)
        v = torch.tanh(v.mean(0))

        p = self.decoder_bag(index_decoder, offset_decoder, value_decoder)
        p = p.reshape(batch_size, -1, self.d_model).transpose(0, 1)
        for layer in self.decoder:
            p = layer(p, encoder_out)
        p = self.decoder_fc(p)
        p = p.transpose(0, 1).view(batch_size, -1)
        p = torch.tanh(p)
        return (v, p)


# =============================================================================
# Feature engineering  (verbatim from the sample — matches the engine schema)
# =============================================================================
class SparseVector:
    def __init__(self):
        self.index = []
        self.value = []
        self.offset = []
        self.pos = 0

    def add(self, index, value):
        value = float(value)
        if value != 0.0:
            self.index.append(self.pos + index)
            self.value.append(value)

    def add_pos(self, pos):
        self.pos += pos

    def add_single(self, value):
        value = float(value)
        if value != 0.0:
            self.index.append(self.pos)
            self.value.append(value)
        self.pos += 1

    def word_start(self):
        self.offset.append(len(self.index))


def add_card(sv, card):
    if card is not None:
        sv.add(card.id, 1)
    sv.add_pos(card_count)


def add_cards(sv, cards, value):
    if cards is not None:
        for card in cards:
            sv.add(card.id, value)
    sv.add_pos(card_count)


def add_pokemon(sv, poke):
    if poke is None:
        sv.add_single(1)
        sv.add_pos(1 + 3 * card_count)
    else:
        sv.add_single(0)
        sv.add_single(poke.hp / 400)
        add_card(sv, poke)
        add_cards(sv, poke.tools, 1.0)
        add_cards(sv, poke.energyCards, 0.5)


def add_player(sv, ps):
    sv.add_single(ps.deckCount / 60)
    sv.add_single(len(ps.discard) / 60)
    sv.add_single(ps.handCount / 8)
    sv.add_single(len(ps.bench) / 5)
    sv.add(len(ps.prize), 1)
    sv.add_pos(7)
    sv.add_single(ps.poisoned)
    sv.add_single(ps.burned)
    sv.add_single(ps.asleep)
    sv.add_single(ps.paralyzed)
    sv.add_single(ps.confused)
    add_cards(sv, ps.discard, 0.25)


def get_encoder_input(obs, your_deck):
    your_index = obs.current.yourIndex
    state = obs.current
    sv = SparseVector()
    for i in range(2):
        ps = state.players[i ^ your_index]
        for j in range(8):
            sv.word_start()
            pos = sv.pos
            if j < len(ps.bench):
                add_pokemon(sv, ps.bench[j])
            else:
                add_pokemon(sv, None)
            if j != 7:
                sv.pos = pos
    for i in range(2):
        ps = state.players[i ^ your_index]
        sv.word_start()
        if 0 < len(ps.active):
            add_pokemon(sv, ps.active[0])
        else:
            add_pokemon(sv, None)
    for i in range(2):
        ps = state.players[i ^ your_index]
        sv.word_start()
        add_player(sv, ps)
    sv.word_start()
    add_cards(sv, state.players[your_index].hand, 0.25)
    sv.word_start()
    for id in your_deck:
        sv.add(id, 0.25)
    sv.add_pos(card_count)
    sv.word_start()
    add_cards(sv, state.stadium, 1.0)
    sv.word_start()
    sv.add_single(1)
    sv.add_single(state.turn / 10)
    sv.add_single(state.firstPlayer == your_index)
    return sv


def get_card(obs, area, index, player_index):
    ps = obs.current.players[player_index]
    match area:
        case AreaType.DECK:
            return obs.select.deck[index]
        case AreaType.HAND:
            return ps.hand[index]
        case AreaType.DISCARD:
            return ps.discard[index]
        case AreaType.ACTIVE:
            return ps.active[index]
        case AreaType.BENCH:
            return ps.bench[index]
        case AreaType.PRIZE:
            return ps.prize[index]
        case AreaType.STADIUM:
            return obs.current.stadium[index]
        case AreaType.LOOKING:
            return obs.current.looking[index]
        case _:
            return None


def decoder_main(sv, feature_index, card):
    if card is not None:
        sv.add(decoder_card_offset + feature_index * card_count + card.id, 1)


def decoder_card_id(sv, context, card_id):
    sv.add(decoder_card_offset + (decoder_main_feature + context) * card_count + card_id, 1)


def decoder_card(sv, context, card):
    if card is not None:
        decoder_card_id(sv, context, card.id)


def get_decoder_input(obs, actions):
    sv = SparseVector()
    your_index = obs.current.yourIndex
    ps = obs.current.players[your_index]
    context = obs.select.context
    for action in actions:
        sv.word_start()
        if len(action) == 0:
            sv.add(0, 1)
            continue
        for i in action:
            o = obs.select.option[i]
            match o.type:
                case OptionType.END:
                    sv.add(1, 1)
                case OptionType.YES:
                    sv.add(2, 1)
                case OptionType.NO:
                    sv.add(3, 1)
                case OptionType.SPECIAL_CONDITION:
                    sv.add(4 + o.specialConditionType, 1)
                case OptionType.NUMBER:
                    sv.add(9 + min(o.number, 4), 1)
                case OptionType.ATTACK:
                    sv.add(decoder_attack_offset + o.attackId, 1)
                case OptionType.PLAY:
                    decoder_main(sv, 0, ps.hand[o.index])
                case OptionType.ATTACH:
                    decoder_main(sv, 1, get_card(obs, o.area, o.index, your_index))
                    decoder_main(sv, 2, get_card(obs, o.inPlayArea, o.inPlayIndex, your_index))
                case OptionType.EVOLVE:
                    decoder_main(sv, 3, get_card(obs, o.area, o.index, your_index))
                    decoder_main(sv, 4, get_card(obs, o.inPlayArea, o.inPlayIndex, your_index))
                case OptionType.ABILITY:
                    decoder_main(sv, 5, get_card(obs, o.area, o.index, your_index))
                case OptionType.DISCARD:
                    decoder_main(sv, 6, get_card(obs, o.area, o.index, your_index))
                case OptionType.RETREAT:
                    decoder_main(sv, 7, ps.active[0])
                case OptionType.CARD:
                    decoder_card(sv, context, get_card(obs, o.area, o.index, o.playerIndex))
                case OptionType.TOOL_CARD:
                    card = get_card(obs, o.area, o.index, o.playerIndex)
                    decoder_card(sv, context, card.tools[o.toolIndex])
                case OptionType.ENERGY_CARD | OptionType.ENERGY:
                    card = get_card(obs, o.area, o.index, o.playerIndex)
                    decoder_card(sv, context, card.energyCards[o.energyIndex])
                case OptionType.SKILL:
                    decoder_card_id(sv, context, o.cardId)
    return sv


def eval_nn(sv_enc, sv_dec, model):
    device = next(model.parameters()).device
    value, policy = model(
        torch.tensor(sv_enc.index, dtype=torch.int32, device=device),
        torch.tensor(sv_enc.value, dtype=torch.float32, device=device),
        torch.tensor(sv_enc.offset, dtype=torch.int32, device=device),
        torch.tensor(sv_dec.index, dtype=torch.int32, device=device),
        torch.tensor(sv_dec.value, dtype=torch.float32, device=device),
        torch.tensor(sv_dec.offset, dtype=torch.int32, device=device))
    return (value.tolist()[0][0], policy.tolist()[0])


# =============================================================================
# MCTS
# =============================================================================
class LearnSample:
    def __init__(self, value, policy, sv_enc, sv_dec):
        self.value = value
        self.policy = policy
        self.sv_enc = sv_enc
        self.sv_dec = sv_dec


class Child:
    def __init__(self, select, prob):
        self.node = None
        self.select = select
        self.prob = prob


class Node:
    def __init__(self, parent, state):
        self.value = -2.0
        self.total = 0.0
        self.visit = 0
        self.parent = parent
        self.children = []
        self.state = state

    def backprop(self, value):
        self.total += value
        self.visit += 1
        if self.parent is not None:
            self.parent.backprop(value)


def _dirichlet(alpha, n):
    g = [random.gammavariate(alpha, 1.0) for _ in range(n)]
    s = sum(g) or 1.0
    return [x / s for x in g]


def create_node(parent, search_state, your_index, your_deck, model, add_noise=False):
    node = Node(parent, search_state)
    obs = search_state.observation
    state = obs.current
    if state.result >= 0:
        if state.result == 2:
            node.value = 0
        elif state.result == your_index:
            node.value = 1
        else:
            node.value = -1
        node.backprop(node.value)
        return (node, None)

    actions = []
    indices = list(range(obs.select.maxCount))
    for _ in range(64):
        actions.append(indices.copy())
        for i in range(len(indices)):
            index = len(indices) - i - 1
            if indices[index] < len(obs.select.option) - i - 1:
                indices[index] += 1
                for j in range(index + 1, len(indices)):
                    indices[j] = indices[j - 1] + 1
                break
        else:
            break

    sv_enc = get_encoder_input(obs, your_deck)
    sv_dec = get_decoder_input(obs, actions)
    value, policy = eval_nn(sv_enc, sv_dec, model)
    v = value
    if state.yourIndex != your_index:
        v = -v
    node.value = v
    node.backprop(v)

    probs = []
    s = 0.0
    for i in range(len(policy)):
        p = math.exp(policy[i] * 10.0)
        probs.append(p)
        s += p
    probs = [p / s for p in probs]

    # AlphaZero-style Dirichlet root noise (self-play exploration only)
    if add_noise and len(probs) > 0:
        noise = _dirichlet(DIRICHLET_ALPHA, len(probs))
        probs = [(1 - DIRICHLET_FRAC) * p + DIRICHLET_FRAC * n for p, n in zip(probs, noise)]

    for i in range(len(policy)):
        node.children.append(Child(actions[i], probs[i]))

    sample = LearnSample(value, policy, sv_enc, sv_dec)
    return (node, sample)


def mcts_agent(obs_dict, your_deck, model, add_noise=False, temperature=0.0):
    """Run MCTS; return (selected_option_indices, training_sample).

    add_noise/temperature are used only during self-play data generation.
    Evaluation calls with the defaults (no noise, greedy)."""
    obs = to_observation_class(obs_dict)
    your_index = obs.current.yourIndex
    state = obs.current
    active = state.players[1 - your_index].active
    search_state = search_begin(
        obs,
        your_deck=random.sample(your_deck, state.players[your_index].deckCount),
        your_prize=random.sample(your_deck, len(state.players[your_index].prize)),
        opponent_deck=[1072] * state.players[1 - your_index].deckCount,
        opponent_prize=[1] * len(state.players[1 - your_index].prize),
        opponent_hand=[1] * state.players[1 - your_index].handCount,
        opponent_active=[1072] if len(active) > 0 and active[0] is None else [])
    root, sample = create_node(None, search_state, your_index, your_deck, model, add_noise=add_noise)

    for _ in range(SEARCH_COUNT):
        current = root
        while True:
            value = -1e9
            nxt = None
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
            else:
                current = nxt.node
                if current.state.observation.current.result >= 0:
                    current.backprop(current.value)
                    break

    # ----- pick the move to play -----
    visited = [(c, c.node.visit) for c in root.children if c.node is not None]
    max_child = None
    if visited:
        if temperature > 0.0 and len(visited) > 1:
            weights = [v ** (1.0 / temperature) for _, v in visited]
            tot = sum(weights) or 1.0
            r = random.random() * tot
            acc = 0.0
            for (child, _), w in zip(visited, weights):
                acc += w
                if r <= acc:
                    max_child = child
                    break
            if max_child is None:
                max_child = visited[-1][0]
        else:
            max_child = max(visited, key=lambda t: t[1])[0]
    else:
        # no child expanded (degenerate) -> fall back to a legal action
        max_child = root.children[0] if root.children else Child(
            random.sample(list(range(len(obs.select.option))), obs.select.maxCount), 1.0)

    # ----- training labels from root statistics (independent of move picked) ---
    min_value = 10.0
    for child in root.children:
        if child.node is not None:
            v = child.node.total / child.node.visit
            if min_value > v:
                min_value = v
    if sample is not None:
        sample.value = root.total / root.visit
        for i in range(len(root.children)):
            child = root.children[i]
            base = sample.value
            if child.node is None:
                v = min_value - base - 0.03
            else:
                v = child.node.total / child.node.visit - base
            sample.policy[i] = max(-1.0, min(1.0, v))

    search_end()
    return (max_child.select, sample)


# =============================================================================
# Batch helpers / opponents
# =============================================================================
class LearnInput:
    def __init__(self):
        self.index = []
        self.value = []
        self.offset = []

    def add(self, sv):
        count = len(self.index)
        self.index.extend(sv.index)
        self.value.extend(sv.value)
        for o in sv.offset:
            self.offset.append(o + count)


def random_agent(obs_dict):
    obs = to_observation_class(obs_dict)
    return random.sample(list(range(len(obs.select.option))), obs.select.maxCount)


def progress(count, text):
    current = 0
    while True:
        percent = 100 * current // count
        sys.stderr.write(f"\r{text} {percent}%   ")
        sys.stderr.flush()
        if current >= count:
            sys.stderr.write("\n")
            sys.stderr.flush()
            break
        yield current
        current += 1


def _deck_error(start_data):
    msgs = {1: "invalid card ID", 2: "max 4 same-name (non-basic-energy)",
            3: "no Basic Pokemon", 4: "only one Ace Spec allowed"}
    raise ValueError("Deck error: " + msgs.get(start_data.errorType, "unknown"))


# =============================================================================
# Evaluation
# =============================================================================
def eval_vs_random(model, deck, games):
    """Champion plays vs the random agent. Returns win rate (draws excluded)."""
    wins = losses = 0
    model.eval()
    with torch.inference_mode():
        for i in range(games):
            obs, start = battle_start(deck, deck)
            if start.errorPlayer >= 0:
                _deck_error(start)
            your_index = i % 2
            while obs["current"]["result"] < 0:
                if obs["current"]["yourIndex"] == your_index:
                    selected, _ = mcts_agent(obs, deck, model)
                else:
                    selected = random_agent(obs)
                obs = battle_select(selected)
            r = obs["current"]["result"]
            battle_finish()
            if r == your_index:
                wins += 1
            elif r != 2:
                losses += 1
    return wins / max(1, wins + losses)


def eval_vs_model(candidate, champion, deck, games):
    """Head-to-head. Returns candidate win rate (draws excluded)."""
    wins = losses = 0
    candidate.eval()
    champion.eval()
    with torch.inference_mode():
        for i in range(games):
            obs, start = battle_start(deck, deck)
            if start.errorPlayer >= 0:
                _deck_error(start)
            cand_index = i % 2  # alternate seats for fairness
            while obs["current"]["result"] < 0:
                m = candidate if obs["current"]["yourIndex"] == cand_index else champion
                selected, _ = mcts_agent(obs, deck, m)
                obs = battle_select(selected)
            r = obs["current"]["result"]
            battle_finish()
            if r == cand_index:
                wins += 1
            elif r != 2:
                losses += 1
    return wins / max(1, wins + losses)


# =============================================================================
# Training
# =============================================================================
def selfplay_game(model, deck):
    """One self-play game -> list of finished LearnSamples (both seats)."""
    obs, start = battle_start(deck, deck)
    if start.errorPlayer >= 0:
        _deck_error(start)
    samples = [[], []]
    ply = 0
    while obs["current"]["result"] < 0:
        temp = 1.0 if ply < TEMP_PLIES else 0.0
        selected, sample = mcts_agent(obs, deck, model, add_noise=True, temperature=temp)
        samples[obs["current"]["yourIndex"]].append(sample)
        obs = battle_select(selected)
        ply += 1
    result = obs["current"]["result"]
    battle_finish()

    out = []
    LAMBDA = 0.9
    for i in range(2):
        value = 1.0 if i == result else -1.0
        for sample in reversed(samples[i]):
            if sample is None:
                continue
            label = (value + sample.value) * 0.5
            value = value * LAMBDA + sample.value * (1.0 - LAMBDA)
            sample.value = label
            out.append(sample)
    return out


def train_on_samples(model, optimizer, scheduler, scaler, device,
                     loss_fn_enc, loss_fn_dec, sample_list):
    model.train()
    random.shuffle(sample_list)
    batch_count = len(sample_list) // BATCH_SIZE
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
                torch.tensor(input_dec.offset, dtype=torch.int32, device=device))
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
    return total_loss / max(1, batch_count)


def main():
    random.seed(SEED)
    torch.manual_seed(SEED)
    try:
        torch.set_float32_matmul_precision("high")
    except Exception:
        pass

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={device}  deck=Mega Lucario ex  search={SEARCH_COUNT}  "
          f"iters={NUM_ITERS}  model=({D_MODEL},{NUM_HEADS},{D_FF},{ENC_LAYERS},{DEC_LAYERS})",
          flush=True)

    model = MyModel(D_MODEL, NUM_HEADS, D_FF, ENC_LAYERS, DEC_LAYERS).to(device)
    champion = MyModel(D_MODEL, NUM_HEADS, D_FF, ENC_LAYERS, DEC_LAYERS).to(device)
    champion.load_state_dict(model.state_dict())

    optimizer = torch.optim.AdamW(model.parameters(), lr=LR)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, NUM_ITERS))
    scaler = torch.cuda.amp.GradScaler(enabled=device.type == "cuda")
    loss_fn_enc = torch.nn.HuberLoss(delta=0.2)
    loss_fn_dec = torch.nn.HuberLoss(reduction="none", delta=0.1)

    metrics_path = os.path.join(WORK, "metrics.csv")
    with open(metrics_path, "w", newline="") as f:
        csv.writer(f).writerow(
            ["iter", "vs_random", "gate_winrate", "promoted", "n_samples", "loss", "elapsed_s"])

    torch.save(champion.state_dict(), os.path.join(WORK, "model_best.pth"))
    best_vs_random = 0.0
    replay = []  # list of per-iter sample_lists
    it = 0
    t0 = time.time()

    for it in range(NUM_ITERS):
        if time.time() - t0 > TIME_BUDGET:
            print(f"[iter {it}] time budget reached, stopping.", flush=True)
            break

        # ---- self-play data collection (current net) ----
        iter_samples = []
        for _ in progress(SELFPLAY_GAMES, f"[iter {it}] self-play "):
            iter_samples.extend(selfplay_game(model, LUCARIO_DECK))
        replay.append(iter_samples)
        if len(replay) > REPLAY_ITERS:
            replay.pop(0)
        train_pool = [s for chunk in replay for s in chunk]

        # ---- train ----
        loss = train_on_samples(model, optimizer, scheduler, scaler, device,
                                loss_fn_enc, loss_fn_dec, list(train_pool))

        # ---- gate vs champion ----
        gate_wr = eval_vs_model(model, champion, LUCARIO_DECK, GATE_GAMES)
        promoted = 0
        if gate_wr >= GATE_WINRATE:
            champion.load_state_dict(model.state_dict())
            promoted = 1

        # ---- anchor eval vs random (uses current champion) ----
        vs_random = eval_vs_random(champion, LUCARIO_DECK, EVAL_GAMES)

        # ---- checkpoints ----
        torch.save(model.state_dict(), os.path.join(WORK, "model_latest.pth"))
        torch.save(model.state_dict(), os.path.join(WORK, f"model_iter{it}.pth"))
        if promoted or vs_random > best_vs_random:
            torch.save(champion.state_dict(), os.path.join(WORK, "model_best.pth"))
            best_vs_random = max(best_vs_random, vs_random)

        elapsed = time.time() - t0
        with open(metrics_path, "a", newline="") as f:
            csv.writer(f).writerow(
                [it, round(vs_random, 4), round(gate_wr, 4), promoted,
                 len(train_pool), round(loss, 5), round(elapsed, 1)])
        print(f"[iter {it}] vs_random={vs_random:.3f} gate={gate_wr:.3f} "
              f"promoted={promoted} samples={len(train_pool)} loss={loss:.4f} "
              f"elapsed={elapsed/60:.1f}m", flush=True)

    meta = {
        "deck": "mega_lucario_ex", "iters_done": it + 1, "best_vs_random": best_vs_random,
        "config": {k: v for k, v in globals().items()
                   if k.isupper() and isinstance(v, (int, float, str))},
        "device": str(device),
    }
    with open(os.path.join(WORK, "run_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print("DONE. best_vs_random=", best_vs_random, "->", WORK, flush=True)


if __name__ == "__main__":
    main()
