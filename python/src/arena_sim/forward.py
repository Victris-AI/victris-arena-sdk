"""The forward model: the engine's own tick, for bots that look ahead.

    from arena_sim import ForwardModel
    fm = ForwardModel()
    state = fm.from_observation(hello, obs, {"enemy": {"pos": [10, 10]}})
    for child, events in fm.step_many(state, [{1: {"move": "E"}, 2: {}}, {1: {"dash": "W"}, 2: {}}]):
        ...

These are the simulator's `forward` functions (the ladder's own match code) in embedded V8. A state
is the engine's match state as a plain dict, JSON-safe, so it can be read, edited to fit what you
believe, and stored. Unlike the JavaScript `forward.step`, which changes the state it is given,
`step` and `step_many` return new states and leave theirs alone.

Each call into V8 costs about 180 microseconds plus copying the state both ways, more than a tick
itself, so expand a search node's children with one `step_many`, not one `step` each.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from typing import Any

from ._core import _load

_GLUE = """
function __fwdStepMany(state, all) {
  const out = [];
  for (const turns of all) {
    const s = ArenaSim.forward.clone(state);
    const events = ArenaSim.forward.step(s, turns);
    out.push([s, events]);
  }
  return out;
}
"""


def _turns(turns: Mapping[int, Any] | None) -> dict[str, Any]:
    return {str(k): v for k, v in (turns or {}).items()}


class ForwardModel:
    """The simulator's forward model: build a state from what a bot was told, then step it.

    `source` is an arena-sim.js to run instead of the bundled one (default: $ARENA_SIM_JS).
    """

    def __init__(self, source: str | os.PathLike[str] | None = None):
        self._source = source
        self._ctx: Any = None

    def _js(self) -> Any:
        if self._ctx is None:
            ctx = _load(self._source)
            ctx.eval(_GLUE)
            self._ctx = ctx
        return self._ctx

    def _call(self, expr: str, *args: Any) -> Any:
        # Arguments go in as one JSON document, parsed once on the other side.
        payload = json.dumps(json.dumps(list(args)))
        return json.loads(self._js().eval(f"JSON.stringify((({expr}))(...JSON.parse({payload})))"))

    def close(self) -> None:
        """Releases the embedded V8 isolate. Safe to call more than once; further use starts a new one."""
        ctx = self._ctx
        self._ctx = None
        if ctx is not None:
            ctx.close()

    def __enter__(self) -> ForwardModel:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def api(self) -> int:
        """The forward model's contract version (`forward.api`); it changes when a function's arguments or results do."""
        return int(self._js().eval("ArenaSim.forward.api"))

    def start(self, hello: Mapping[str, Any], map: Mapping[str, Any] | None = None) -> dict:
        """The match's state on its first tick, exactly as the ladder starts it, from the `hello`
        (which names the map and carries the seed). `map` is needed only for a map this release doesn't ship."""
        return self._call("ArenaSim.forward.start", hello, map)

    def from_observation(
        self,
        hello: Mapping[str, Any],
        obs: Mapping[str, Any],
        assume: Mapping[str, Any] | None = None,
        map: Mapping[str, Any] | None = None,
    ) -> dict:
        """A state that agrees with everything `obs` shows, for fighter `hello["bot_id"]`. What it
        doesn't show comes from `assume` (see the simulator guide: `self`, `enemy`, `pickups`,
        `projectiles`, `areas`), otherwise from a cautious default. An enemy out of sight needs
        `assume["enemy"]["pos"]`."""
        return self._call("ArenaSim.forward.fromObservation", hello, obs, assume or {}, map)

    def step(self, state: Mapping[str, Any], turns: Mapping[int, Any] | None) -> tuple[dict, list[dict]]:
        """One tick from `state` with each fighter's turn (a dict as a bot sends it, by fighter id;
        a missing one is idle). Returns the new state and the tick's events; `state` is unchanged."""
        return self.step_many(state, [turns])[0]

    def step_many(self, state: Mapping[str, Any], turns: Sequence[Mapping[int, Any] | None]) -> list[tuple[dict, list[dict]]]:
        """One tick from `state` for each entry of `turns`, in one call: a search node's children.
        Returns `(new state, events)` for each, in order."""
        out = self._call("__fwdStepMany", state, [_turns(t) for t in turns])
        return [(s, events) for s, events in out]

    def observe(self, state: Mapping[str, Any], fighter: int) -> dict:
        """What `fighter` is told on this tick: the observation it would receive, without the server's budget and events."""
        return self._call("ArenaSim.forward.observe", state, int(fighter))

    def options(self, state: Mapping[str, Any], fighter: int) -> dict:
        """The steps and dashes `fighter` could start now: `{"moves": [...], "dashes": [...]}`."""
        return self._call("ArenaSim.forward.options", state, int(fighter))

    def validate(self, state: Mapping[str, Any], fighter: int, turn: Mapping[str, Any] | None) -> dict:
        """How the engine would take `fighter`'s turn now: `{"turn": parts it plays, "rejected": [...]}`."""
        return self._call("ArenaSim.forward.validate", state, int(fighter), turn)

    def hash(self, state: Mapping[str, Any]) -> str:
        """The ladder's hash of the whole state, as recorded with every replay tick."""
        return self._call("ArenaSim.forward.hash", state)
