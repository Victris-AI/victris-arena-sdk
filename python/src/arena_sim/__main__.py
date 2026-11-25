"""python -m arena_sim versions | check [ladder URL] | changelog [ladder URL] | source <dir>"""

import json
import sys

from ._check import check, ladder_url, rules_note
from ._core import Simulator
from ._release import changelog, write_source

USAGE = "usage: python -m arena_sim versions | check [ladder URL] | changelog [ladder URL] | source <dir>"


def main(argv: list[str]) -> int:
    if argv[:1] == ["versions"]:
        print(json.dumps(Simulator().versions(), indent=2))
        return 0
    if argv[:1] == ["check"] and len(argv) <= 2:
        server = ladder_url(argv[1] if len(argv) == 2 else None)
        r = check(server)
        ours, theirs = r["simulator"], r["ladder"]
        if r["current"]:
            print(f"current: release {ours['release']}, rules {ours['rules']} ({ours['rules_hash']}), as {server} runs")
            return 0
        print(f"out of date: this is release {ours['release']} (rules {ours['rules_hash']}); {server} runs {theirs.get('release')} (rules {theirs.get('rules_hash')})")
        print(rules_note(r))
        print(f"what changed: python -m arena_sim changelog {server}")
        print(f"update with: {r['update']}")
        return 1
    if argv[:1] == ["changelog"] and len(argv) <= 2:
        print(changelog(argv[1] if len(argv) == 2 else None), end="")
        return 0
    if argv[:1] == ["source"] and len(argv) == 2:
        written = write_source(argv[1])
        print(f"wrote {len(written)} files under {argv[1]}: the TypeScript this release was built from, and its CHANGELOG.md")
        return 0
    print(USAGE, file=sys.stderr)
    return 2


sys.exit(main(sys.argv[1:]))
