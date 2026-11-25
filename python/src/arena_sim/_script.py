"""Encoders written in JavaScript, outside the fast environments: in a Python bot on the ladder,
over recorded matches for imitation, and checked against the ladder's JSON.

The encoder the fast environments train with runs inside the simulator, in JavaScript, so a bot
that plays the network on the ladder must encode exactly as it did. `ScriptEncoder` runs that same
JavaScript in this process's V8: the same code reads the observation in training and on the
ladder, so nothing is written twice.
"""

from __future__ import annotations

import atexit
import json
import os
from collections import OrderedDict
from collections.abc import Callable, Iterable, Sequence
from contextlib import suppress
from typing import Any

import numpy as np
from gymnasium import spaces

from ._check import check_hello
from ._core import _load
from ._data import _text
from .encoding import Basic, Encoder

Scripts = Sequence[str | os.PathLike[str]]

# A context per (source, scripts): loading the simulator takes a moment, and registering twice is harmless.
_contexts: dict[tuple[str | None, tuple[str, ...]], Any] = {}


def _close_contexts() -> None:
    while _contexts:
        ctx = _contexts.popitem()[1]
        with suppress(Exception):
            ctx.close()


atexit.register(_close_contexts)

_GLUE = """
var __live = { encoders: [], seats: new Map() };
function __liveInit(name, size, grid) {
  var e = ArenaSim.resolveEncoder(name, { size: size, grid: grid });
  var g = ArenaSim.gridLength(e), coded = e.gridType === "uint8";
  var buffer = new ArrayBuffer(4 * e.features + (coded ? 1 : 4) * g + e.actions);
  var out = { vec: new Float32Array(buffer, 0, e.features), grid: coded ? new Uint8Array(buffer, 4 * e.features, g) : new Float32Array(buffer, 4 * e.features, g), mask: new Int8Array(buffer, 4 * e.features + (coded ? 1 : 4) * g, e.actions) };
  __live.encoders.push({ encoder: e, out: out, buffer: buffer });
  return JSON.stringify({ id: __live.encoders.length - 1, spec: { gridShape: e.gridShape, gridType: e.gridType || "float32", features: e.features, actions: e.actions } });
}
function __liveBuffer(id) { return __live.encoders[id].buffer; }
function __liveStart(id, key, hello) { __live.seats.set(key, __live.encoders[id].encoder.start(JSON.parse(hello))); }
function __liveEnd(key) { __live.seats.delete(key); }
function __liveEncode(id, key, obs) {
  var out = __live.encoders[id].out;
  out.grid.fill(0); out.vec.fill(0); out.mask.fill(0);
  __live.seats.get(key).encode(JSON.parse(obs), out);
}
function __liveTurn(key, action) { return JSON.stringify(__live.seats.get(key).turn(action)); }
function __liveAction(key, turn) { var s = __live.seats.get(key); if (!s.action) throw new Error("this encoder's seats have no action(turn)"); return s.action(JSON.parse(turn)); }
function __dataset(name, size, grid, replay, fighters) {
  var e = ArenaSim.resolveEncoder(name, { size: size, grid: grid });
  __live.data = ArenaSim.replayDataset(ArenaSim.parseReplay(replay), e, fighters === null ? undefined : fighters);
  return JSON.stringify({ steps: __live.data.steps, layout: __live.data.layout, spec: __live.data.spec });
}
function __datasetBuffer() { return __live.data.buffer; }
function __check(name, size, grid, replay, limit) {
  return JSON.stringify(ArenaSim.checkEncoder(ArenaSim.parseReplay(replay), ArenaSim.resolveEncoder(name, { size: size, grid: grid }), limit));
}
"""


def _ctx(source: str | os.PathLike[str] | None, scripts: Scripts) -> Any:
    if isinstance(scripts, (str, os.PathLike)):
        scripts = [scripts]
    key = (None if source is None else os.fspath(source), tuple(os.path.abspath(os.fspath(p)) for p in scripts))
    ctx = _contexts.get(key)
    if ctx is None:
        ctx = _contexts[key] = _load(source, scripts)
        ctx.eval(_GLUE)
    return ctx


def _spaces(spec: dict[str, Any], basic: Basic | None) -> tuple[spaces.Space, spaces.Space]:
    if basic is not None and spec["gridType"] == "float32":
        return basic.observation_space, basic.action_space
    shape = tuple(spec["gridShape"])
    g = spaces.Box(0, 255, shape, np.uint8) if spec["gridType"] == "uint8" else spaces.Box(-np.inf, np.inf, shape, np.float32)
    return spaces.Dict({"grid": g, "vec": spaces.Box(-np.inf, np.inf, (spec["features"],), np.float32)}), spaces.Discrete(spec["actions"])


