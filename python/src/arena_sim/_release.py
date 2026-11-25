"""What this release is made of: its release notes, and the TypeScript the bundled game was built
from (arena-sim.js.map carries every source file, as the release's tag has it)."""

from __future__ import annotations

import json
import posixpath
import re
import urllib.request
from importlib.resources import files
from pathlib import Path

from ._check import ladder_url

_HEADING = re.compile(r"## (\d+)\.(\d+)\.(\d+)\b")


def _bundled(name: str) -> str:
    return files("arena_sim").joinpath(name).read_text(encoding="utf-8")


def _release() -> str:
    return re.search(r'\bRELEASE = "([^"]+)"', _bundled("arena-sim.js")).group(1)  # type: ignore[union-attr]


def _sections(markdown: str) -> list[tuple[tuple[int, ...], str]]:
    """Each release's notes, heading included, newest first; Unreleased and the preamble left out.
    A heading inside a code block stays in its release's notes."""
    out: list[tuple[tuple[int, ...], list[str]]] = []
    current: list[str] | None = None
    fenced = False
    for line in markdown.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            m = _HEADING.match(line)
            current = None
            if m:
                current = [line]
                out.append((tuple(int(g) for g in m.groups()), current))
        elif current is not None:
            current.append(line)
    return [(v, "".join(lines).rstrip() + "\n") for v, lines in out]


def changelog(server: str | None = None, offline: bool = False) -> str:
    """The release notes of every release since this one, from the ladder (default: $ARENA_SERVER,
    else the public ladder), newest first. Offline, or when the ladder can't be reached, the notes
    bundled with this release: its own and the ones before."""
    release = _release()
    ours = tuple(int(p) for p in release.split("."))
    if not offline:
        try:
            req = urllib.request.Request(f"{ladder_url(server)}/api/changelog", headers={"User-Agent": f"arena-sim/{release}"})
            with urllib.request.urlopen(req, timeout=15) as res:
                newer = [text for v, text in _sections(json.load(res)["markdown"]) if v > ours]
            return "\n".join(newer) if newer else f"Nothing since {release}: it is the newest release.\n"
        except Exception:
            pass
    return "\n".join(text for v, text in _sections(_bundled("CHANGELOG.md")) if v <= ours)


def write_source(dest: str | Path) -> list[str]:
    """Writes the TypeScript (and the libraries) the bundled game was built from under `dest`, at
    their paths in the game's repository, with this release's CHANGELOG.md. Returns the paths."""
    smap = json.loads(_bundled("arena-sim.js.map"))
    root = Path(dest)
    written = []
    for name, text in zip(smap["sources"], smap.get("sourcesContent") or []):
        # The map's paths are relative to packages/sim/dist, where the bundle is built.
        path = posixpath.normpath(posixpath.join("packages/sim/dist", name))
        if text is None or path.startswith("../") or path.startswith("/"):
            continue
        out = root / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        written.append(path)
    (root / "CHANGELOG.md").write_text(_bundled("CHANGELOG.md"), encoding="utf-8")
    written.append("CHANGELOG.md")
    return written
