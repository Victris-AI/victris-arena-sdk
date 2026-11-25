"""Learn a policy from the ladder's games: imitate the strongest bots, then play it in the simulator.

    python -m arena_sim.examples.imitate --ladder http://127.0.0.1:7777 --min-rating 1800 --out arena-bc

Every ladder match is public, with its replay. This downloads the recent matches of the bots rated
at least `--min-rating` (keeping the replays in `--cache`, so a second run fetches only new ones),
turns each strong bot's every tick into what your encoder reads and the action closest to what the
bot did (`replay_dataset`), and trains `train_ppo_gpu`'s network to predict that action (behaviour
cloning). It holds a tenth of the matches out to measure how often the network agrees with the bots
on games it never saw, then plays it against the house bots in the simulator.

The network it saves is the same kind `train_ppo_gpu` makes, so `train_ppo_gpu.load()` plays it,
and `league --init` goes on from it with reinforcement learning. Imitation alone copies the
experts on the states they reached; on states they never did, it can fall apart. A teacher you
can run (a bot of yours, `--teacher` in `league`) and reinforcement learning are the next steps.
With `--encoder` and `--scripts` it learns through an encoder of yours (see the simulator guide).
"""

from __future__ import annotations

import argparse
import os
import time

import numpy as np
import torch
import torch.nn.functional as F

from arena_sim import FastVectorEnv, download_replays, replay_dataset
from arena_sim.examples.train_ppo_gpu import Net, Policy, masked, pick_device, save, win_rate


def dataset(ladder: str, min_rating: float, limit: int, cache: str, encoder: str, scripts: list[str], bot: str | None = None) -> dict:
    """The strong bots' ticks from the ladder's recent matches, through the encoder."""
    pairs = list(download_replays(ladder, bot=bot, limit=limit, min_rating=min_rating, cache=cache))
    strong = [set(m["strong"]) for m, _ in pairs]
    data = replay_dataset(pairs, encoder, scripts, fighters=None, grid="uint8")
    # rows of the strong bots only, with an action to learn
    keep = np.array([f in strong[m] for m, f in zip(data["match"], data["fighter"])], dtype=bool) & (data["action"] >= 0)
    print(f"{len(pairs)} matches ({len(data['skipped'])} from another release, skipped), {int(keep.sum()):,} ticks to learn from", flush=True)
    return {k: v[keep] for k, v in data.items() if k != "skipped"}


def train(data: dict, spec: dict, encoder: str, width: int, epochs: int, batch: int, lr: float, device: torch.device, seed: int) -> Net:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    matches = np.unique(data["match"])
    held = set(rng.choice(matches, max(1, len(matches) // 10), replace=False).tolist()) if len(matches) > 1 else set()
    test = np.isin(data["match"], list(held))
    tensors = {k: torch.as_tensor(data[k]).to(device) for k in ("grid", "vec", "mask", "action")}
    net = Net(width, spec, encoder).to(device)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    train_rows, test_rows = np.flatnonzero(~test), np.flatnonzero(test)

    def logits_of(rows: torch.Tensor) -> torch.Tensor:
        logits, _ = net(net.prepare(tensors["grid"][rows]), tensors["vec"][rows])
        return masked(logits, tensors["mask"][rows].bool())

    for epoch in range(epochs):
        net.train()
        order = torch.as_tensor(rng.permutation(train_rows), device=device)
        for k in range(0, len(order), batch):
            rows = order[k:k + batch]
            loss = F.cross_entropy(logits_of(rows), tensors["action"][rows].long())
            opt.zero_grad()
            loss.backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            agree = [(logits_of(rows).argmax(1) == tensors["action"][rows]).float().sum().item()
                     for rows in torch.as_tensor(test_rows, device=device).split(batch)]
        print(f"epoch {epoch + 1}: last loss {loss.item():.3f}, agrees with the bots on {sum(agree) / max(1, len(test_rows)):.1%} of held-out ticks", flush=True)
    return net


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ladder", default="http://127.0.0.1:7777", help="the ladder to learn from")
    parser.add_argument("--min-rating", type=float, default=1800, help="imitate the bots rated at least this")
    parser.add_argument("--bot", default=None, help="imitate this bot only (still rated at least --min-rating)")
    parser.add_argument("--limit", type=int, default=200, help="recent matches per bot")
    parser.add_argument("--cache", default="replays", help="where to keep downloaded replays")
    parser.add_argument("--encoder", default="basic", help="the simulator's encoder: basic, or one a script registers")
    parser.add_argument("--scripts", nargs="*", default=[], help="JavaScript files that register your encoder")
    parser.add_argument("--out", default="arena-bc", help="where to save the network (.pt is added)")
    parser.add_argument("--width", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch", type=int, default=4096)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--device", default="auto", help="auto (a GPU if torch sees one), cpu or cuda")
    parser.add_argument("--eval-games", type=int, default=128)
    parser.add_argument("--seed", type=int, default=0)
    a = parser.parse_args()
    dev = pick_device(a.device)
    start = time.time()
    data = dataset(a.ladder, a.min_rating, a.limit, a.cache, a.encoder, a.scripts, a.bot)
    if len(data["action"]) == 0:
        raise SystemExit("nothing to learn from: lower --min-rating, or check --ladder")
    env = FastVectorEnv(1, encoder=a.encoder, scripts=a.scripts, grid="uint8")
    spec = env.spec
    env.close()
    net = train(data, spec, a.encoder, a.width, a.epochs, a.batch, a.lr, dev, a.seed)
    save(net, a.out + ".pt")
    print(f"saved {a.out}.pt ({time.time() - start:.0f}s)")
    policy = Policy(net, dev)
    for house in ("random", "ts-starter", "ts-starter"):
        evaluator = FastVectorEnv(a.eval_games, opponent=house, encoder=a.encoder, scripts=a.scripts, grid="uint8", workers=min(4, os.cpu_count() or 1))
        print(f"wins {win_rate(policy, evaluator):.0%} against {house}", flush=True)
        evaluator.close()


if __name__ == "__main__":
    main()
