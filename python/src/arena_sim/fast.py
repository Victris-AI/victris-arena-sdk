"""Fast environments: the encoding done inside the simulator, read in place.

`ArenaVectorEnv` and `ArenaSelfPlayEnv` send every observation from V8 to Python as the ladder's
JSON and encode it in Python, which costs about 30 times what the game does. `FastVectorEnv` and
`FastSelfPlayEnv` play the same matches through the same match code, but the simulator writes each
seat's arrays, action mask, reward and done flag into one buffer that numpy reads without a copy,
and actions go back the same way. The encoder runs in the simulator: `Basic` (a test checks it
matches `Basic.encode` on the ladder's JSON exactly), or your own, written in JavaScript and loaded
with `scripts`, which can also add bots of yours to play against or learn from. With `workers=N`
the games are split over N processes, each with its own V8, sharing memory with this one.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import pickle
import sys
import time
from collections.abc import Callable, Sequence
from multiprocessing.shared_memory import SharedMemory
from typing import Any

import numpy as np
from gymnasium import spaces
from gymnasium.vector import AutoresetMode, VectorEnv
from gymnasium.vector.utils import batch_space

from ._core import _load
from .encoding import Basic
from .envs import ScriptedOpponent

HOUSE_BOTS = ("random", "ts-starter")
EXTERNAL = "@external"
REWARDS = ("win_loss", "damage_trade")
GRIDS = ("float32", "uint8")

_DANGER = Basic.CHANNELS.index("danger")
# Basic's danger value for each code: 1 / code (worked out in float64 then rounded, as Basic does), 0 for none.
_DANGER_VALUES = np.array([0.0] + [1.0 / c for c in range(1, 256)]).astype(np.float32)
_danger_tensors: dict[Any, Any] = {}


def decode_grid(codes: Any) -> Any:
    """`Basic`'s grid from a `grid="uint8"` one, value for value: a danger code c is 1 / c (0 for
    none), any other code is half its value. Takes a numpy array or a torch tensor (on any device)
    shaped (..., channels, size, size) and returns float32 of the same kind. Danger more than 254
    ticks away reads as 1/255, the one place the codes are not exact."""
    torch = sys.modules.get("torch")
    if torch is not None and isinstance(codes, torch.Tensor):
        out = codes.float() * 0.5
        # kept per device, so after the first call this copies nothing from the host (a CUDA graph can replay it)
        values = _danger_tensors.get(codes.device)
        if values is None:
            values = _danger_tensors[codes.device] = torch.as_tensor(_DANGER_VALUES, device=codes.device)
        out[..., _DANGER, :, :] = values[codes[..., _DANGER, :, :].long()]
        return out
    out = np.asarray(codes).astype(np.float32) * np.float32(0.5)
    out[..., _DANGER, :, :] = _DANGER_VALUES[np.asarray(codes)[..., _DANGER, :, :]]
    return out

Policy = Callable[[Any, "np.ndarray"], Any]
"""A batched opponent policy: (observations, action masks) -> actions, called once a step with every game it plays."""


Scripts = Sequence[str | os.PathLike[str]]


def _shapes(seats: int, spec: dict[str, Any]) -> dict[str, tuple[np.dtype, tuple[int, ...]]]:
    """Every array the batch shares, by name: its type and shape. The simulator's VectorLayout has the same names."""
    grid = (seats, *spec["gridShape"])
    vec = (seats, spec["features"])
    f4, i4 = np.dtype(np.float32), np.dtype(np.int32)
    g = np.dtype(spec["gridType"])
    return {
        "grid": (g, grid), "vec": (f4, vec), "final_grid": (g, grid), "final_vec": (f4, vec),
        "reward": (f4, (seats,)), "dealt": (f4, (seats,)), "taken": (f4, (seats,)), "action": (i4, (seats,)),
        "seed": (i4, (seats,)), "teacher": (i4, (seats,)), "mask": (np.dtype(np.int8), (seats, spec["actions"])),
        "terminated": (np.dtype(np.uint8), (seats,)), "result": (np.dtype(np.int8), (seats,)),
    }


