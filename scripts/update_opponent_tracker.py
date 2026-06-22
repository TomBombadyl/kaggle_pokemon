#!/usr/bin/env python3
"""
Auto-update OPPONENT_DECK_DISTRIBUTION.md tracker from:
1. Leaderboard snapshot (report/leaderboard_snap_*.json)
2. Episode data (data/episodes/raw/*.json)
3. Gate logs (report/gates/*.txt or *.log)
4. Submission history (report/our_submissions.json)

Usage:
    python scripts/update_opponent_tracker.py

Output:
    Updates report/OPPONENT_DECK_DISTRIBUTION.md in-place
"""

import json
import csv
import glob
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def load_leaderboard_snapshot():
    """Load latest leaderboard snapshot."""
    snapshots = sorted(glob.glob("report/leaderboard_snap_*.json"), reverse=True)
    if not snapshots:
        print("❌ No leaderboard snapshot found. Run: python scripts/update_from_kaggle.py")
        return None

    with open(snapshots[0]) as f:
        data = json.load(f)

    print(f"✅ Loaded leaderboard: {snapshots[0]}")
    return data

def parse_agent_deck(agent_name):
    """Infer deck type from agent name."""
    name_lower = agent_name.lower()

    deck_map = {
        'lucario': 'Mega Lucario-EX',
        'alakazam': 'Alakazam/Kadabra/Abra',
        'dragapult': 'Dragapult-EX',
        'kyogre': 'Kyogre/Water',
        'bellibolt': 'Bellibolt/Water',
        'trevenant': 'Trevenant ex',
        'crustle': 'Crustle/Wall',
        'iono': 'Control/Disruption',
        'abomasnow': 'Abomasnow-EX',
    }

    for key, deck in deck_map.items():
        if key in name_lower:
            return deck

    return "Unknown"

def load_gate_logs():
    """Parse gate logs to extract opponent win rates."""
    results = defaultdict(lambda: {'wins': 0, 'losses': 0})

    gate_files = glob.glob("report/gates/*.txt") + glob.glob("report/gates/*.log")
    for gate_file in gate_files:
        try:
            with open(gate_file) as f:
                for line in f:
                    # Parse lines like: "  13.3%  vs a-sample-rule-based-agent-iono-s-deck  W4 L26 D0 U0"
                    if ' vs ' in line and 'W' in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            # Extract opponent name (everything between 'vs' and 'W')
                            try:
                                vs_idx = parts.index('vs')
                                # Find W...
                                for i, p in enumerate(parts[vs_idx:]):
                                    if p.startswith('W'):
                                        opp_name = ' '.join(parts[vs_idx+1:vs_idx+1+i])
                                        # Parse W/L
                                        w_val = int(p[1:]) if p[1:] else 0
                                        l_val = int(parts[i+vs_idx+1][1:]) if i+vs_idx+1 < len(parts) else 0
                                        results[opp_name]['wins'] += w_val
                                        results[opp_name]['losses'] += l_val
                                        break
                            except (ValueError, IndexError):
                                pass
        except Exception as e:
            print(f"⚠️  Error parsing {gate_file}: {e}")

    return results

def main():
    print("🔄 Updating OPPONENT_DECK_DISTRIBUTION.md...")

    # Load data
    leaderboard = load_leaderboard_snapshot()
    gate_data = load_gate_logs()

    if not leaderboard:
        print("⚠️  Skipping update (no leaderboard data)")
        return

    # Build sections
    top_agents = []
    if 'top_10' in leaderboard:
        for entry in leaderboard['top_10']:
            deck = parse_agent_deck(entry.get('name', 'Unknown'))
            top_agents.append({
                'rank': entry.get('rank', '?'),
                'name': entry.get('name', 'Unknown'),
                'deck': deck,
                'score': entry.get('score', '?')
            })

    opponent_summary = []
    for opp_name, stats in sorted(gate_data.items(), key=lambda x: x[1]['wins'] + x[1]['losses'], reverse=True)[:10]:
        total = stats['wins'] + stats['losses']
        wr = 100 * stats['wins'] // max(1, total)
        deck = parse_agent_deck(opp_name)
        opponent_summary.append({
            'name': opp_name,
            'deck': deck,
            'wr': wr,
            'total': total
        })

    # Update tracker
    tracker_file = Path("report/OPPONENT_DECK_DISTRIBUTION.md")
    if not tracker_file.exists():
        print("⚠️  Tracker file not found. Create it first with initial template.")
        return

    # For now, just print summary
    print("\n✅ TOP RANKED AGENTS:")
    for agent in top_agents[:5]:
        print(f"  #{agent['rank']} {agent['name']:40} | {agent['deck']:30} | μ={agent['score']}")

    print("\n✅ OPPONENT SUMMARY (from gates):")
    for opp in opponent_summary:
        total = opp['total']
        wr = opp['wr']
        print(f"  {wr:3d}% vs {opp['name']:40} | {opp['deck']:30} | {total} games")

    print(f"\n✅ Update report/OPPONENT_DECK_DISTRIBUTION.md manually with above data")
    print(f"   (Auto-update not yet implemented; requires careful table formatting)")

if __name__ == "__main__":
    main()