class ScriptEncoder(Encoder):
    """An encoder from the simulator, by name: "basic", or one a script in `scripts` registers with
    `ArenaSim.registerEncoder`. It encodes exactly as the fast environments do with the same
    `encoder=` and `scripts=`, so a policy trained there plays on the ladder through it:

        encoder = ScriptEncoder("mine", scripts=["encoder.js"])
        x = encoder.encode(observation, hello)              # {"grid": ..., "vec": ...}
        mask = encoder.action_mask(observation, hello)
        turn = encoder.decode(policy(x, mask), observation, hello)

    It keeps each fighter's encoder (which may remember earlier ticks) by its match and fighter,
    and starts a new one when a match starts. It works in the JSON environments too
    (`ArenaVectorEnv(..., encoder=ScriptEncoder(...))`), though slower than the fast ones.
    """

    def __init__(self, name: str = "basic", scripts: Scripts = (), size: int = 21, grid: str = "float32",
                 source: str | os.PathLike[str] | None = None, keep: int = 4096):
        self._js = _ctx(source, scripts)
        out = json.loads(self._js.eval(f"__liveInit({json.dumps(name)}, {int(size)}, {json.dumps(grid)})"))
        self._id, self.spec = out["id"], out["spec"]
        self.observation_space, self.action_space = _spaces(self.spec, Basic(size) if name == "basic" else None)
        buf = self._js.eval(f"__liveBuffer({self._id})")
        f, g = self.spec["features"], int(np.prod(self.spec["gridShape"]))
        gtype = np.dtype(self.spec["gridType"])
        self._vec = np.frombuffer(buf, np.float32, f, 0)
        self._grid = np.frombuffer(buf, gtype, g, 4 * f).reshape(self.spec["gridShape"])
        self._mask = np.frombuffer(buf, np.int8, self.spec["actions"], 4 * f + gtype.itemsize * g)
        # by seat: the last tick encoded, and what it gave (a match's ticks only go forward)
        self._seats: OrderedDict[str, tuple[int, dict[str, np.ndarray], np.ndarray]] = OrderedDict()
        self._keep = keep

    def _seat(self, obs: dict, hello: dict) -> tuple[str, dict[str, np.ndarray], np.ndarray]:
        base = f"{hello.get('match_id')}:{hello.get('bot_id')}"
        last = self._seats.get(base)
        if last is not None and last[0] == obs["tick"]:
            self._seats.move_to_end(base)
            return base, last[1], last[2]
        if last is None or obs["tick"] < last[0]:  # a new match (one that reuses an id starts again from tick 0)
            check_hello(hello)
            self._js.eval(f"__liveStart({self._id}, {json.dumps(base)}, {json.dumps(json.dumps(hello))})")
        self._js.eval(f"__liveEncode({self._id}, {json.dumps(base)}, {json.dumps(json.dumps(obs))})")
        x = {"grid": self._grid.copy(), "vec": self._vec.copy()}
        self._seats[base] = (obs["tick"], x, self._mask.copy())
        self._seats.move_to_end(base)
        while len(self._seats) > self._keep:
            old, _ = self._seats.popitem(last=False)
            self._js.eval(f"__liveEnd({json.dumps(old)})")
        return base, x, self._seats[base][2]

    def encode(self, obs: dict, hello: dict) -> dict[str, np.ndarray]:
        return self._seat(obs, hello)[1]

    def action_mask(self, obs: dict, hello: dict) -> np.ndarray:
        return self._seat(obs, hello)[2]

    def decode(self, action: Any, obs: dict, hello: dict) -> dict:
        key, _, _ = self._seat(obs, hello)
        return json.loads(self._js.eval(f"__liveTurn({json.dumps(key)}, {int(action)})"))

    def action(self, turn: dict, obs: dict, hello: dict) -> int:
        """The action closest to `turn` (a teacher's, or a bot you're imitating) that the mask allows, or -1."""
        key, _, mask = self._seat(obs, hello)
        a = int(self._js.eval(f"__liveAction({json.dumps(key)}, {json.dumps(json.dumps(turn))})"))
        return a if 0 <= a < len(mask) and mask[a] else -1


Fighters = Sequence[int] | Callable[[dict], Sequence[int]] | None