def _js(op: Any) -> str | None:
    """How the simulator sees an opponent or teacher: a bot's name, EXTERNAL for one played from Python, or None (from the buffer)."""
    if isinstance(op, ScriptedOpponent):
        return EXTERNAL
    return op if isinstance(op, str) else None


class _Batch:
    """One VectorBatch in this process's V8; `arrays` are views of its buffer, by name. Plays the
    games' `ScriptedOpponent`s and a `ScriptedOpponent` teacher itself, after every step."""

    def __init__(self, num_games: int, options: dict[str, Any], source: str | os.PathLike[str] | None, scripts: Scripts,
                 opponents: Sequence[Any], teacher: Any):
        self._profiling = bool(options.get("profile"))
        self._num_games = num_games
        self._v8_seconds = self._python_seconds = 0.0
        self._steps = 0
        self._completed_at: float | None = None
        self._ctx = _load(source, scripts)
        self._opponents = list(opponents)
        self._playing: list[Any] = [None] * num_games
        self._teacher = teacher
        self._hellos: dict[tuple[int, int], dict] = {}
        js = {**options, "opponents": [_js(op) for op in opponents], "teacher": _js(teacher)}
        out = json.loads(self._ctx.eval(f"var __vec = new ArenaSim.VectorBatch({int(num_games)}, {json.dumps(js)}); "
                                        "JSON.stringify({layout: __vec.layout, spec: __vec.spec, bots: ArenaSim.botNames()})"))
        self.spec, self.bots = out["spec"], out["bots"]
        buf = self._ctx.eval("__vec.buffer")
        self.arrays = {}
        for name, (dtype, shape) in _shapes(2 * num_games, self.spec).items():
            at = out["layout"][name]
            assert at["length"] == int(np.prod(shape)), name
            self.arrays[name] = np.frombuffer(buf, dtype, at["length"], at["offset"]).reshape(shape)

        self._ready_at = time.perf_counter() if self._profiling else None

    def profile(self, reset: bool = False) -> dict[str, Any] | None:
        if not self._profiling:
            return None
        simulator = json.loads(self._ctx.eval(f"JSON.stringify(__vec.profile({str(reset).lower()}))"))
        result = {"pid": os.getpid(), "first_game": 0, "num_games": self._num_games,
                  "ready_at": self._ready_at, "completed_at": self._completed_at, "steps": self._steps,
                  "v8_seconds": self._v8_seconds, "python_seconds": self._python_seconds, "simulator": simulator}
        if reset:
            self._v8_seconds = self._python_seconds = 0.0
            self._steps = 0
        return result

    def _answer(self) -> None:
        """Plays the seats Python plays or teaches: each gets its observation as the ladder's JSON."""
        if self._teacher is None and not any(isinstance(op, ScriptedOpponent) for op in [*self._opponents, *self._playing]):
            return
        pending = json.loads(self._ctx.eval("__vec.pending()"))
        if not pending:
            return
        turns = []
        for g, fighter, role, hello, obs in pending:
            if hello is not None:
                self._hellos[(g, fighter)] = hello
                if role == "opponent":
                    self._playing[g] = self._opponents[g]
            who = self._teacher if role == "teacher" else self._playing[g]
            turns.append([g, fighter, role, who.decide(obs, self._hellos[(g, fighter)], (g, fighter))])
        self._ctx.eval(f"__vec.answer({json.dumps(json.dumps(turns))})")

    def reset(self, seed: int) -> None:
        self._ctx.eval(f"__vec.reset({int(seed)})")
        self._answer()

    def step(self) -> None:
        if not self._profiling:
            self._ctx.eval("__vec.step()")
            self._answer()
            return
        before = time.perf_counter()
        self._ctx.eval("__vec.step()")
        after_v8 = time.perf_counter()
        self._answer()
        self._completed_at = time.perf_counter()
        self._v8_seconds += after_v8 - before
        self._python_seconds += self._completed_at - after_v8
        self._steps += 1

    def set_opponents(self, opponents: Sequence[Any]) -> None:
        self._ctx.eval(f"__vec.setOpponents({json.dumps([_js(op) for op in opponents])})")
        self._opponents = list(opponents)

    def set_teacher(self, teacher: Any) -> None:
        self._ctx.eval(f"__vec.setTeacher({json.dumps(_js(teacher))})")
        self._teacher = teacher

    def replay_text(self, g: int) -> str | None:
        return self._ctx.eval(f"__vec.replayText({int(g)})")

    def close(self) -> None:
        # Drop views of the V8 ArrayBuffer before disposing the isolate (needed for a clean exit).
        # Clear in place: FastVectorEnv keeps `self._a` as this same dict.
        self.arrays.clear()
        ctx = getattr(self, "_ctx", None)
        self._ctx = None
        if ctx is not None:
            ctx.close()


