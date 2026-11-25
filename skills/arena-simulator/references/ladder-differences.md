## Differences from the ladder

- **No clock.** Nothing is timed, so `self.budget_ms_left` stays at the match budget and a reply
  never arrives late. On the ladder you have 1 second a tick and 300 seconds a match, network time
  included; time your bot's decisions yourself.
- **Your fighter is 1 against the starter.** On the ladder you may be fighter 1 or 2. The seed, not
  the id, decides who spawns where, and the maps are mirror-symmetric, so a policy shouldn't care.
- **Only the starter and Random are bundled.** `ts-starter` runs the same strategy as the downloadable
  TypeScript starter. Brawler, Kiter and the other house opponents are available on the ladder;
  their strategies and shared helpers are excluded from simulator bundles and source maps.
  Train offline with the starter, Random, self-play, your own bots or networks learned from replays.
  The stronger Brawler and Kiter are scripted ladder opponents, with the same combat rules.

- **Bundled limits.** Deadlines and failure tolerance are the release's defaults. Pass the live
  `operational_policy.match_limits` from `GET /api` as `Game`'s `limits` option to reproduce the
  ladder's current ones; replays keep their match's actual limits.
- **No matchmaking.** Online weighted/information policy choices do not affect offline games.
  Offline games use the opponents, maps and seats you choose; they don't
  reproduce queueing, the ladder's map balancing or its fighter-id assignment. When comparing bots,
  cover every map and both fighter ids.
- **No live transport.** There are no reconnects, `server_draining` notices or restarts to handle.

From https://victrisarena.com/docs/simulator#differences-from-the-ladder

## Staying current

Rules and engine change only in a release, and each release's simulator carries its number. A
simulator is current while its release and rules hash match the ladder's (`GET /api`,
`versions.release` and `versions.rules_hash`). After a release, download it again.

- **Hear about releases.** Subscribe to `https://victrisarena.com/changelog.atom`. A release that
  changes the rules says so in its title: until you update, the simulator plays another game.
- **The Python package warns when the ladder plays other rules.** It compares what the ladder has
  already sent you with the rules it ships, and raises an `OutdatedSimulatorWarning` (once per rules
  table) when they differ. It never contacts a ladder on its own to do it:
  - a live match's `hello`, when `Basic` or `ScriptEncoder` encodes the match's first observation.
    With an encoder of your own, call `check_hello(hello)` when a match starts;
  - the replays `download_replays` fetches (each replay's header records its rules).

  The match limits in `hello.rules.limits` are the ladder's live settings and don't count. The
  simulator's own games (`sim-…` match ids), on rules you pass to it, are left alone.

- **See what changed.** `python -m arena_sim changelog` prints the ladder's release notes since
  yours (`changelog()` in Python). Each package also carries its own release's notes.
- **Read the source.** Each release ships the TypeScript it was built from, as source maps next to
  the bundles (`arena-sim.mjs.map`, `arena-sim.js.map`) and inside the Python package:
  `python -m arena_sim source ./arena-src` writes it out (`packages/engine/src/…`, `packages/sim/src/…`)
  with that release's `CHANGELOG.md`.
- **Go back to a release.** Every release's downloads stay at `/download/<release>/…`, for example
  `pip install https://victrisarena.com/download/0.41.1/arena_sim-0.41.1-py3-none-any.whl`, so you can
  re-run training or evaluation on the simulator a policy was trained on.

```bash
python -m arena_sim check https://victrisarena.com   # says whether it's current, and how to update
python -m arena_sim changelog                      # what changed since this release
python -m arena_sim source ./arena-src             # the TypeScript this release was built from
```

```js
import { RELEASE, SHIPPED_RULES, rulesHash } from "./arena-sim.mjs";

const api = await (await fetch("https://victrisarena.com/api")).json();
if (api.versions.release !== RELEASE || api.versions.rules_hash !== rulesHash(SHIPPED_RULES))
  console.warn("the ladder runs another release: download the simulator again");
// A live bot can check the rules it trained on at the start of each match. The ladder writes its
// live limits into hello.rules.limits, which don't change the game, so leave them out:
// rulesHash({ ...hello.rules, limits: SHIPPED_RULES.limits }) === rulesHash(SHIPPED_RULES)
```

From https://victrisarena.com/docs/simulator#staying-current
