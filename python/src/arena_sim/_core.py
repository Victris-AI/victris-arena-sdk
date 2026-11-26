"""The simulator in embedded V8: the ladder's own match code (arena-sim.js), stepped in batches.

A call from Python into V8 costs about 180 microseconds, several ticks' worth, so a Simulator
holds many games and steps them all in one call.
"""

from __future__ import annotations

import atexit
import json
import os
import weakref
from collections.abc import Mapping, Sequence
from contextlib import suppress
from importlib.resources import files
from typing import Any

_v8_pid: int | None = None
# Isolates still open at process exit (forgotten close, module caches). Closing here avoids a hang on
# Python 3.13+ where MiniRacer's garbage-collection teardown can stall indefinitely.
_live: weakref.WeakSet[Any] = weakref.WeakSet()


def _track(ctx: Any) -> Any:
    _live.add(ctx)
    return ctx


def _dispose_tracked() -> None:
    for ctx in list(_live):
        with suppress(Exception):
            ctx.close()


atexit.register(_dispose_tracked)


def _context() -> Any:
    global _v8_pid
    from py_mini_racer import MiniRacer, init_mini_racer

    if _v8_pid is None:
        # mini-racer's default flag, --single-threaded, turns off V8's background compilation,
        # which halves the engine's speed. V8 starts on first use, so in each process after a fork.
        init_mini_racer(flags=(), ignore_duplicate_init=True)
        _v8_pid = os.getpid()
    elif _v8_pid != os.getpid():
        # V8's threads don't survive fork(): using it in the child would crash without a word.
        raise RuntimeError(
            "arena_sim: V8 was started in the parent process before it forked this one. Start worker "
            "processes with the 'spawn' method (e.g. AsyncVectorEnv(..., context='spawn')), or don't "
            "use a Simulator or environment in the parent until the workers have started."
        )
    return _track(MiniRacer())


def _source(path: str | os.PathLike[str] | None) -> str:
    path = path or os.environ.get("ARENA_SIM_JS")
    if path:
        with open(path, encoding="utf-8") as f:
            return f.read()
    return files("arena_sim").joinpath("arena-sim.js").read_text(encoding="utf-8")


def _load(source: str | os.PathLike[str] | None = None, scripts: Sequence[str | os.PathLike[str]] = ()) -> Any:
    """A V8 context with the simulator (`ArenaSim`), then each script in `scripts`, which can
    register bots and encoders of yours (`ArenaSim.registerBot`, `ArenaSim.registerEncoder`)."""
    if isinstance(scripts, (str, os.PathLike)):
        scripts = [scripts]
    ctx = _context()
    ctx.eval(_source(source))
    ctx.eval(_GLUE)
    for path in scripts:
        with open(path, encoding="utf-8") as f:
            code = f.read()
        try:
            ctx.eval(code)
        except Exception as e:
            raise ValueError(f"{os.fspath(path)}: {str(e).splitlines()[0] if str(e) else type(e).__name__}") from e
    return ctx


# Plain functions, because mini-racer calls a function with `this` set to the global object.
_GLUE = """
var __batch = null;
function __versions() {
  return JSON.stringify({ release: ArenaSim.RELEASE, engine: ArenaSim.ENGINE_VERSION, protocol: ArenaSim.PROTOCOL_VERSION, rules: ArenaSim.SHIPPED_RULES.version, rules_hash: ArenaSim.rulesHash(ArenaSim.SHIPPED_RULES), maps: ArenaSim.SHIPPED_MAPS.map((m) => m.name), house_bots: Object.keys(ArenaSim.HOUSE_BOTS) });
}
"""


def _by_fighter(msgs: Mapping[str, Any]) -> dict[int, Any]:
    return {int(k): v for k, v in msgs.items()}


class Simulator:
    """Many games at once, each the ladder's match code driven by the replies you give it.

    A game's options are `new Game`'s: `seed`, `opponent` (a house bot playing fighter 2:
    "ts-starter" or "random"; without one you play both fighters), `map`, `rules`, `limits`, `name`,
    `version`. Messages are the JSON the ladder sends, as dicts keyed by fighter id.
    `source` is an arena-sim.js to run instead of the bundled one (default: $ARENA_SIM_JS).
    `scripts` are JavaScript files run after it, which can register bots of yours to name as an
    `opponent` (`ArenaSim.registerBot`).
    """

    def __init__(self, num_games: int = 1, source: str | os.PathLike[str] | None = None, scripts: Sequence[str | os.PathLike[str]] = ()):
        if num_games < 1:
            raise ValueError("num_games must be at least 1")
        self.num_games = num_games
        self._source = source
        self._scripts = scripts
        self._ctx: Any = None

    def _js(self) -> Any:
        if self._ctx is None:
            ctx = _load(self._source, self._scripts)
            ctx.eval(f"__batch = new ArenaSim.Batch({self.num_games});")
            self._ctx = ctx
        return self._ctx

    def close(self) -> None:
        """Releases the embedded V8 isolate. Safe to call more than once; further use raises."""
        ctx = self._ctx
        self._ctx = None
        if ctx is not None:
            ctx.close()

    def __enter__(self) -> Simulator:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def versions(self) -> dict[str, Any]:
        """What the game was built with: the release, engine and protocol versions, rules version and hash, maps, house bots."""
        return json.loads(self._js().eval("__versions()"))

    def start(self, i: int, **options: Any) -> tuple[dict[int, dict], dict[int, dict]]:
        """Starts a game in slot `i`. Returns each of your fighters' `hello` and first observation."""
        out = json.loads(self._js().eval(f"__batch.start({int(i)}, {json.dumps(options)})"))
        return _by_fighter(out["hello"]), _by_fighter(out["next"])

    def step(self, replies: Sequence[Mapping[int, Any] | None]) -> list[dict[int, dict] | None]:
        """Steps every game with a reply in one call: `replies[i]` is game i's `{fighter: reply}`,
        or None to leave it alone. A reply is a turn dict (its `tick` is filled in), the raw JSON
        text, or None for no reply. Returns, by slot, what each player is sent next (an observation,
        or `end` once that game is over), or None for a game not stepped."""
        if len(replies) != self.num_games:
            raise ValueError(f"step takes {self.num_games} replies, one per game (None to skip)")
        payload = json.dumps([None if r is None else {str(k): v for k, v in r.items()} for r in replies])
        out = json.loads(self._js().eval(f"__batch.step({json.dumps(payload)})"))
        return [None if msgs is None else _by_fighter(msgs) for msgs in out]

    def result(self, i: int) -> dict | None:
        """Game i's result (`winner`, `reason`, `final_tick`), or None while it is running."""
        return json.loads(self._js().eval(f"JSON.stringify(__batch.game({int(i)}).result)"))

    def state(self, i: int) -> dict:
        """Game i's whole match state as it stands, fog and all: what `ForwardModel` steps. For training
        and testing a search with the truth; on the ladder a bot only has its observations."""
        return json.loads(self._js().eval(f"JSON.stringify(__batch.game({int(i)}).state())"))

    def replay(self, i: int) -> dict:
        """Game i's replay, once it is over: `header`, `ticks` and `result`, as the ladder records them."""
        return json.loads(self._js().eval(f"JSON.stringify(__batch.game({int(i)}).replay())"))

    def replay_text(self, i: int) -> str:
        """Game i's replay as a replay file's text (JSON Lines); gzip it for `arena view`."""
        return self._js().eval(f"ArenaSim.encodeReplay(__batch.game({int(i)}).replay())")