def _worker(conn: Any, seats: int, first: int, num_games: int, options: dict[str, Any], source: Any, scripts: Scripts,
            opponents: Sequence[Any], teacher: Any, copy_final: bool) -> None:
    """A worker process: its own V8 and batch for games [first, first + num_games), copied into the shared arrays after each call."""
    shm: SharedMemory | None = None
    shared: dict[str, np.ndarray] = {}
    batch: _Batch | None = None
    profiling = bool(options.get("profile"))
    timing = dict(action_copy_seconds=0.0, publication_seconds=0.0, service_seconds=0.0, service_cpu_seconds=0.0)
    completed_at = None
    try:
        batch = _Batch(num_games, options, source, scripts, opponents, teacher)
        conn.send(("ready", {"spec": batch.spec, "bots": batch.bots}))
        cmd, name = conn.recv()
        assert cmd == "attach", cmd
        shm = SharedMemory(name=name)
        shared = _views(shm.buf, seats, batch.spec)
        mine = slice(2 * first, 2 * (first + num_games))
        outputs = [n for n in batch.arrays if n != "action" and (copy_final or not n.startswith("final_"))]

        def publish() -> None:
            for n in outputs:
                shared[n][mine] = batch.arrays[n]

        conn.send(("ok", None))
        while True:
            cmd, arg = conn.recv()
            if cmd == "step":
                if profiling:
                    before, cpu = time.perf_counter(), time.process_time()
                batch.arrays["action"][:] = shared["action"][mine]
                if profiling:
                    after_action = time.perf_counter()
                batch.step()
                if profiling:
                    after_batch = time.perf_counter()
                publish()
                if profiling:
                    completed_at = time.perf_counter()
                    timing["action_copy_seconds"] += after_action - before
                    timing["publication_seconds"] += completed_at - after_batch
                    timing["service_seconds"] += completed_at - before
                    timing["service_cpu_seconds"] += time.process_time() - cpu
                # Completion is timestamped before the ACK, independent of parent receive order.
                conn.send(("ok", completed_at))
            elif cmd == "profile":
                report = batch.profile(arg)
                if report is not None:
                    report.update(timing)
                    report["completed_at"] = completed_at
                    report["first_game"] = first
                conn.send(("ok", report))
                if arg:
                    for key in timing:
                        timing[key] = 0.0
            elif cmd == "reset":
                batch.reset(arg)
                publish()
                conn.send(("ok", None))
            elif cmd == "opponents":
                batch.set_opponents(arg)
                conn.send(("ok", None))
            elif cmd == "teacher":
                batch.set_teacher(arg)
                conn.send(("ok", None))
            elif cmd == "replay":
                conn.send(("ok", batch.replay_text(arg)))
            elif cmd == "close":
                break
    except Exception as e:  # the parent raises it
        conn.send(("error", f"{type(e).__name__}: {e}"))
    finally:
        shared.clear()
        if batch is not None:
            batch.close()
        if shm is not None:
            shm.close()


