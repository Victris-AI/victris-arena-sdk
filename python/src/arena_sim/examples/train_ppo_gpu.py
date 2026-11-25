"""Train a policy with PPO in PyTorch, built for a GPU: `train_ppo`'s curriculum in minutes.

    python -m arena_sim.examples.train_ppo_gpu --out arena-gpu

The same task as `train_ppo` (the `Basic` encoding, the `damage_trade` reward, `random` then
`ts-starter`), trained much faster. It plays `FastVectorEnv` with byte grids, split over worker
processes; observations go to the device as bytes and are decoded there; the rollout and the update
stay on the device; and on a GPU each minibatch step is one replay of a CUDA graph. It runs on a CPU
too (slowly). Needs torch: a CUDA build for a GPU. A starting point to copy and change, like
`train_ppo`: the network, the reward and the curriculum are choices, not the game's.
"""

from __future__ import annotations

import argparse
import os
import time
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from arena_sim import Basic, FastVectorEnv, decode_grid

# (who to train against, who must be beaten, the share of wins that ends the stage), as in train_ppo
CURRICULUM = [
    (["random"], "random", 0.9),
    (["ts-starter", "ts-starter", "ts-starter", "random"], "ts-starter", 0.6),
]
CHANNELS, FEATURES, ACTIONS = len(Basic.CHANNELS), len(Basic.FEATURES), 17 * len(Basic.ATTACKS)


def basic_spec(size: int = 21) -> dict[str, Any]:
    """What `Basic` gives a network: the simulator's description of an encoder (`env.spec`)."""
    return {"gridShape": [CHANNELS, size, size], "gridType": "uint8", "features": FEATURES, "actions": ACTIONS}


