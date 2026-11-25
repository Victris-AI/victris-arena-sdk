"""Ladder games as training data: each fighter's view of a recorded match, rebuilt from its replay
by the match code the server ran it on (for imitation learning, offline RL and analysis)."""

from __future__ import annotations

import atexit
import gzip
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import warnings
from collections.abc import Iterator

from ._check import same_rules
from ._core import Simulator

_simulators: dict[str | None, Simulator] = {}


def _close_simulators() -> None:
    while _simulators:
        _simulators.popitem()[1].close()


atexit.register(_close_simulators)


def _text(replay: str | bytes | os.PathLike[str] | dict) -> str:
    if isinstance(replay, dict):  # parsed: {"header": ..., "ticks": [...], "result": ...}
        lines = [replay["header"], *replay["ticks"], *([replay["result"]] if replay.get("result") else [])]
        return "\n".join(json.dumps(line) for line in lines) + "\n"
    if isinstance(replay, str) and replay.lstrip().startswith("{"):
        return replay
    if isinstance(replay, (str, os.PathLike)):
        with open(replay, "rb") as f:
            replay = f.read()
    if replay[:2] == b"\x1f\x8b":
        replay = gzip.decompress(replay)
    return replay.decode("utf-8")


def replay_trajectories(replay: str | bytes | os.PathLike[str] | dict, source: str | os.PathLike[str] | None = None) -> dict[int, dict]:
    """Each fighter's trajectory in a recorded match, by fighter id: `hello`, `steps` (each tick's
    `observation` as the bot was sent it, and the `turn` the server took from its reply, with a
    `reason` when that turn was idle because of a timeout, a bad message...) and `end`.

    `replay` is a replay file's path, its bytes (gzipped or not), its text, or a parsed replay.
    Exact but for what a replay doesn't record: `budget_ms_left` stays at the match budget,
    `match_id` is "replay", the deadlines in `hello` are the rules' defaults, a refused message's event has no `detail`, and a
    match the server ended early (a disqualification) lacks the last observation it sent. Raises
    ValueError for a replay from another engine version or rules table than this simulator's.
    """
    key = None if source is None else os.fspath(source)
    sim = _simulators.get(key) or _simulators.setdefault(key, Simulator(source=source))
    try:
        out = sim._js().eval(f"JSON.stringify(ArenaSim.replayTrajectories(ArenaSim.parseReplay({json.dumps(_text(replay))})))")
    except Exception as e:  # the engine's message says why (another engine version, a rules mismatch...)
        raise ValueError(str(e).splitlines()[0]) from e
    return {int(k): v for k, v in json.loads(out).items()}


def _get(url: str) -> bytes:
    # A hosted ladder sits behind Cloudflare, which refuses Python's default user agent.
    req = urllib.request.Request(url, headers={"User-Agent": "victris-arena-sim"})
    with urllib.request.urlopen(req, timeout=60) as res:
        return res.read()


class _OutsideWindow(Exception):
    """The ladder won't hand this replay to anyone without Arena+: it's older than both bots' newest
    200 public matches. Newer matches only push it further out, so the answer never changes."""


def _refusal(e: urllib.error.HTTPError) -> str | None:
    try:
        return json.loads(e.read()).get("code")
    except Exception:
        return None


def download_replays(server: str, bot: str | None = None, limit: int = 50, min_rating: float | None = None,
                     cache: str | os.PathLike[str] | None = None) -> Iterator[tuple[dict, str]]:
    """The ladder's most recent matches, newest first, as pairs of the match record (`GET
    /api/matches`: bots, versions, winner, reason...) and its replay's text. Voided matches are skipped.

    Whose matches: `bot`'s (at most 500), everyone's, or with `min_rating`, those of every bot on the
    leaderboard rated at least that (each one's most recent `limit`, each match once); each match
    record then also has `strong`, the fighter ids of those bots in it, for picking whose turns to
    learn from (`replay_dataset(..., fighters=...)`). `cache` is a directory to keep replays in: one
    already there isn't downloaded again, so a second run only fetches what's new. Replays played on
    other rules than this simulator's raise an `OutdatedSimulatorWarning` (once per rules table).

    Anyone may download each bot's newest 200 public matches. A bot's list stops at its first match
    older than that, since every match after it is older still, with a warning naming where.
    """
    base = server.rstrip("/")
    strong: set[str] | None = None
    if min_rating is not None:
        board = json.loads(_get(f"{base}/api/leaderboard"))
        strong = {row["name"] for row in board if row["rating"] >= min_rating}
        names = sorted(strong) if bot is None else [bot]
    else:
        names = [bot]
    seen: set[str] = set()
    packs: dict[str, dict[str, bytes]] = {}
    for name in names:
        query = urllib.parse.urlencode({"limit": limit, **({"bot": name} if name else {})})
        for match in json.loads(_get(f"{base}/api/matches?{query}")):
            if match.get("voided") or match["id"] in seen:
                continue
            seen.add(match["id"])
            if strong is not None:
                match["strong"] = [b["fighter"] for b in match["bots"] if b["name"] in strong]
            try:
                data = _fetch(match, cache, packs)
            except _OutsideWindow:
                warnings.warn(
                    f"{name or 'The ladder'}: match {match['id']} and older are outside the public "
                    "replay window (each bot's newest 200 matches), so the list stops there",
                    stacklevel=2,
                )
                break
            text = _text(data)
            # The header, the replay's first line, has the rules the match was played on.
            header = json.loads(text.split("\n", 1)[0])
            if header.get("type") == "header" and "rules" in header:
                same_rules(header["rules"], "The ladder's replays were played")
            yield match, text


def _replay_bytes(match: dict, packs: dict[str, dict[str, bytes]]) -> bytes:
    """From its minute's pack, which holds many matches at once, or else from its own URL: older
    matches aren't in one, and a pack appears a minute or two after its matches end."""
    url = match.get("pack_url")
    if url and url not in packs:
        packs.clear()  # the matches come in order, so a pack's are together
        try:
            packs[url] = _read_pack(_get(url))
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            packs[url] = {}
    held = (packs.get(url) or {}).get(match["id"])
    if held:
        return held
    try:
        return _get(match["replay_url"])
    except urllib.error.HTTPError as e:
        if e.code == 403 and _refusal(e) == "arena_plus_required":
            raise _OutsideWindow(match["id"]) from None
        raise


def _read_pack(data: bytes) -> dict[str, bytes]:
    """A pack is a line of JSON, its index, then the gzipped files it locates."""
    head, _, body = data.partition(b"\n")
    return {m["id"]: body[m["replay"][0]:sum(m["replay"])] for m in json.loads(head)["matches"]}


def _fetch(match: dict, cache: str | os.PathLike[str] | None, packs: dict[str, dict[str, bytes]]) -> bytes:
    if cache is None:
        return _replay_bytes(match, packs)
    path = os.path.join(cache, f"{match['id']}.jsonl.gz")
    # A refusal is kept too, so a rerun doesn't ask about the same old match again.
    outside = path + ".outside"
    if os.path.exists(outside):
        raise _OutsideWindow(match["id"])
    if not os.path.exists(path):
        os.makedirs(cache, exist_ok=True)
        try:
            data = _replay_bytes(match, packs)
        except _OutsideWindow:
            open(outside, "wb").close()
            raise
        with open(path + ".part", "wb") as f:
            f.write(data)
        os.replace(path + ".part", path)
    with open(path, "rb") as f:
        return f.read()
