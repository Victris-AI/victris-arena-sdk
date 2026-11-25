"""Is this simulator the one a ladder runs? Rules change only in a release, so comparing the
release and the rules hash with the ladder's GET /api answers it.

Without asking anyone, the simulator also notices when what a ladder already sent you was played
on other rules: a live match's hello (through `Basic`, `ScriptEncoder` or `check_hello`) and the
replays `download_replays` fetches. It warns (`OutdatedSimulatorWarning`) once per rules table."""

from __future__ import annotations

import json
import os
import urllib.request
import warnings
from typing import Any

PUBLIC_LADDER = "https://victrisarena.com"


class OutdatedSimulatorWarning(UserWarning):
    """A ladder plays on other rules (or runs another release) than this simulator."""


def ladder_url(server: str | None = None) -> str:
    """The ladder to compare with: `server`, else $ARENA_SERVER, else the public ladder."""
    return (server or os.environ.get("ARENA_SERVER") or PUBLIC_LADDER).rstrip("/")


def check(server: str | None = None, source: str | None = None) -> dict[str, Any]:
    """Compares this simulator with the ladder at `server` (default: $ARENA_SERVER, else the public
    ladder). Returns `current` (True when they match), both sides' versions, and `update`: the
    command that installs the ladder's package."""
    from ._core import Simulator

    ours = Simulator(source=source).versions()
    # A hosted ladder sits behind Cloudflare, which refuses Python's default user agent.
    req = urllib.request.Request(f"{ladder_url(server)}/api", headers={"User-Agent": f"arena-sim/{ours['release']}"})
    with urllib.request.urlopen(req, timeout=15) as res:
        api = json.load(res)
    theirs = api["versions"]
    current = ours["release"] == theirs.get("release") and ours["rules_hash"] == theirs.get("rules_hash")
    return {"current": current, "simulator": ours, "ladder": theirs, "update": f"pip install {api['simulator']['python']}"}


def rules_note(r: dict[str, Any]) -> str:
    """Whether an out-of-date simulator (`r`, from `check`) still plays the ladder's game."""
    ours, theirs = r["simulator"], r["ladder"]
    if ours["rules_hash"] == theirs.get("rules_hash"):
        return f"The rules are the same ({ours['rules']}), so matches still play as they do on the ladder."
    return f"The rules changed ({ours['rules']} → {theirs.get('rules')}): matches here no longer play as they do on the ladder."


_ctx: Any = None
# by rules table: whether it is this simulator's game (warned about once)
_seen: dict[str, bool] = {}

# Limits are the ladder's live operational settings, which it writes into each match's rules: they
# change without a release and don't change the game, so the comparison leaves them out.
_SAME_GAME = """
function __sameGame(text) {
  var shipped = ArenaSim.SHIPPED_RULES, rules = JSON.parse(text);
  return JSON.stringify({
    same: ArenaSim.rulesHash(Object.assign({}, rules, { limits: shipped.limits })) === ArenaSim.rulesHash(shipped),
    release: ArenaSim.RELEASE, ours: shipped.version, theirs: rules.version,
  });
}
"""


def same_rules(rules: dict[str, Any], where: str) -> bool:
    """Whether `rules` (a match's) are the game this simulator ships, limits aside. Warns once per
    rules table when they aren't; `where` says what was played on them ("This ladder match is played")."""
    key = json.dumps(rules, sort_keys=True)
    if key in _seen:
        return _seen[key]
    global _ctx
    if _ctx is None:
        from ._core import _load

        _ctx = _load()
        _ctx.eval(_SAME_GAME)
    r = json.loads(_ctx.eval(f"__sameGame({json.dumps(key)})"))
    _seen[key] = r["same"]
    if not r["same"]:
        version = r["theirs"] if r["theirs"] != r["ours"] else f"{r['theirs']}, though not this release's table of that version"
        warnings.warn(
            f"{where} on rules {version}, but arena_sim {r['release']} ships rules {r['ours']}: what you train "
            "or test with this simulator isn't the game that ladder plays. See what changed with python -m arena_sim "
            "changelog, and install the ladder's simulator (GET /api → simulator.python).",
            OutdatedSimulatorWarning,
            stacklevel=3,
        )
    return r["same"]


def check_hello(hello: dict[str, Any]) -> bool:
    """Whether a live match's `hello` has this simulator's rules (limits aside); warns once per rules
    table when it hasn't. Call it when a match starts in a bot with an encoder of your own (`Basic`
    and `ScriptEncoder` do). Matches the simulator itself plays, and replays, are its own game."""
    match = str(hello.get("match_id", ""))
    if match.startswith("sim-") or match == "replay" or "rules" not in hello:
        return True
    return same_rules(hello["rules"], "This ladder match is played")
