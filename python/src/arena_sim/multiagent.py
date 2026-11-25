"""Self-play as a PettingZoo parallel environment: both fighters are agents, acting at once.

Needs the `pettingzoo` extra (pip install "victris-arena-sim[pettingzoo]").
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np
from pettingzoo import ParallelEnv

from ._core import Simulator
from .encoding import Encoder, Raw, win_loss
from .envs import Reward

AGENTS = ["fighter_1", "fighter_2"]


class ArenaParallelEnv(ParallelEnv):
    """One self-play match an episode. Agents are "fighter_1" and "fighter_2"; observations,
    actions, rewards and infos are keyed by agent, as in `ArenaEnv` for each fighter."""

    metadata = {"name": "arena_v0", "render_modes": []}

    def __init__(self, encoder: Encoder | None = None, reward: Reward = win_loss, map: str | None = None,
                 source: str | os.PathLike[str] | None = None):
        self.encoder = encoder or Raw()
        self.reward = reward
        self.map = map
        self.possible_agents = list(AGENTS)
        self.agents: list[str] = []
        self._sim = Simulator(1, source)
        self._rng = np.random.default_rng()
        self._hello: dict[int, dict] = {}
        self._obs: dict[int, dict] = {}

    def observation_space(self, agent: str) -> Any:
        return self.encoder.observation_space

    def action_space(self, agent: str) -> Any:
        return self.encoder.action_space

    def _info(self, fid: int, **extra: Any) -> dict[str, Any]:
        info: dict[str, Any] = {"observation": self._obs[fid], **extra}
        mask = self.encoder.action_mask(self._obs[fid], self._hello[fid])
        if mask is not None:
            info["action_mask"] = mask
        return info

    def _encoded(self) -> dict[str, Any]:
        return {a: self.encoder.encode(self._obs[i + 1], self._hello[i + 1]) for i, a in enumerate(AGENTS)}

    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        game_seed = int(self._rng.integers(0, 2**31))
        self._hello, self._obs = self._sim.start(0, seed=game_seed, **({"map": self.map} if self.map else {}))
        self.agents = list(AGENTS)
        return self._encoded(), {a: self._info(i + 1, seed=game_seed) for i, a in enumerate(AGENTS)}

    def step(self, actions: dict[str, Any]) -> tuple[dict, dict, dict, dict, dict]:
        replies = {i + 1: self.encoder.decode(actions[a], self._obs[i + 1], self._hello[i + 1]) for i, a in enumerate(AGENTS) if a in actions}
        msgs = self._sim.step([replies])[0]
        assert msgs is not None
        rewards = {a: self.reward(self._obs[i + 1], msgs[i + 1]) for i, a in enumerate(AGENTS)}
        over = msgs[1]["type"] == "end"
        if not over:
            self._obs = msgs
        obs = self._encoded()
        infos = {a: self._info(i + 1, **({"end": msgs[i + 1]} if over else {})) for i, a in enumerate(AGENTS)}
        done = {a: over for a in AGENTS}
        if over:
            self.agents = []
        return obs, rewards, done, {a: False for a in AGENTS}, infos

    def close(self) -> None:
        self._sim.close()
