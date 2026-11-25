"""Gymnasium environments: one match an episode.

`ArenaEnv` is a standard single environment against a house bot. `ArenaVectorEnv` (against house
bots, your own policies or scripted bots) and `ArenaSelfPlayEnv` (both fighters yours) run many
matches in one simulator and step them in one call, which is what makes the simulator fast from
Python: a call into V8 costs several ticks' worth of time, so one call per environment per tick
wastes most of it.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from typing import Any

import gymnasium
import numpy as np
from gymnasium.vector import AutoresetMode, VectorEnv
from gymnasium.vector.utils import batch_space, concatenate, create_empty_array

from ._core import Simulator
from .encoding import Encoder, MessageSpace, Raw, win_loss

Reward = Callable[[dict, dict], float]
"""(the observation acted on, the message that came back: the next observation or `end`) -> reward"""


def _game_options(opponent: str, map: str | None) -> dict[str, Any]:
    return {"opponent": opponent, **({"map": map} if map else {})}


class ArenaEnv(gymnasium.Env):
    """One match an episode, as fighter 1 against a house bot ("ts-starter" or "random").

    Each reset draws the match's seed from the environment's random generator, so
    `reset(seed=s)` makes the episodes that follow reproducible; `info["seed"]` is the match's
    seed. `info["observation"]` is the observation as the ladder sends it, `info["action_mask"]`
    the encoder's mask (if it has one), and at the end `info["end"]` is the `end` message.
    When the match ends the returned observation is the last one acted on.
    """

    metadata = {"render_modes": []}

    def __init__(self, opponent: str = "ts-starter", encoder: Encoder | None = None, reward: Reward = win_loss,
                 map: str | None = None, source: str | os.PathLike[str] | None = None):
        self.opponent = opponent
        self.map = map
        self.encoder = encoder or Raw()
        self.reward = reward
        self.observation_space = self.encoder.observation_space
        self.action_space = self.encoder.action_space
        self._sim = Simulator(1, source)  # V8 starts on the first reset
        self._hello: dict = {}
        self._obs: dict = {}

    def _info(self, **extra: Any) -> dict[str, Any]:
        info: dict[str, Any] = {"observation": self._obs, **extra}
        mask = self.encoder.action_mask(self._obs, self._hello)
        if mask is not None:
            info["action_mask"] = mask
        return info

    def action_masks(self) -> np.ndarray | None:
        """The current action mask, the method sb3-contrib's MaskablePPO looks for (also in `info["action_mask"]`)."""
        mask = self.encoder.action_mask(self._obs, self._hello)
        return None if mask is None else mask.astype(bool)

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
        super().reset(seed=seed)
        game_seed = int(self.np_random.integers(0, 2**31))
        hello, first = self._sim.start(0, seed=game_seed, **_game_options(self.opponent, self.map))
        self._hello, self._obs = hello[1], first[1]
        return self.encoder.encode(self._obs, self._hello), self._info(seed=game_seed)

    def step(self, action: Any) -> tuple[Any, float, bool, bool, dict[str, Any]]:
        turn = self.encoder.decode(action, self._obs, self._hello)
        msg = self._sim.step([{1: turn}])[0][1]  # type: ignore[index]
        reward = self.reward(self._obs, msg)
        if msg["type"] == "end":
            return self.encoder.encode(self._obs, self._hello), reward, True, False, self._info(end=msg)
        self._obs = msg
        return self.encoder.encode(self._obs, self._hello), reward, False, False, self._info()

    def close(self) -> None:
        self._sim.close()


def _objects(values: list[Any]) -> np.ndarray:
    """A 1-D object array, one entry per environment (np.array would merge equal-shaped arrays into one)."""
    out = np.empty(len(values), dtype=object)
    for i, v in enumerate(values):
        out[i] = v
    return out


class ScriptedOpponent:
    """A bot written in Python, as on the ladder, to play against or (in the fast environments) to
    learn from as a teacher. Give it `decide(observation, hello)`, which gets the ladder's JSON
    observation and the match's hello and returns a turn dict; or `start(hello)`, called when each
    match starts, which returns that match's `decide(observation)`, keeping per-match state in it.
    It runs per game, in Python. With worker processes it is sent to each of them, so `decide` or
    `start` must be a function defined at the top level of a module."""

    def __init__(self, decide: Callable[[dict, dict], dict] | None = None, start: Callable[[dict], Callable[[dict], dict]] | None = None):
        if (decide is None) == (start is None):
            raise ValueError("a ScriptedOpponent takes decide(observation, hello) or start(hello), one of them")
        self.decide_fn, self.start = decide, start
        self._matches: dict[Any, tuple[dict, Callable[[dict], dict]]] = {}

    def __getstate__(self) -> dict[str, Any]:
        return {"decide_fn": self.decide_fn, "start": self.start}

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__init__(state["decide_fn"], state["start"])

    def decide(self, observation: dict, hello: dict, seat: Any = None) -> dict:
        """Its turn for `observation`. `seat` (any key) tells apart the matches it plays at once,
        for `start`: a new hello for a seat starts a new match there."""
        if self.start is None:
            return self.decide_fn(observation, hello)
        current = self._matches.get(seat)
        if current is None or current[0] is not hello:
            current = self._matches[seat] = (hello, self.start(hello))
        return current[1](observation)


