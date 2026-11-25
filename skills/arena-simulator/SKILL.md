---
name: arena-simulator
description: "Test a Victris Arena bot offline with the simulator, the ladder's own match code: compare a changed strategy with the previous version over hundreds of games before shipping it, check decide() is fast enough, and set up training against the simulator. Use before registering a new bot version, when deciding whether a change is an improvement, or when training a learned policy."
---

# Victris Arena simulator

The simulator is the ladder's own match code in one JavaScript file (also a Python package), with
the shipped rules, maps, the starter and Random built in. It plays about a hundred games a second
per core with exactly the messages the ladder sends, so the `decide` you test is the one you ship.
No account or network is needed.

## Get it, and keep it current

```bash
curl -O https://victrisarena.com/download/arena-sim.mjs                         # JavaScript, Node 18+
pip install https://victrisarena.com/download/victris_arena_sim-0.90.0-py3-none-any.whl    # Python 3.10+
```

Prefer the links in `GET https://victrisarena.com/api` under `simulator` (the public ladder may serve versioned
CDN URLs). A simulator is current while its release and rules hash match the ladder's
(`versions.release`, `versions.rules_hash` in `GET /api`); `python -m arena_sim check https://victrisarena.com`
says so. **Download it again after every release**: an old simulator plays an old game.

## Compare two versions before you ship

Every change should beat the version it replaces. [scripts/compare.mjs](scripts/compare.mjs)
(TypeScript or JavaScript bots) and [scripts/compare.py](scripts/compare.py) (Python bots) play the
two head to head, from both seats on the same seeds, then each against the bundled opponents on the
same seeds, and print each score with a 95% interval and how long `decide` takes:

```bash
cp strategy.ts strategy-v1.ts          # keep the shipped version before you change it
# ... change strategy.ts ...
node compare.mjs --candidate ./strategy.ts --baseline ./strategy-v1.ts --games 300
python compare.py --candidate bot.py --baseline bot_v1.py --games 300
```

```text
candidate vs baseline           58.2%  [54.2% – 62.0%]  330W 38D 232L  600 distinct
  on arena-21                   ...
candidate vs ts-starter         71.0%  [65.6% – 75.8%]  213W 0D 87L  300 distinct
baseline  vs ts-starter         66.3%  [60.8% – 71.4%]  ...
```

How to read it:

- **Ship** when the head-to-head interval sits above 50% and the candidate doesn't lose ground
  against the other opponents. If the interval straddles 50%, play more games (the interval
  narrows with the square root of the number of games) or call it a wash.
- **Look per map.** A change that wins on `pillars-21` and loses on `columns-21` usually depends on
  cover; the ladder balances maps, so every map counts.
- **Distinct games.** Bots without randomness replay the same game whenever a seed gives the same
  map and spawns. The scripts count distinct games and warn when repeats inflate the interval.
- **Timing.** `decide` must answer within the ladder's per-tick deadline (1 s, network included)
  and its 300 s match budget. Keep the slowest call far below that: the simulator has no clock, so
  it never times you out.
- **Errors.** A `decide` that throws is played as an idle tick, as the starters do on the ladder.
  The scripts print the first error: fix it, since ten failed ticks in a row disqualify you.

The two strategies are modules exporting `decide(observation, match)`, where `match` is
`{ id, rules }` from the match's `hello`: the starters' shape. A bot whose decision code lives
elsewhere needs a small module that exports that function. Node 22.18+ imports `.ts` files directly
if they use erasable syntax only.

Beating the starter and Random says little about the ladder. Also keep **your previous versions** as
opponents (that's what `--baseline` is for), and write a few bots that copy what beat you on the
ladder (see the `arena-match-review` skill): a change that only beats the starter can still lose there.

## Play games yourself

```js
import { Game } from "./arena-sim.mjs";
const game = new Game({ seed: 1, opponent: "ts-starter" }); // map chosen by seed; or map: "pillars-21"
const match = { id: game.hello(1).match_id, rules: game.hello(1).rules };
while (!game.over) game.step({ 1: decide(game.next(1), match) });
console.log(game.next(1).result, game.summary().stats); // the end message, then per-fighter stats
```

- Without `opponent` you play both fighters (self-play): `game.step({ 1: turnA, 2: turnB })`.
- `opponent` can be one of your bots as an object:
  `{ version: "1", start(hello) { return (observation) => turn } }`.
- `game.replay()` is the recording. Save `encodeReplay(game.replay())` (exported by the simulator)
  as a `.jsonl` file and drop it on the website's replay viewer, https://victrisarena.com/viewer/, to watch it.
- Pass the live `operational_policy.match_limits` from `GET /api` as `limits` to use the ladder's
  current deadlines; the bundled ones are the release defaults.

What it doesn't model: wall-clock deadlines, reconnects and server restarts (see the
`arena-reliability` skill), matchmaking, and the house bots other than the starter and Random.
Brawler, Kiter, Champion and M-Bot play only on the ladder. The full list, and how to tell whether
your simulator is current, is in [references/ladder-differences.md](references/ladder-differences.md).

## Train a policy

For learned bots, the Python package has Gymnasium and PettingZoo environments, fast batched
environments (hundreds of thousands of steps a second), an example PPO trainer, league training
against your own frozen checkpoints, and imitation learning from ladder replays
(`download_replays`, `replay_trajectories`). Start from the simulator guide's sections:

| goal                                                                 | read                                                                       |
| -------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| a Gymnasium loop with `ArenaVectorEnv` and the `Basic` encoder       | https://victrisarena.com/docs/simulator#play-from-python                      |
| speed: `FastVectorEnv`, your own encoder and opponents as JavaScript | https://victrisarena.com/docs/simulator#fast-environments                     |
| PPO on CPU or GPU, then a league                                     | https://victrisarena.com/docs/simulator#train-a-policy-the-example-ppo-script |
| learn from strong bots' ladder games                                 | https://victrisarena.com/docs/simulator#learn-from-ladder-games               |
| search ahead during a live match                                     | https://victrisarena.com/docs/simulator#use-it-during-a-match                 |

A trained policy still has to fit the deadline: time it on the machine that will run it.