def replay_dataset(replays: Iterable[Any], encoder: str = "basic", scripts: Scripts = (), fighters: Fighters = None,
                   size: int = 21, grid: str = "float32", source: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Recorded matches as training data, through an encoder from the simulator (as `ScriptEncoder`
    names it): a row for each fighter's every tick, with what it saw as your network reads it and
    the action it took.

    `replays` is any number of replays (a file's path, its bytes, its text or a parsed replay), or
    the `(match, text)` pairs `download_replays` yields. `fighters` picks whose rows to keep: None
    for both, a list of fighter ids, or a function of the replay's header (its `bots`, with each
    one's `id`, `name` and `version`) returning them. Returns numpy arrays: `grid`, `vec`, `mask`,
    `action` (the encoder's action closest to the turn the bot sent, allowed by the mask, or -1
    where there is none, as when it timed out), `fighter`, `tick` and `match` (which replay, by
    its place in `replays`), and `skipped`: the places of replays from another engine version or
    rules table, which the simulator can't replay.
    """
    js = _ctx(source, scripts)
    parts: dict[str, list[np.ndarray]] = {k: [] for k in ("grid", "vec", "mask", "action", "fighter", "tick", "match")}
    skipped: list[int] = []
    spec: dict[str, Any] | None = None
    for i, replay in enumerate(replays):
        text = _text(replay[1] if isinstance(replay, tuple) else replay)
        header = json.loads(text.split("\n", 1)[0])
        ids = fighters(header) if callable(fighters) else fighters
        if ids is not None and len(ids) == 0:
            continue
        try:
            out = json.loads(js.eval(f"__dataset({json.dumps(encoder)}, {int(size)}, {json.dumps(grid)}, {json.dumps(text)}, {json.dumps(None if ids is None else [int(x) for x in ids])})"))
        except Exception as e:
            if "recorded with engine" in str(e) or "rules hash" in str(e):
                skipped.append(i)
                continue
            raise ValueError(str(e).splitlines()[0]) from e
        spec = out["spec"]
        buf = js.eval("__datasetBuffer()")
        n = out["steps"]
        shapes = {"grid": (np.dtype(spec["gridType"]), (n, *spec["gridShape"])), "vec": (np.dtype(np.float32), (n, spec["features"])),
                  "mask": (np.dtype(np.int8), (n, spec["actions"])), "action": (np.dtype(np.int32), (n,)),
                  "fighter": (np.dtype(np.int32), (n,)), "tick": (np.dtype(np.int32), (n,))}
        for name, (dtype, shape) in shapes.items():
            at = out["layout"][name]
            parts[name].append(np.frombuffer(buf, dtype, at["length"], at["offset"]).reshape(shape).copy())
        parts["match"].append(np.full(n, i, np.int32))
    if spec is None:
        enc = ScriptEncoder(encoder, scripts, size, grid, source)
        spec = enc.spec
        empty = {"grid": np.zeros((0, *spec["gridShape"]), spec["gridType"]), "vec": np.zeros((0, spec["features"]), np.float32),
                 "mask": np.zeros((0, spec["actions"]), np.int8)}
        return {**empty, **{k: np.zeros(0, np.int32) for k in ("action", "fighter", "tick", "match")}, "skipped": skipped}
    return {**{k: np.concatenate(v) for k, v in parts.items()}, "skipped": skipped}


def check_encoder(replay: Any, encoder: str = "basic", scripts: Scripts = (), size: int = 21, grid: str = "float32",
                  limit: int = 20, source: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Checks an encoder from the simulator on a recorded match: every array it writes, and the turn
    for every action its mask allows, must be the same whether it reads the observations the fast
    environments pass it or the ladder's JSON (what a live bot reads), and `action(turn(a))` must
    give back `a` (which labelling a teacher's or a recorded bot's turns relies on). Returns
    `steps` (how many it checked) and `mismatches`, the first `limit` differences, each with its
    `fighter`, `tick`, `what` ("grid", "vec", "mask", "turn" or "action"), `index` and `detail`.
    Memory shared between seats, or state kept outside `start`, shows up here."""
    js = _ctx(source, scripts)
    text = _text(replay[1] if isinstance(replay, tuple) else replay)
    try:
        return json.loads(js.eval(f"__check({json.dumps(encoder)}, {int(size)}, {json.dumps(grid)}, {json.dumps(text)}, {int(limit)})"))
    except Exception as e:
        raise ValueError(str(e).splitlines()[0]) from e