def _views(buf: Any, seats: int, spec: dict[str, Any]) -> dict[str, np.ndarray]:
    out, offset = {}, 0
    for name, (dtype, shape) in _shapes(seats, spec).items():
        offset = -(-offset // 8) * 8
        n = int(np.prod(shape))
        out[name] = np.ndarray(shape, dtype, buf, offset)
        offset += n * dtype.itemsize
    return out


def _bytes(seats: int, spec: dict[str, Any]) -> int:
    offset = 0
    for dtype, shape in _shapes(seats, spec).values():
        offset = -(-offset // 8) * 8 + int(np.prod(shape)) * dtype.itemsize
    return offset


def _recv(conn: Any, expect: str = "ok") -> Any:
    kind, value = conn.recv()
    if kind == "error":
        raise RuntimeError(f"arena_sim worker failed: {value}")
    assert kind == expect, kind
    return value


def _sendable(value: Any) -> Any:
    """Checks that an opponent or teacher can go to a worker process, which needs it pickled."""
    try:
        pickle.dumps(value)
    except Exception as e:
        raise ValueError("with workers, every ScriptedOpponent is sent to the worker processes, so its decide must "
                         f"be picklable: a function defined at the top level of a module, not a lambda or closure ({e})") from None
    return value


class _Pool:
    """The games split over worker processes (started with spawn: V8 doesn't survive fork); `arrays` are in shared memory."""

    def __init__(self, num_games: int, workers: int, options: dict[str, Any], source: Any, scripts: Scripts,
                 opponents: Sequence[Any], teacher: Any, copy_final: bool):
        self._profiling = bool(options.get("profile"))
        self._parent = dict(steps=0, dispatch_seconds=0.0, wait_seconds=0.0,
                            dispatch_thread_cpu_seconds=0.0, wait_thread_cpu_seconds=0.0)
        seats = 2 * num_games
        _sendable((list(opponents), teacher))
        ctx = multiprocessing.get_context("spawn")
        self._conns, self._procs, self._firsts = [], [], []
        first = 0
        src = os.fspath(source) if source is not None else None
        paths = [os.fspath(p) for p in scripts]
        for w in range(workers):
            n = num_games // workers + (1 if w < num_games % workers else 0)
            parent, child = ctx.Pipe()
            p = ctx.Process(target=_worker, args=(child, seats, first, n, options, src, paths, list(opponents[first:first + n]), teacher, copy_final), daemon=True)
            p.start()
            self._conns.append(parent)
            self._procs.append(p)
            self._firsts.append(first)
            first += n
        ready = self._all("ready")
        self.spec, self.bots = ready[0]["spec"], ready[0]["bots"]
        # the encoder's sizes are known once a worker has loaded it, so the shared memory comes after
        self._shm = SharedMemory(create=True, size=_bytes(seats, self.spec))
        self.arrays = _views(self._shm.buf, seats, self.spec)
        self._send("attach", self._shm.name)

    def _all(self, expect: str = "ok") -> list[Any]:
        return [_recv(c, expect) for c in self._conns]

    def _send(self, cmd: str, arg: Any = None) -> list[Any]:
        for c in self._conns:
            c.send((cmd, arg))
        return self._all()

    def reset(self, seed: int) -> None:
        # each worker gets its own seed, so the games differ between workers but repeat for a seed
        seeds = np.random.default_rng(seed).integers(0, 2**31, len(self._conns))
        for c, s in zip(self._conns, seeds):
            c.send(("reset", int(s)))
        self._all()

    def step(self) -> None:
        if not self._profiling:
            self._send("step")
            return
        before, cpu = time.perf_counter(), time.thread_time()
        for c in self._conns:
            c.send(("step", None))
        dispatched, dispatch_cpu = time.perf_counter(), time.thread_time()
        self._all()
        self._parent["steps"] += 1
        self._parent["dispatch_seconds"] += dispatched - before
        self._parent["wait_seconds"] += time.perf_counter() - dispatched
        self._parent["dispatch_thread_cpu_seconds"] += dispatch_cpu - cpu
        self._parent["wait_thread_cpu_seconds"] += time.thread_time() - dispatch_cpu

    def profile(self, reset: bool = False) -> dict[str, Any] | None:
        if not self._profiling:
            return None
        workers = self._send("profile", reset)
        result = {"parent": dict(self._parent), "workers": workers}
        if reset:
            for key in self._parent:
                self._parent[key] = 0
        return result

    def set_opponents(self, opponents: Sequence[Any]) -> None:
        _sendable(list(opponents))
        for c, first, nxt in zip(self._conns, self._firsts, [*self._firsts[1:], len(opponents)]):
            c.send(("opponents", list(opponents[first:nxt])))
        self._all()

    def set_teacher(self, teacher: Any) -> None:
        self._send("teacher", _sendable(teacher))

    def replay_text(self, g: int) -> str | None:
        w = max(i for i, first in enumerate(self._firsts) if first <= g)
        self._conns[w].send(("replay", g - self._firsts[w]))
        return _recv(self._conns[w])

    def close(self) -> None:
        for c in self._conns:
            try:
                c.send(("close", None))
            except (BrokenPipeError, OSError):
                pass
        for p in self._procs:
            p.join(5)
            if p.is_alive():
                p.terminate()
        if hasattr(self, "_shm"):
            self.arrays = {}
            self._shm.close()
            self._shm.unlink()


def _objects(values: list[Any]) -> np.ndarray:
    out = np.empty(len(values), dtype=object)
    for i, v in enumerate(values):
        out[i] = v
    return out


def _inside(op: Any) -> Any:
    """What the simulator's side needs of an opponent: a bot's name or a ScriptedOpponent; a policy runs here, from the buffer."""
    return op if isinstance(op, (str, ScriptedOpponent)) else None


class _FastSeats(VectorEnv):
    """Games stepped together by the simulator, which encodes them itself.

    `encoder` is "basic" (`Basic`, which takes `size` and `grid`) or the name of an encoder a script
    in `scripts` registers (`ArenaSim.registerEncoder`); the observation is `{"grid", "vec"}` and the
    action a number below the encoder's action count. `teacher` is a bot (a house bot's name or one a
    script registers with `ArenaSim.registerBot`) or a `ScriptedOpponent`: its turn on each of your
    seats, as the encoder's closest action allowed now, is in `info["teacher_action"]` (-1 where none
    fits), for distilling it into your policy. `set_teacher` changes it for the matches that start next.

    Autoreset, `info["seed"]`, `info["action_mask"]` and `info["final_obs"]` (same-step autoreset)
    work as in `ArenaVectorEnv`. Instead of the `end` message, a seat whose match just ended has
    `info["result"]`: 1 for a win, -1 for a loss, 0 for a draw. `reward` is "win_loss" or
    "damage_trade" (the functions of the same names, computed in the simulator); for a reward of
    your own, `info["dealt"]` and `info["taken"]` are the damage each seat dealt and took this tick,
    as fractions of its max hp (0 on the tick a match ends).

    The arrays a step returns are copies unless `copy=False`: then `grid` and `vec` are views of the
    simulator's buffer (no copying at all for self-play), overwritten by the next step, so use them
    before stepping again. With `grid="uint8"` `Basic`'s grid is a byte a tile, a quarter the size,
    and `decode_grid` turns it back into `Basic`'s values exactly (on the GPU, if you like).
    `replay_text(g)` gives game g's most recently finished match.
    """

    def __init__(self, num_games: int, seats: slice, map: str | None, reward: str, size: int, workers: int,
                 copy: bool, grid: str, source: str | os.PathLike[str] | None, autoreset_mode: AutoresetMode,
                 encoder: str = "basic", scripts: Scripts = (), teacher: Any = None, taught: Sequence[int] = (1, 2),
                 opponents: Sequence[Any] = (), profile: bool = False, profile_every: int = 16):
        if autoreset_mode not in (AutoresetMode.NEXT_STEP, AutoresetMode.SAME_STEP):
            raise ValueError("autoreset_mode is AutoresetMode.NEXT_STEP or AutoresetMode.SAME_STEP")
        if reward not in REWARDS:
            raise ValueError(f"reward is one of {', '.join(REWARDS)} (fast environments compute it in the simulator; "
                             "for your own, use info['dealt'] and info['taken'])")
        if not 1 <= workers <= num_games:
            raise ValueError(f"workers must be between 1 and the number of games ({num_games})")
        if grid not in GRIDS:
            raise ValueError(f"grid is one of {', '.join(GRIDS)}")
        if not isinstance(profile, bool):
            raise ValueError("profile must be a bool")
        if isinstance(profile_every, bool) or not isinstance(profile_every, int) or profile_every < 1 or profile_every > 2**53 - 1:
            raise ValueError("profile_every must be a positive safe integer")
        self._check_teacher(teacher)
        self.metadata = {"autoreset_mode": autoreset_mode}
        self.num_games = num_games
        self._mine = seats
        self.num_envs = len(range(2 * num_games)[seats])
        self.copy = copy
        same = autoreset_mode == AutoresetMode.SAME_STEP
        options = {"profile": {"every": profile_every} if profile else False, "reward": reward, "size": size, "grid": grid, "encoder": encoder, "taught": list(taught),
                   "autoreset": "same_step" if same else "next_step", **({"map": map} if map else {})}
        inside = [_inside(op) for op in opponents] or [None] * num_games
        self._backend: _Batch | _Pool = (_Batch(num_games, options, source, scripts, inside, teacher) if workers == 1
                                         else _Pool(num_games, workers, options, source, scripts, inside, teacher, same))
        self._a = self._backend.arrays
        self.spec, self.bots = self._backend.spec, self._backend.bots
        self.teacher = teacher
        if encoder == "basic":
            self.encoder: Basic | None = Basic(size)
            self.single_observation_space = self.encoder.observation_space
            if grid == "uint8":
                coded = spaces.Box(0, 255, self.encoder.observation_space["grid"].shape, np.uint8)
                self.single_observation_space = spaces.Dict({"grid": coded, "vec": self.encoder.observation_space["vec"]})
            self.single_action_space = self.encoder.action_space
        else:
            self.encoder = None
            shape = tuple(self.spec["gridShape"])
            g = spaces.Box(0, 255, shape, np.uint8) if self.spec["gridType"] == "uint8" else spaces.Box(-np.inf, np.inf, shape, np.float32)
            self.single_observation_space = spaces.Dict({"grid": g, "vec": spaces.Box(-np.inf, np.inf, (self.spec["features"],), np.float32)})
            self.single_action_space = spaces.Discrete(self.spec["actions"])
        self.observation_space = batch_space(self.single_observation_space, self.num_envs)
        self.action_space = batch_space(self.single_action_space, self.num_envs)
        self._rng = np.random.default_rng()
        self._done = np.zeros(num_games, dtype=bool)

    def _check_teacher(self, teacher: Any) -> None:
        if teacher is not None and not isinstance(teacher, (str, ScriptedOpponent)):
            raise ValueError("a teacher is a bot's name or a ScriptedOpponent")

    def set_teacher(self, teacher: Any) -> None:
        """Sets the teacher for the matches that start from now on: a bot's name, a `ScriptedOpponent`, or None."""
        self._check_teacher(teacher)
        if isinstance(teacher, str) and teacher not in self.bots:
            raise ValueError(f"unknown bot '{teacher}' ({', '.join(self.bots)})")
        self._backend.set_teacher(teacher)
        self.teacher = teacher

    def profile(self, reset: bool = False) -> dict[str, Any] | None:
        """Detached diagnostic totals, or None unless profile=True. Clearing counters leaves games alone.

        Python durations are seconds from perf_counter (wall time, including scheduling) and
        process/thread CPU clocks. Worker completion timestamps precede ACK sends. The simulator's
        sampled phase durations are milliseconds; its clock and sample interval are in each report.
        Queries are explicit: step never serializes a simulator profile or observations for telemetry.
        """
        report = self._backend.profile(reset)
        if report is None or isinstance(self._backend, _Pool):
            return report
        return {"parent": None, "workers": [report]}

    def _opponent_actions(self) -> None:
        """Fills the actions of the seats this environment plays itself."""

    def _restarted(self, games: np.ndarray) -> None:
        """Called with the games whose next match has just started."""

    def _out(self, name: str) -> np.ndarray:
        view = self._a[name][self._mine]
        return np.array(view) if self.copy or name not in ("grid", "vec") else view

    def _infos(self) -> dict[str, Any]:
        everywhere = np.ones(self.num_envs, dtype=bool)
        info = {"seed": self._a["seed"][self._mine].astype(np.int64), "_seed": everywhere,
                "action_mask": np.array(self._a["mask"][self._mine]), "_action_mask": everywhere,
                "dealt": np.array(self._a["dealt"][self._mine]), "_dealt": everywhere,
                "taken": np.array(self._a["taken"][self._mine]), "_taken": everywhere}
        if self.teacher is not None:
            info["teacher_action"], info["_teacher_action"] = self._a["teacher"][self._mine].astype(np.int64), everywhere
        return info

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        self._backend.reset(int(self._rng.integers(0, 2**31)))
        self._done = np.zeros(self.num_games, dtype=bool)
        self._restarted(np.arange(self.num_games))
        return {"grid": self._out("grid"), "vec": self._out("vec")}, self._infos()

    def step(self, actions: Any) -> tuple[Any, np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
        self._a["action"][self._mine] = np.asarray(actions).reshape(self.num_envs)
        self._opponent_actions()
        restarting = np.flatnonzero(self._done)
        self._backend.step()
        ended = self._a["terminated"][0::2].astype(bool)  # both seats of a match end together
        same_step = self.metadata["autoreset_mode"] == AutoresetMode.SAME_STEP
        self._done = ended & ~same_step
        self._restarted(np.flatnonzero(ended) if same_step else restarting)
        terminated = self._a["terminated"][self._mine].astype(bool)
        infos = self._infos()
        if terminated.any():
            infos["result"], infos["_result"] = self._a["result"][self._mine].astype(np.int64), terminated
            if same_step:
                grid, vec = self._a["final_grid"][self._mine], self._a["final_vec"][self._mine]
                infos["final_obs"] = _objects([{"grid": np.array(grid[i]), "vec": np.array(vec[i])} if t else None for i, t in enumerate(terminated)])
                infos["_final_obs"] = terminated.copy()
        obs = {"grid": self._out("grid"), "vec": self._out("vec")}
        return obs, np.array(self._a["reward"][self._mine]), terminated, np.zeros(self.num_envs, dtype=bool), infos

    def replay_text(self, g: int) -> str | None:
        """Game g's most recently finished match as a replay file's text (JSON Lines; gzip it for `arena view`), or None."""
        return self._backend.replay_text(g)

    def close_extras(self, **kwargs: Any) -> None:
        self._backend.close()


class FastSelfPlayEnv(_FastSeats):
    """`ArenaSelfPlayEnv` with the encoding computed in the simulator: `num_games` matches, both
    fighters of each played by you, as `2 * num_games` environments in order (game 0's fighter 1,
    game 0's fighter 2, game 1's fighter 1, ...). See `_FastSeats` for the encoder, the teacher and
    what differs from the JSON environments.
    """

    def __init__(self, num_games: int, map: str | None = None, reward: str = "win_loss", size: int = 21,
                 workers: int = 1, copy: bool = True, grid: str = "float32", source: str | os.PathLike[str] | None = None,
                 autoreset_mode: AutoresetMode = AutoresetMode.NEXT_STEP, encoder: str = "basic", scripts: Scripts = (),
                 teacher: Any = None, profile: bool = False, profile_every: int = 16):
        super().__init__(num_games, slice(None), map, reward, size, workers, copy, grid, source, autoreset_mode, encoder, scripts, teacher,
                         profile=profile, profile_every=profile_every)


class FastVectorEnv(_FastSeats):
    """`ArenaVectorEnv` with the encoding computed in the simulator: `num_envs` matches, you as fighter 1.

    `opponent` plays fighter 2: a bot by name (a house bot, "ts-starter" or "random", or one a
    script in `scripts` registers), which runs inside the simulator; a `ScriptedOpponent`, a bot
    written in Python, which gets each observation as the ladder's JSON; a `Policy` (called once a
    step with the arrays and masks of every game it plays); or a list of these spread over the
    games. `set_opponents` changes them for the matches that start next. See `_FastSeats` for the
    encoder, the teacher and what differs from the JSON environments.
    """

    def __init__(self, num_envs: int, opponent: Any = "ts-starter", map: str | None = None, reward: str = "win_loss",
                 size: int = 21, workers: int = 1, copy: bool = True, grid: str = "float32",
                 source: str | os.PathLike[str] | None = None, autoreset_mode: AutoresetMode = AutoresetMode.NEXT_STEP,
                 encoder: str = "basic", scripts: Scripts = (), teacher: Any = None, profile: bool = False, profile_every: int = 16):
        ops = self._spread(opponent, num_envs)
        super().__init__(num_envs, slice(0, None, 2), map, reward, size, workers, copy, grid, source, autoreset_mode,
                         encoder, scripts, teacher, (1,), ops, profile, profile_every)
        self._playing: list[Any] = [None] * num_envs
        self.set_opponents(opponent)

    @staticmethod
    def _spread(opponent: Any, n: int) -> list[Any]:
        ops = list(opponent) if isinstance(opponent, (list, tuple)) else [opponent]
        for op in ops:
            if not isinstance(op, (str, ScriptedOpponent)) and not callable(op):
                raise ValueError("an opponent is a bot's name, a ScriptedOpponent or a batched policy")
        return [ops[g % len(ops)] for g in range(n)]

    def set_opponents(self, opponent: Any) -> None:
        """Sets fighter 2 for the matches that start from now on (one opponent, or a list spread over the games)."""
        ops = self._spread(opponent, self.num_envs)
        for op in ops:
            if isinstance(op, str) and op not in self.bots:
                raise ValueError(f"unknown bot '{op}' ({', '.join(self.bots)})")
        self.opponents = ops
        self._backend.set_opponents([_inside(op) for op in ops])

    @property
    def playing(self) -> list[Any]:
        """Each game's opponent in the match it is playing now (`opponents` is who plays the next ones)."""
        return list(self._playing)

    def _restarted(self, games: np.ndarray) -> None:
        for g in games:
            self._playing[g] = self.opponents[g]

    def _opponent_actions(self) -> None:
        groups: dict[int, tuple[Any, list[int]]] = {}
        for g, op in enumerate(self._playing):
            if callable(op) and not isinstance(op, (str, ScriptedOpponent)) and not self._done[g]:
                groups.setdefault(id(op), (op, []))[1].append(g)
        for op, games in groups.values():
            seats = 2 * np.array(games) + 1
            obs = {"grid": self._a["grid"][seats], "vec": self._a["vec"][seats]}
            self._a["action"][seats] = np.asarray(op(obs, np.array(self._a["mask"][seats]))).reshape(len(games))