class Net(nn.Module):
    """The grid flattened next to the numbers, two hidden layers, then the action logits and a value.
    Sized for an encoder by its `spec` (`env.spec`: the grid's shape, the numbers, the actions)."""

    def __init__(self, width: int = 256, spec: dict[str, Any] | None = None, encoder: str = "basic"):
        super().__init__()
        self.width, self.spec, self.encoder = width, spec or basic_spec(), encoder
        inputs = int(np.prod(self.spec["gridShape"])) + self.spec["features"]
        self.trunk = nn.Sequential(nn.Linear(inputs, width), nn.ReLU(), nn.Linear(width, width), nn.ReLU())
        self.pi = nn.Linear(width, self.spec["actions"])
        self.v = nn.Linear(width, 1)
        nn.init.orthogonal_(self.pi.weight, 0.01)  # start close to uniform over the legal actions
        nn.init.zeros_(self.pi.bias)

    def forward(self, grid: torch.Tensor, vec: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = self.trunk(torch.cat([grid.flatten(1), vec], 1))
        return self.pi(h), self.v(h).squeeze(1)

    def prepare(self, grid: torch.Tensor) -> torch.Tensor:
        """The grid as the network reads it: `Basic`'s byte codes decoded, another encoder's bytes as numbers."""
        if grid.dtype != torch.uint8:
            return grid
        return decode_grid(grid) if self.encoder == "basic" else grid.float()


def pick_device(device: str = "auto", workers: int = 0) -> torch.device:
    """`auto` is a GPU if torch sees one. On the CPU, torch gets the cores the simulator's workers
    leave, at most 8: with a thread per core it can run tens of times slower than with a few."""
    dev = torch.device("cuda" if device == "auto" and torch.cuda.is_available() else "cpu" if device == "auto" else device)
    if dev.type == "cpu":
        torch.set_num_threads(max(1, min(8, (os.cpu_count() or 2) - workers)))
    return dev


def masked(logits: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    return logits.float().masked_fill(~mask, -1e9)


class Policy:
    """A trained network as a batched policy: `policy(observations, action_masks) -> actions`, the
    shape `FastVectorEnv` takes for an opponent. Observations are its encoder's arrays (for `Basic`,
    the grid as floats or as bytes)."""

    def __init__(self, net: Net, device: str | torch.device = "cpu", greedy: bool = True):
        self.net, self.device, self.greedy = net.eval(), torch.device(device), greedy

    @torch.no_grad()
    def __call__(self, observations: dict[str, np.ndarray], masks: np.ndarray) -> np.ndarray:
        grid = self.net.prepare(torch.as_tensor(observations["grid"], device=self.device))
        logits, _ = self.net(grid, torch.as_tensor(observations["vec"], device=self.device))
        logits = masked(logits, torch.as_tensor(masks, device=self.device).bool())
        if not self.greedy:
            logits = logits - torch.log(-torch.log(torch.rand_like(logits).clamp_(1e-9, 1 - 1e-9)))
        return logits.argmax(1).cpu().numpy()


def save(net: Net, path: str) -> None:
    torch.save({"width": net.width, "spec": net.spec, "encoder": net.encoder, "state_dict": net.state_dict()}, path)


def load_net(path: str, device: str = "cpu") -> Net:
    saved = torch.load(path, map_location=device)
    spec = saved.get("spec") or basic_spec(saved["size"])  # saved before networks recorded their encoder
    net = Net(saved["width"], spec, saved.get("encoder", "basic")).to(device)
    net.load_state_dict(saved["state_dict"])
    return net


def load(path: str, device: str = "cpu") -> Policy:
    """A network saved by this script (or `imitate`, or `league`), as a `Policy`. On the ladder, a
    bot encodes each observation with `ScriptEncoder(<the encoder>)` (or `Basic()` for `Basic`) and
    calls it on a batch of one."""
    return Policy(load_net(path, device), device)


class Rollout:
    """`steps` ticks of every environment, kept on the device; the grid as the environment gives it."""

    def __init__(self, steps: int, envs: int, spec: dict[str, Any], device: torch.device):
        z = lambda *shape, dtype=torch.float32: torch.zeros((steps, envs, *shape), dtype=dtype, device=device)  # noqa: E731
        gtype = torch.uint8 if spec["gridType"] == "uint8" else torch.float32
        self.grid, self.vec, self.mask = z(*spec["gridShape"], dtype=gtype), z(spec["features"]), z(spec["actions"], dtype=torch.bool)
        self.act, self.logp, self.val, self.rew = z(dtype=torch.long), z(), z(), z()
        # the teacher's action (-1 for none), when the environment has a teacher
        self.teacher = z(dtype=torch.long)
        # `done[t]`: the step before t ended a match, so t restarted it and decided nothing
        self.done, self.adv, self.ret, self.valid = z(), z(), z(), z()
        self.last_val, self.last_done = torch.zeros(envs, device=device), torch.zeros(envs, device=device)


class Trainer:
    """PPO on a fast environment. Two optional pulls besides the reward: `kl` toward a fixed
    `prior` network (say, the one imitation learning gave), so early updates don't undo what it
    knew; and `teacher_weight`, imitation of the environment's teacher (`info["teacher_action"]`)
    on the states the policy itself reaches."""

    def __init__(self, env: FastVectorEnv, net: Net, steps: int, epochs: int, minibatches: int, lr: float, device: torch.device,
                 prior: Net | None = None, kl: float = 0.0, teacher_weight: float = 0.0, on_step: Any = None):
        self.env, self.net, self.steps, self.epochs, self.minibatches, self.device = env, net, steps, epochs, minibatches, device
        self.prior, self.kl, self.teacher_weight = (prior.eval() if prior is not None else None), kl, teacher_weight
        # called after every step with (terminated, info), e.g. to count results by opponent
        self.on_step = on_step
        self.cuda = device.type == "cuda"
        self.amp = dict(device_type="cuda", dtype=torch.bfloat16, enabled=self.cuda, cache_enabled=False)
        self.opt = torch.optim.Adam(net.parameters(), lr=lr, eps=1e-5, **(dict(fused=True, capturable=True) if self.cuda else {}))
        n = env.num_envs
        self.r = Rollout(steps, n, env.spec, device)
        self.size = steps * n // minibatches
        self.idx = torch.zeros(self.size, dtype=torch.long, device=device)
        self.graph: Any = None
        self.obs, self.info = env.reset(seed=0)
        self.done = torch.zeros(n, device=device)
        self.pinned: dict[str, torch.Tensor] = {}

    def _to_device(self, name: str, array: np.ndarray) -> torch.Tensor:
        """Copies an array to the device, on a GPU through page-locked memory kept for it (copies from there run asynchronously)."""
        if not self.cuda:
            return torch.from_numpy(array).to(self.device)
        if name not in self.pinned:
            self.pinned[name] = torch.empty(array.shape, dtype=torch.from_numpy(array[:0]).dtype).pin_memory()
        self.pinned[name].numpy()[:] = array
        return self.pinned[name].to(self.device, non_blocking=True)

    @torch.no_grad()
    def collect(self) -> None:
        r = self.r
        for t in range(self.steps):
            grid, vec = self._to_device("grid", self.obs["grid"]), self._to_device("vec", self.obs["vec"])
            mask = self._to_device("mask", self.info["action_mask"]).bool()
            with torch.autocast(**self.amp):
                logits, value = self.net(self.net.prepare(grid), vec)
            logits = masked(logits, mask)
            action = (logits - torch.log(-torch.log(torch.rand_like(logits).clamp_(1e-9, 1 - 1e-9)))).argmax(1)  # a sample
            r.grid[t], r.vec[t], r.mask[t], r.act[t], r.val[t], r.done[t] = grid, vec, mask, action, value.float(), self.done
            if "teacher_action" in self.info:
                r.teacher[t] = self._to_device("teacher", self.info["teacher_action"])
            r.logp[t] = F.log_softmax(logits, 1).gather(1, action[:, None]).squeeze(1)
            # reading the actions waits for this step's work, so the page-locked buffers are free again
            self.obs, reward, terminated, truncated, self.info = self.env.step(action.cpu().numpy())
            r.rew[t] = torch.from_numpy(reward).to(self.device)
            if self.on_step is not None:
                self.on_step(terminated, self.info)
            self.done = torch.from_numpy((terminated | truncated).astype(np.float32)).to(self.device)
        with torch.autocast(**self.amp):
            _, last = self.net(self.net.prepare(self._to_device("grid", self.obs["grid"])), self._to_device("vec", self.obs["vec"]))
        r.last_val.copy_(last.float())
        r.last_done.copy_(self.done)

    def _minibatch(self) -> None:
        """One PPO step on the rollout entries in `idx`; steps that only restarted a match weigh nothing."""
        r, i = self.r, self.idx
        flat = lambda x: x.flatten(0, 1)[i]  # noqa: E731
        w = flat(r.valid)
        n = w.sum().clamp(min=1.0)
        grid, vec, mask = self.net.prepare(flat(r.grid)), flat(r.vec), flat(r.mask)
        with torch.autocast(**self.amp):
            logits, value = self.net(grid, vec)
        logp_all = F.log_softmax(masked(logits, mask), 1)
        ratio = (logp_all.gather(1, flat(r.act)[:, None]).squeeze(1) - flat(r.logp)).exp()
        adv = flat(r.adv)
        mean = (adv * w).sum() / n
        adv = (adv - mean) / (((adv - mean).pow(2) * w).sum() / n).sqrt().add(1e-8)
        policy_loss = (torch.max(-adv * ratio, -adv * ratio.clamp(0.8, 1.2)) * w).sum() / n
        value_loss = 0.5 * ((value.float() - flat(r.ret)).pow(2) * w).sum() / n
        entropy = (-(logp_all.exp() * logp_all).sum(1) * w).sum() / n
        loss = policy_loss + 0.5 * value_loss - 0.01 * entropy
        if self.prior is not None and self.kl > 0:
            with torch.no_grad(), torch.autocast(**self.amp):
                prior_logits, _ = self.prior(grid, vec)
            prior_logp = F.log_softmax(masked(prior_logits, mask), 1)
            # KL(policy || prior) over the legal actions
            kl = (logp_all.exp() * (logp_all - prior_logp)).masked_fill(~mask, 0).sum(1)
            loss = loss + self.kl * (kl * w).sum() / n
        if self.teacher_weight > 0:
            label = flat(r.teacher)
            has = (label >= 0).float() * w
            nll = -logp_all.gather(1, label.clamp(min=0)[:, None]).squeeze(1)
            loss = loss + self.teacher_weight * (nll * has).sum() / has.sum().clamp(min=1.0)
        loss.backward()
        nn.utils.clip_grad_norm_(self.net.parameters(), 0.5)
        self.opt.step()
        self.opt.zero_grad(set_to_none=False)

    def update(self, gamma: float = 0.995, lam: float = 0.95) -> None:
        r = self.r
        gae = torch.zeros_like(r.last_val)
        next_val, next_done = r.last_val, r.last_done
        for t in reversed(range(self.steps)):
            going = 1.0 - next_done
            gae = r.rew[t] + gamma * next_val * going - r.val[t] + gamma * lam * going * gae
            r.adv[t] = gae
            next_val, next_done = r.val[t], r.done[t]
        torch.add(r.adv, r.val, out=r.ret)
        torch.sub(torch.ones_like(r.done), r.done, out=r.valid)
        if self.cuda and self.graph is None:
            # Warm up on a side stream (that allocates the gradients and the optimizer's state), then
            # capture one minibatch step: replaying it skips Python and the kernel launches.
            side = torch.cuda.Stream()
            side.wait_stream(torch.cuda.current_stream())
            with torch.cuda.stream(side):
                for _ in range(3):
                    self.idx.copy_(torch.randint(0, self.steps * self.env.num_envs, (self.size,), device=self.device))
                    self._minibatch()
            torch.cuda.current_stream().wait_stream(side)
            self.graph = torch.cuda.CUDAGraph()
            with torch.cuda.graph(self.graph):
                self._minibatch()
        self.net.train()
        for _ in range(self.epochs):
            order = torch.randperm(self.steps * self.env.num_envs, device=self.device)
            for k in range(self.minibatches):
                self.idx.copy_(order[k * self.size:(k + 1) * self.size])
                if self.graph is not None:
                    self.graph.replay()
                else:
                    self._minibatch()
        self.net.eval()


def win_rate(policy: Policy, env: FastVectorEnv, seed: int = 0) -> float:
    """The share of `env.num_envs` fresh matches the policy wins, playing its best action."""
    obs, info = env.reset(seed=seed)
    results = np.full(env.num_envs, 2)  # 2 until the match ends, then 1, 0 or -1
    while (results == 2).any():
        obs, _, terminated, _, info = env.step(policy(obs, info["action_mask"]))
        for i in np.flatnonzero(terminated & (results == 2)):
            results[i] = info["result"][i]
    return float((results == 1).mean())


def train(out: str, games: int = 2048, workers: int | None = None, steps: int = 16, epochs: int = 10, minibatches: int = 8,
          lr: float = 3e-4, width: int = 256, chunk: int = 500_000, max_steps: int = 50_000_000, eval_games: int = 128,
          device: str = "auto", seed: int = 0, curriculum: list = CURRICULUM) -> list[tuple[str, float]]:
    """Runs the curriculum and returns each stage's opponent and the last share of wins against it."""
    workers = workers or max(1, min(16, (os.cpu_count() or 2) - 2, games))
    dev = pick_device(device, workers)
    torch.manual_seed(seed)
    env = FastVectorEnv(games, opponent=curriculum[0][0], reward="damage_trade", workers=workers, copy=False, grid="uint8")
    net = Net(width, env.spec).to(dev)
    trainer = Trainer(env, net, steps, epochs, minibatches, lr, dev)
    policy = Policy(net, dev)
    reached = []
    trained, start = 0, time.time()
    try:
        for opponents, target, goal in curriculum:
            env.set_opponents(opponents)
            evaluator = FastVectorEnv(eval_games, opponent=target, grid="uint8", workers=min(2, workers, eval_games))
            stage, rate = 0, 0.0
            while stage < max_steps:
                done_at = stage + chunk
                while stage < done_at:
                    trainer.collect()
                    trainer.update()
                    stage += steps * env.num_envs
                rate = win_rate(policy, evaluator, seed=trained + stage)
                print(f"{trained + stage:>11,} steps  {time.time() - start:6.0f}s  wins {rate:4.0%} against {target}", flush=True)
                if rate >= goal:
                    break
            evaluator.close()
            trained += stage
            reached.append((target, rate))
            save(net, out + ".pt")
            if rate < goal:
                print(f"stopped: {rate:.0%} against {target} after {stage:,} steps, short of {goal:.0%}")
                break
    finally:
        env.close()
    print(f"saved {out}.pt ({dev})")
    return reached


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default="arena-gpu", help="where to save the network (.pt is added)")
    parser.add_argument("--games", type=int, default=2048, help="matches played at once")
    parser.add_argument("--workers", type=int, default=None, help="simulator processes (default: most of the cores, up to 16)")
    parser.add_argument("--steps", type=int, default=16, help="ticks of every match per update")
    parser.add_argument("--epochs", type=int, default=10, help="passes over each rollout")
    parser.add_argument("--minibatches", type=int, default=8, help="minibatches per pass")
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--width", type=int, default=256, help="units in each hidden layer")
    parser.add_argument("--chunk", type=int, default=500_000, help="training steps between evaluations")
    parser.add_argument("--max-steps", type=int, default=50_000_000, help="training steps a stage may take")
    parser.add_argument("--eval-games", type=int, default=128, help="matches played to measure the share of wins")
    parser.add_argument("--device", default="auto", help="auto (a GPU if torch sees one), cpu or cuda")
    parser.add_argument("--seed", type=int, default=0)
    a = parser.parse_args()
    train(a.out, a.games, a.workers, a.steps, a.epochs, a.minibatches, a.lr, a.width, a.chunk, a.max_steps, a.eval_games, a.device, a.seed)


if __name__ == "__main__":
    main()
