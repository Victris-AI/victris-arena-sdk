"""Victris Arena's simulator: the ladder's own match code, run in embedded V8, for training offline.

    from arena_sim import ArenaVectorEnv, Basic
    env = ArenaVectorEnv(64, opponent=["ts-starter"], encoder=Basic())

`Simulator` is the batched, low-level interface (any number of games, self-play included);
`ArenaEnv` and `ArenaVectorEnv` are Gymnasium environments, and `arena_sim.multiagent` has a
PettingZoo one for self-play. `FastVectorEnv` and `FastSelfPlayEnv` play the same matches many
times faster, with the encoding computed inside the simulator: `Basic`, or your own in JavaScript,
which `ScriptEncoder` also runs in a live bot. `ForwardModel` is the engine's own tick for bots that look ahead: build a state from a hello or an
observation, then step candidate turns. `check(ladder_url)` (or `python -m arena_sim check <url>`) says
whether this is the release the ladder runs. Without asking anyone, it also warns
(`OutdatedSimulatorWarning`) when a live match's hello (`Basic`, `ScriptEncoder`, `check_hello`) or the
replays `download_replays` fetches were played on other rules than this simulator's. `changelog()` has the release notes since this
release, and `write_source(dir)` the TypeScript this release was built from.
"""

from ._check import OutdatedSimulatorWarning, check, check_hello
from ._core import Simulator
from ._data import download_replays, replay_trajectories
from ._release import changelog, write_source
from ._script import ScriptEncoder, check_encoder, replay_dataset
from .encoding import DIRS, Basic, Encoder, MessageSpace, Raw, damage_trade, win_loss
from .envs import ArenaEnv, ArenaSelfPlayEnv, ArenaVectorEnv, ScriptedOpponent
from .fast import FastSelfPlayEnv, FastVectorEnv, decode_grid
from .forward import ForwardModel

__all__ = ["DIRS", "OutdatedSimulatorWarning", "changelog", "check", "check_hello", "check_encoder", "download_replays", "replay_dataset", "replay_trajectories", "ScriptEncoder", "ArenaEnv", "ArenaSelfPlayEnv", "ArenaVectorEnv", "FastSelfPlayEnv", "FastVectorEnv", "ForwardModel", "ScriptedOpponent", "Basic", "Encoder", "MessageSpace", "Raw", "Simulator", "damage_trade", "decode_grid", "win_loss", "write_source"]
