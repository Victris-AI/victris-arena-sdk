"""Train against a league: bots, frozen copies of yourself, and yourself, weighted toward whoever beats you.

    python -m arena_sim.examples.league --init arena-bc.pt --out league --bots random ts-starter --minutes 30

A policy trained against one opponent learns to beat that opponent. This plays every match against
one drawn from a pool: bots by name (Random, the starter, or yours, from `--scripts`), the network you
started from, frozen copies of the learner taken as it improves, and the learner itself. Opponents
it still loses to are drawn more often (the weight of each is (1 - its share of wins)², from recent
results), so training goes where the policy is weak instead of farming what it already beats.

It is `train_ppo_gpu`'s PPO with two optional pulls: `--kl`, toward the network you started from
(after imitation, say), so early updates don't throw away what it knew; and `--teacher`, a bot whose
turn on every state the learner reaches is imitated alongside the reward (a bot of yours from
`--scripts`, or a house bot). Every `--eval-every` steps it plays each named bot and saves
`<out>/last.pt`; `<out>/best.pt` is the one with the best worst-case share of wins.

A starting point to copy and change: the pool, the weighting and the losses are choices, not the
game's. With `--encoder` and `--scripts` it trains through an encoder of yours.
"""

from __future__ import annotations

import argparse
import copy
import os
import time
from typing import Any

import numpy as np
import torch

from arena_sim import FastVectorEnv
from arena_sim.examples.train_ppo_gpu import Net, Policy, Trainer, load_net, pick_device, save, win_rate


class Entry:
    """An opponent in the pool and its recent results against the learner (decayed, so old games fade)."""

    def __init__(self, name: str, opponent: Any):
        self.name, self.opponent, self.wins, self.games = name, opponent, 0.0, 0.0

    def rate(self) -> float:
        return (self.wins + 1) / (self.games + 2)  # the learner's share of wins, a little toward even

    def weight(self) -> float:
        return (1 - self.rate()) ** 2 + 0.02


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--init", default=None, help="a network to start from (imitate's, train_ppo_gpu's or league's)")
    parser.add_argument("--out", default="league", help="a directory for the networks")
    parser.add_argument("--bots", nargs="*", default=["random", "ts-starter"], help="bots in the pool, by name")
    parser.add_argument("--scripts", nargs="*", default=[], help="JavaScript files that register your bots and encoder")
    parser.add_argument("--encoder", default="basic", help="the simulator's encoder: basic, or one a script registers")
    parser.add_argument("--self-play", type=float, default=0.2, help="share of matches against the learner itself")
    parser.add_argument("--snapshot-every", type=int, default=2_000_000, help="steps between frozen copies of the learner")
    parser.add_argument("--max-snapshots", type=int, default=8, help="frozen copies kept in the pool (oldest go first)")
    parser.add_argument("--kl", type=float, default=0.0, help="pull toward the --init network")
    parser.add_argument("--teacher", default=None, help="a bot whose turns the learner imitates as it plays")
    parser.add_argument("--teacher-weight", type=float, default=0.5)
    parser.add_argument("--games", type=int, default=2048)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--steps", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--minibatches", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--width", type=int, default=256, help="units in each hidden layer, without --init")
    parser.add_argument("--eval-every", type=int, default=2_000_000)
    parser.add_argument("--eval-games", type=int, default=128)
    parser.add_argument("--minutes", type=float, default=30)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--seed", type=int, default=0)
    a = parser.parse_args()

    workers = a.workers or max(1, min(16, (os.cpu_count() or 2) - 2, a.games))
    dev = pick_device(a.device, workers)
    torch.manual_seed(a.seed)
    rng = np.random.default_rng(a.seed)
    os.makedirs(a.out, exist_ok=True)
    env = FastVectorEnv(a.games, opponent=a.bots[0] if a.bots else "random", reward="damage_trade", encoder=a.encoder, scripts=a.scripts,
                        teacher=a.teacher, workers=workers, copy=False, grid="uint8")
    net = load_net(a.init, str(dev)) if a.init else Net(a.width, env.spec, a.encoder).to(dev)
    if net.spec["gridShape"] != env.spec["gridShape"] or net.spec["actions"] != env.spec["actions"]:
        raise SystemExit(f"{a.init} was trained with another encoder than {a.encoder}")
    start_net = copy.deepcopy(net).eval()
    pool = [Entry(name, name) for name in a.bots]
    if a.init:
        pool.append(Entry("init", Policy(start_net, dev, greedy=False)))
    learner = Entry("self", Policy(net, dev, greedy=False))
    by_opponent = {id(e.opponent): e for e in [*pool, learner]}

    def count(terminated: np.ndarray, info: dict) -> None:
        playing = env.playing
        for g in np.flatnonzero(terminated):
            e = by_opponent.get(id(playing[g]))
            if e is not None:
                e.games += 1
                e.wins += 1.0 if info["result"][g] == 1 else 0.5 if info["result"][g] == 0 else 0.0

    trainer = Trainer(env, net, a.steps, a.epochs, a.minibatches, a.lr, dev, prior=start_net if a.kl > 0 else None, kl=a.kl,
                      teacher_weight=a.teacher_weight if a.teacher else 0.0, on_step=count)

    def draw() -> None:
        """Assigns the next matches' opponents: self-play's share, the rest by the pool's weights."""
        weights = np.array([e.weight() for e in pool])
        picks = rng.choice(len(pool), a.games, p=weights / weights.sum()) if pool else np.zeros(a.games, int)
        ops = [learner.opponent if (not pool or rng.random() < a.self_play) else pool[i].opponent for i in picks]
        env.set_opponents(ops)
        for e in [*pool, learner]:
            e.wins, e.games = e.wins * 0.98, e.games * 0.98

    evaluators = {name: FastVectorEnv(a.eval_games, opponent=name, encoder=a.encoder, scripts=a.scripts, grid="uint8", workers=min(2, workers))
                  for name in a.bots}
    greedy = Policy(net, dev)
    trained, snapshots, best, start = 0, 0, -1.0, time.time()
    next_snapshot, next_eval = a.snapshot_every, a.eval_every
    try:
        while time.time() - start < a.minutes * 60:
            draw()
            trainer.collect()
            trainer.update()
            trained += a.steps * env.num_envs
            if trained >= next_snapshot:
                next_snapshot += a.snapshot_every
                snapshots += 1
                frozen = Entry(f"snapshot-{snapshots}", Policy(copy.deepcopy(net).eval(), dev, greedy=False))
                pool.append(frozen)
                by_opponent[id(frozen.opponent)] = frozen
                old = [e for e in pool if e.name.startswith("snapshot-")]
                if len(old) > a.max_snapshots:
                    pool.remove(old[0])
            if trained >= next_eval:
                next_eval += a.eval_every
                rates = {name: win_rate(greedy, ev, seed=trained) for name, ev in evaluators.items()}
                pool_line = "  ".join(f"{e.name} {e.rate():.0%}" for e in pool)
                print(f"{trained:>12,} steps {time.time() - start:6.0f}s  wins: " + "  ".join(f"{n} {r:.0%}" for n, r in rates.items())
                      + f"  | in training: {pool_line}", flush=True)
                save(net, os.path.join(a.out, "last.pt"))
                worst = min(rates.values()) if rates else 0.0
                if worst > best:
                    best = worst
                    save(net, os.path.join(a.out, "best.pt"))
    finally:
        env.close()
        for ev in evaluators.values():
            ev.close()
    save(net, os.path.join(a.out, "last.pt"))
    print(f"saved {a.out}/last.pt after {trained:,} steps")


if __name__ == "__main__":
    main()
