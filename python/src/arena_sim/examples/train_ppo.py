"""Train a policy with PPO that beats the house bots: first `random`, then `ts-starter`.

    python -m arena_sim.examples.train_ppo --out arena-ppo

Needs the `sb3` extra. It is a starting point to copy and change: the encoder (`Basic`, computed in
the simulator by `FastVectorEnv`), the reward (`damage_trade`), the network and the curriculum are
all choices, not the game's. Each stage trains
against its opponents until the policy wins often enough against the stage's target, measured by
playing fresh matches, then the next stage starts from what it learned.
"""

from __future__ import annotations

import argparse
import time

import numpy as np
from gymnasium.vector import AutoresetMode
from sb3_contrib import MaskablePPO

from arena_sim import FastVectorEnv
from arena_sim.sb3 import ArenaVecEnv

# (who to train against, who must be beaten, the share of wins that ends the stage)
CURRICULUM = [
    (["random"], "random", 0.9),
    # Keep some easy games, so the first lesson isn't forgotten.
    (["ts-starter", "ts-starter", "ts-starter", "random"], "ts-starter", 0.6),
]


def win_rate(model: MaskablePPO, opponent: str, games: int = 64, seed: int = 0) -> float:
    """The share of `games` fresh matches against `opponent` that the policy wins, playing its best action."""
    env = FastVectorEnv(games, opponent=opponent)
    obs, info = env.reset(seed=seed)
    results: list[int | None] = [None] * games
    while None in results:
        actions, _ = model.predict(obs, action_masks=info["action_mask"].astype(bool), deterministic=True)
        obs, _, terminated, _, info = env.step(actions)
        for i in np.flatnonzero(terminated):
            results[i] = int(info["result"][i]) if results[i] is None else results[i]
    env.close()
    return results.count(1) / games


def train(out: str, envs: int = 64, chunk: int = 100_000, max_steps: int = 10_000_000, eval_games: int = 64,
          device: str = "auto", seed: int = 0, curriculum: list = CURRICULUM) -> list[tuple[str, float]]:
    """Runs the curriculum and returns each stage's opponent and the last share of wins against it."""
    env = ArenaVecEnv(FastVectorEnv(envs, opponent=curriculum[0][0], reward="damage_trade", autoreset_mode=AutoresetMode.SAME_STEP))
    env.seed(seed)
    model = MaskablePPO("MultiInputPolicy", env, n_steps=128, batch_size=2048, learning_rate=3e-4, ent_coef=0.01,
                        gamma=0.995, seed=seed, device=device, verbose=0)
    reached = []
    start = time.time()
    for opponents, target, goal in curriculum:
        env.env.set_opponents(opponents)
        trained, rate = 0, 0.0
        while trained < max_steps:
            model.learn(chunk, reset_num_timesteps=False)
            trained += chunk
            rate = win_rate(model, target, games=eval_games, seed=model.num_timesteps)
            print(f"{model.num_timesteps:>9,} steps  {time.time() - start:6.0f}s  wins {rate:4.0%} against {target}", flush=True)
            if rate >= goal:
                break
        reached.append((target, rate))
        model.save(out)
        if rate < goal:
            print(f"stopped: {rate:.0%} against {target} after {trained:,} steps, short of {goal:.0%}")
            break
    print(f"saved {out}.zip ({model.device})")
    return reached


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default="arena-ppo", help="where to save the model (.zip is added)")
    parser.add_argument("--envs", type=int, default=64, help="matches played at once")
    parser.add_argument("--chunk", type=int, default=100_000, help="training steps between evaluations")
    parser.add_argument("--max-steps", type=int, default=10_000_000, help="training steps a stage may take")
    parser.add_argument("--eval-games", type=int, default=64, help="matches played to measure the share of wins")
    parser.add_argument("--device", default="auto", help="where the network runs: auto (a GPU if torch sees one), cpu or cuda")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    train(args.out, args.envs, args.chunk, args.max_steps, args.eval_games, args.device, args.seed)


if __name__ == "__main__":
    main()
