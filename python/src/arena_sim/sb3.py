"""Stable-Baselines3: the batched environments as an SB3 VecEnv, with action masks for
sb3-contrib's MaskablePPO. Needs the `sb3` extra.

    from gymnasium.vector import AutoresetMode
    from sb3_contrib import MaskablePPO
    from arena_sim import ArenaVectorEnv, Basic
    from arena_sim.sb3 import ArenaVecEnv

    env = ArenaVecEnv(ArenaVectorEnv(64, opponent=["ts-starter"], encoder=Basic(), autoreset_mode=AutoresetMode.SAME_STEP))
    model = MaskablePPO("MultiInputPolicy", env).learn(1_000_000)
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from gymnasium.vector import AutoresetMode
from stable_baselines3.common.vec_env import VecEnv
from stable_baselines3.common.vec_env.base_vec_env import VecEnvIndices, VecEnvObs, VecEnvStepReturn

from .envs import _Seats
from .fast import _FastSeats


class ArenaVecEnv(VecEnv):
    """An `ArenaVectorEnv`, `ArenaSelfPlayEnv` or one of the fast environments as an SB3 VecEnv,
    every environment stepped in one call. SB3 restarts an episode on the step that ends it, so make
    the environment with `autoreset_mode=AutoresetMode.SAME_STEP`. A finished episode's info has its
    `terminal_observation` and the `end` message (from a fast environment, its `result`: 1, -1 or 0);
    `env_method("action_masks")`, which MaskablePPO calls, gives the encoder's masks.
    """

    def __init__(self, env: _Seats | _FastSeats):
        if env.metadata.get("autoreset_mode") != AutoresetMode.SAME_STEP:
            raise ValueError("SB3 restarts an episode on the step that ends it: make the environment with autoreset_mode=AutoresetMode.SAME_STEP")
        self.env = env
        super().__init__(env.num_envs, env.single_observation_space, env.single_action_space)
        self._actions: Any = None
        self._masks: np.ndarray | None = None

    def reset(self) -> VecEnvObs:
        # SB3's seed() gives each environment its own seed; one seed drives every match here.
        seed = self._seeds[0] if self._seeds and self._seeds[0] is not None else None
        obs, infos = self.env.reset(seed=seed)
        self._reset_seeds()
        self._masks = infos.get("action_mask")
        self.reset_infos = [{} for _ in range(self.num_envs)]
        return obs

    def step_async(self, actions: np.ndarray) -> None:
        self._actions = actions

    def step_wait(self) -> VecEnvStepReturn:
        obs, rewards, terminated, truncated, infos = self.env.step(self._actions)
        self._masks = infos.get("action_mask")
        dones = terminated | truncated
        out: list[dict[str, Any]] = [{} for _ in range(self.num_envs)]
        for i in np.flatnonzero(dones):
            ending = {"end": infos["end"][i]} if "end" in infos else {"result": int(infos["result"][i])}
            out[i] = {"terminal_observation": infos["final_obs"][i], **ending, "TimeLimit.truncated": bool(truncated[i] and not terminated[i])}
        return obs, rewards.astype(np.float32), dones, out

    def env_method(self, method_name: str, *method_args: Any, indices: VecEnvIndices = None, **method_kwargs: Any) -> list[Any]:
        if method_name != "action_masks":
            raise AttributeError(f"ArenaVecEnv's environments have no method {method_name!r} (only action_masks)")
        if self._masks is None:
            raise AttributeError("the encoder has no action masks")
        return [self._masks[i].astype(bool) for i in self._get_indices(indices)]

    def has_attr(self, attr_name: str) -> bool:
        # MaskablePPO asks before it calls env_method("action_masks").
        return (attr_name == "action_masks" and self._masks is not None) or hasattr(self.env, attr_name)

    def get_attr(self, attr_name: str, indices: VecEnvIndices = None) -> list[Any]:
        value = getattr(self.env, attr_name)
        return [value for _ in self._get_indices(indices)]

    def set_attr(self, attr_name: str, value: Any, indices: VecEnvIndices = None) -> None:
        setattr(self.env, attr_name, value)

    def env_is_wrapped(self, wrapper_class: type, indices: VecEnvIndices = None) -> list[bool]:
        return [False for _ in self._get_indices(indices)]

    def close(self) -> None:
        self.env.close()

    def get_images(self) -> Sequence[np.ndarray | None]:
        return [None for _ in range(self.num_envs)]