Policy = Callable[[Any, "np.ndarray | None"], Any]
"""A batched policy: (observations, action masks or None) -> actions, in the encoder's spaces. Called
once per step with every game it plays, e.g. a frozen copy of your network."""


class _Seats(VectorEnv):
    """Matches stepped together in one call, each environment one seat (a game and a fighter).

    A match that ends restarts on the next step by default (Gymnasium's next-step autoreset): that
    step ignores its seats' actions and returns the new match's first observations with a reward of
    0. With `autoreset_mode=AutoresetMode.SAME_STEP` it restarts on the step that ended it, which
    returns the new match's first observations and puts the last ones in `info["final_obs"]` (what
    Stable-Baselines3 expects). Infos carry `seed` (the match's), `action_mask` (if the encoder has
    one), and `end` (the `end` message) for seats whose match just ended.
    """

    def __init__(self, num_games: int, seats: list[tuple[int, int]], encoder: Encoder | None, reward: Reward,
                 map: str | None, source: str | os.PathLike[str] | None, autoreset_mode: AutoresetMode = AutoresetMode.NEXT_STEP):
        if autoreset_mode not in (AutoresetMode.NEXT_STEP, AutoresetMode.SAME_STEP):
            raise ValueError("autoreset_mode is AutoresetMode.NEXT_STEP or AutoresetMode.SAME_STEP")
        self.metadata = {"autoreset_mode": autoreset_mode}
        if encoder is None or isinstance(encoder.observation_space, MessageSpace):
            raise ValueError(f"{type(self).__name__} needs an encoder with array spaces, such as arena_sim.Basic()")
        self.num_games = num_games
        self.num_envs = len(seats)
        self._seats = seats
        self.map = map
        self.encoder = encoder
        self.reward = reward
        self.single_observation_space = encoder.observation_space
        self.single_action_space = encoder.action_space
        self.observation_space = batch_space(self.single_observation_space, self.num_envs)
        self.action_space = batch_space(self.single_action_space, self.num_envs)
        self._sim = Simulator(num_games, source)
        self._hello: list[dict[int, dict]] = [{} for _ in range(num_games)]
        self._obs: list[dict[int, dict]] = [{} for _ in range(num_games)]
        self._done = np.zeros(num_games, dtype=bool)
        self._seeds = np.zeros(num_games, dtype=np.int64)
        self._rng = np.random.default_rng()

    def _options(self, g: int) -> dict[str, Any]:
        """Game g's options besides seed and map, decided as it starts."""
        return {}

    def _other_replies(self, games: list[int]) -> dict[int, dict[int, Any]]:
        """Replies for the seats of these running games that the environment plays itself."""
        return {}

    def _start(self, g: int) -> None:
        self._seeds[g] = int(self._rng.integers(0, 2**31))
        options = {"seed": int(self._seeds[g]), **self._options(g), **({"map": self.map} if self.map else {})}
        self._hello[g], self._obs[g] = self._sim.start(g, **options)
        self._done[g] = False

    def _encode(self, seats: list[tuple[int, int]]) -> Any:
        encoded = [self.encoder.encode(self._obs[g][f], self._hello[g][f]) for g, f in seats]
        return concatenate(self.single_observation_space, encoded, create_empty_array(self.single_observation_space, len(seats)))

    def _masks(self, seats: list[tuple[int, int]]) -> np.ndarray | None:
        masks = [self.encoder.action_mask(self._obs[g][f], self._hello[g][f]) for g, f in seats]
        return None if not masks or masks[0] is None else np.stack(masks)  # type: ignore[arg-type]

    def _infos(self, ended: dict[int, dict[int, dict]] | None = None) -> dict[str, Any]:
        everywhere = np.ones(self.num_envs, dtype=bool)
        infos: dict[str, Any] = {"seed": self._seeds[[g for g, _ in self._seats]], "_seed": everywhere}
        masks = self._masks(self._seats)
        if masks is not None:
            infos["action_mask"], infos["_action_mask"] = masks, everywhere
        if ended:
            infos["end"] = _objects([ended[g][f] if g in ended else None for g, f in self._seats])
            infos["_end"] = np.array([g in ended for g, _ in self._seats])
        return infos

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        for g in range(self.num_games):
            self._start(g)
        return self._encode(self._seats), self._infos()

    def step(self, actions: Any) -> tuple[Any, np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
        restart = self._done.copy()
        replies: list[dict[int, Any] | None] = [None if restart[g] else {} for g in range(self.num_games)]
        for i, (g, f) in enumerate(self._seats):
            if not restart[g]:
                replies[g][f] = self.encoder.decode(actions[i], self._obs[g][f], self._hello[g][f])  # type: ignore[index]
        for g, r in self._other_replies([g for g in range(self.num_games) if not restart[g]]).items():
            replies[g].update(r)  # type: ignore[union-attr]
        acted_on = list(self._obs)
        results = self._sim.step(replies)
        ended: dict[int, dict[int, dict]] = {}
        for g, msgs in enumerate(results):
            if msgs is None:
                continue
            if next(iter(msgs.values()))["type"] == "end":  # every player hears the end on the same tick
                ended[g] = msgs
                self._done[g] = True
            else:
                self._obs[g] = msgs
        rewards = np.array([0.0 if results[g] is None else self.reward(acted_on[g][f], results[g][f]) for g, f in self._seats])
        final: list[Any] = []
        if ended and self.metadata["autoreset_mode"] == AutoresetMode.SAME_STEP:
            # The last observations acted on, then the next matches start at once.
            final = [self.encoder.encode(self._obs[g][f], self._hello[g][f]) if g in ended else None for g, f in self._seats]
            restart[list(ended)] = True
        for g in np.flatnonzero(restart):
            self._start(int(g))
        terminations = np.array([g in ended for g, _ in self._seats])
        infos = self._infos(ended)
        if final:
            infos["final_obs"], infos["_final_obs"] = _objects(final), terminations.copy()
        return self._encode(self._seats), rewards, terminations, np.zeros(self.num_envs, dtype=bool), infos

    def close_extras(self, **kwargs: Any) -> None:
        self._sim.close()


class ArenaVectorEnv(_Seats):
    """`num_envs` matches stepped together in one call, you as fighter 1 in each.

    `opponent` plays fighter 2: a house bot ("ts-starter" or "random"), a `Policy` (called once
    a step with the observations and masks of every game it plays, so a network runs batched), a
    `ScriptedOpponent`, or a list of these assigned to the environments in turn. `set_opponents`
    changes them for the matches that start next, e.g. to add a newer copy of your policy.
    Needs an array encoder such as `Basic`; for raw messages use `Simulator` directly.
    """

    def __init__(self, num_envs: int, opponent: Any = "ts-starter", encoder: Encoder | None = None,
                 reward: Reward = win_loss, map: str | None = None, source: str | os.PathLike[str] | None = None,
                 autoreset_mode: AutoresetMode = AutoresetMode.NEXT_STEP):
        super().__init__(num_envs, [(g, 1) for g in range(num_envs)], encoder, reward, map, source, autoreset_mode)
        self.set_opponents(opponent)
        self._playing: list[Any] = [None] * num_envs

    def set_opponents(self, opponent: Any) -> None:
        """Sets fighter 2 for the matches that start from now on (one opponent, or a list spread over the environments)."""
        ops = opponent if isinstance(opponent, (list, tuple)) else [opponent]
        self.opponents = [ops[g % len(ops)] for g in range(self.num_envs)]

    def _options(self, g: int) -> dict[str, Any]:
        self._playing[g] = self.opponents[g]
        # A house bot runs inside the game; any other opponent is a second player this environment plays.
        return {"opponent": self._playing[g]} if isinstance(self._playing[g], str) else {}

    def _other_replies(self, games: list[int]) -> dict[int, dict[int, Any]]:
        replies: dict[int, dict[int, Any]] = {}
        groups: dict[int, tuple[Any, list[int]]] = {}
        for g in games:
            op = self._playing[g]
            if isinstance(op, ScriptedOpponent):
                replies[g] = {2: op.decide(self._obs[g][2], self._hello[g][2], g)}
            elif not isinstance(op, str):
                groups.setdefault(id(op), (op, []))[1].append(g)
        for op, gs in groups.values():
            seats = [(g, 2) for g in gs]
            actions = op(self._encode(seats), self._masks(seats))
            for k, g in enumerate(gs):
                replies[g] = {2: self.encoder.decode(actions[k], self._obs[g][2], self._hello[g][2])}
        return replies


class ArenaSelfPlayEnv(_Seats):
    """Self-play: `num_games` matches stepped together, both fighters of each played by you. Its
    `2 * num_games` environments are the seats in order (game 0's fighter 1, game 0's fighter 2,
    game 1's fighter 1, ...), so one policy learns from both sides of every match. Both seats of a
    match end on the same step. Needs an array encoder such as `Basic`.
    """

    def __init__(self, num_games: int, encoder: Encoder | None = None, reward: Reward = win_loss,
                 map: str | None = None, source: str | os.PathLike[str] | None = None,
                 autoreset_mode: AutoresetMode = AutoresetMode.NEXT_STEP):
        super().__init__(num_games, [(g, f) for g in range(num_games) for f in (1, 2)], encoder, reward, map, source, autoreset_mode)
