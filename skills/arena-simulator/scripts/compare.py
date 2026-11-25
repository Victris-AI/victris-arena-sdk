#!/usr/bin/env python3
"""Compares two versions of a Victris Arena bot's strategy in the simulator, before you ship one.

Plays them head to head (each side as fighter 1 and as fighter 2, on the same seeds), then each
against the bundled opponents on the same seeds, and prints each side's score with a 95% interval
and how long decide() takes.

    python compare.py --candidate bot.py --baseline bot_v1.py
    python compare.py --candidate bot.py --baseline bot_v1.py --games 600 --against ts-starter,random

Each file defines decide(observation, match), as the Python starter's bot.py does: `match` is
{"id": ..., "rules": ...} from the match's hello. Install the simulator first:
    pip install <the wheel's URL from GET https://victrisarena.com/api, under simulator.python>
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import sys
import time
import traceback
from pathlib import Path

from arena_sim import Simulator


def load(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, Path(path).resolve())
    if spec is None or spec.loader is None:
        sys.exit(f"can't load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(path).resolve().parent))
    spec.loader.exec_module(module)
    if not callable(getattr(module, "decide", None)):
        sys.exit(f"{path} defines no decide()")
    return module.decide


class Player:
    """Calls a strategy as the starters do: a bug in it makes that tick idle instead of crashing."""

    def __init__(self, side: str, decide):
        self.side, self.decide = side, decide
        self.calls, self.seconds, self.slowest, self.errors, self.first_error = 0, 0.0, 0.0, 0, None

    def turn(self, observation: dict, match: dict) -> dict:
        started = time.perf_counter()
        try:
            return self.decide(observation, match) or {}
        except Exception:
            self.errors += 1
            self.first_error = self.first_error or traceback.format_exc(limit=3)
            return {}
        finally:
            spent = time.perf_counter() - started
            self.calls += 1
            self.seconds += spent
            self.slowest = max(self.slowest, spent)


def play(seeds: list[int], seats: dict[int, Player], opponent: str | None) -> list[float]:
    """Plays one game per seed, all stepped together. `seats` maps fighter ids to players; the
    score is fighter 1's: 1 for a win, 0.5 a draw, 0 a loss."""
    scores: list[float] = [0.0] * len(seeds)
    with Simulator(len(seeds)) as sim:
        matches, pending = [], []
        for i, seed in enumerate(seeds):
            options = {"seed": seed} | ({"opponent": opponent} if opponent else {})
            hellos, first = sim.start(i, **options)
            matches.append({f: {"id": h["match_id"], "rules": h["rules"]} for f, h in hellos.items()})
            pending.append(first)
        while any(p is not None for p in pending):
            replies = []
            for i, messages in enumerate(pending):
                if messages is None:
                    replies.append(None)
                    continue
                replies.append({f: seats[f].turn(m, matches[i][f]) for f, m in messages.items()})
            for i, messages in enumerate(sim.step(replies)):
                if messages is None:
                    continue
                end = messages.get(1)
                if end is not None and end.get("type") == "end":
                    scores[i] = {"win": 1.0, "draw": 0.5}.get(end["result"], 0.0)
                    pending[i] = None
                else:
                    pending[i] = messages
    return scores


def interval(points: float, n: int) -> tuple[float, float]:
    """Wilson score interval for a share of points, at 95%."""
    z, p = 1.96, points / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def line(label: str, scores: list[float]) -> str:
    n, points = len(scores), sum(scores)
    low, high = interval(points, n)
    wins, draws = scores.count(1.0), scores.count(0.5)
    return f"{label:<30} {points / n:7.1%}  [{low:.1%} – {high:.1%}]  {wins}W {draws}D {n - wins - draws}L"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--games", type=int, default=300)
    parser.add_argument("--against", default="ts-starter,random")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    candidate = Player("candidate", load(args.candidate, "candidate_bot"))
    baseline = Player("baseline", load(args.baseline, "baseline_bot"))
    seeds = list(range(args.seed, args.seed + args.games))
    started = time.perf_counter()
    with Simulator(1) as sim:
        print(f"Victris Arena simulator {sim.versions()['release']}, {args.games} games per line\n")

    forward = play(seeds, {1: candidate, 2: baseline}, None)
    reverse = [1 - s for s in play(seeds, {1: baseline, 2: candidate}, None)]
    print(line("candidate vs baseline", forward + reverse))
    for opponent in filter(None, args.against.split(",")):
        print()
        print(line(f"candidate vs {opponent}", play(seeds, {1: candidate}, opponent)))
        print(line(f"baseline  vs {opponent}", play(seeds, {1: baseline}, opponent)))

    print("\ndecide() time on your machine (the ladder allows 1000 ms a tick, network included):")
    for p in (candidate, baseline):
        errors = f", {p.errors} errors (idle ticks)" if p.errors else ""
        print(f"  {p.side:<9} mean {1000 * p.seconds / max(1, p.calls):.2f} ms, max {1000 * p.slowest:.1f} ms over {p.calls} calls{errors}")
        if p.first_error:
            print("    first error: " + p.first_error.strip().replace("\n", "\n    "))
    print(f"\n{time.perf_counter() - started:.1f} s")
    print("\nShip the candidate when its head-to-head interval sits above 50% and it doesn't lose ground against the others.")


if __name__ == "__main__":
    main()
