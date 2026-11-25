---
name: arena-match-review
description: "Find out why a Victris Arena bot wins and loses on the ladder from its rating, version health, match statistics, position heatmaps and replays, then choose and verify the next change. Use when someone asks how their bot is doing, why it lost, whether a new version is better, or what to improve next."
---

# Victris Arena match review

Turn the ladder's records into one specific, testable change. Work from evidence (the numbers and
the replays), not guesses, and change one thing per version so the next review can tell whether it
worked.

## 1. Where does the bot stand?

With the MCP server: `get_bot` (`{"name": "<bot>", "rating_days": 14}`). Over HTTP:
`GET https://victrisarena.com/api/bots/<bot>`.

- **Versions**, each with its own rating, record and rank. A version is ranked after 30 rated games;
  before that its rating is noise. Compare versions only once both have their 30.
- **Score** is `round(rating − 2 × max(rating_deviation, 25))`: a new or uncertain version is
  penalised until it has played enough.
- **Idle penalty:** a ranked version online (queued or playing) less than 4 hours a day loses score
  after a day away, and earns it back only by staying online (`online_owed_hours`). A drop after
  downtime isn't a strategy problem.
- `get_bot_ratings` gives its rating game by game and its daily rank, to see when a version turned.
- `get_leaderboard` shows the bots around it; `get_agents` how its AI agent compares.

## 2. Is it healthy? Fix this before strategy

Each version's `health` (in `get_bot`, over its latest 500 matches) says whether the bot is actually
playing. Problems here cost more than any strategy:

| field                     | healthy                     | if not                                                                                                 |
| ------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------ |
| `idle_pct` (by reason)    | under 0.5%                  | turns played as idle: `timeout` (too slow), `malformed_json` or `schema` (bad replies), `disconnected` |
| `disqualifications`       | 0                           | ten failed ticks in a row lost a match                                                                 |
| `near_limit_pct`          | 0                           | replies over 80% of the deadline: timeouts are coming                                                  |
| `reply_ms.p95`            | well under the 1 s deadline | slow `decide`, slow machine or slow network                                                            |
| `lowest_budget_ms_left`   | far from 0                  | the 300 s match budget is nearly spent                                                                 |
| `refused_pct` (by reason) | low                         | turn parts the engine refused (below)                                                                  |

Timeouts, disconnects and budget problems belong to the `arena-reliability` skill. Refusals point at
strategy bugs:

| refused reason                                                                   | what the bot is doing wrong                                                      |
| -------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `not_ready`                                                                      | using a move, dash or attack still on cooldown: read `self.cooldowns`            |
| `blocked`                                                                        | stepping into a wall or cutting a corner: choose from `obs.moves` / `obs.dashes` |
| `invalid_state`                                                                  | acting while stunned or recovering from a dash: check `self.state`               |
| `out_of_range`, `not_visible`                                                    | frostburst cast too far or at a tile out of sight                                |
| `missing_target`, `bad_target`, `unknown_attack`, `bad_dir`, `conflicting_moves` | malformed turn parts: fix the code that builds turns                             |

## 3. How does it lose? Read the match statistics

List recent games with statistics: `list_matches` with `{"bot": "<bot>", "stats": true, "limit": 50}`
(or `GET https://victrisarena.com/api/matches?bot=<bot>&limit=200&stats=1`). Find your fighter in each match's
`stats.fighters` by `bots[].fighter`. Then aggregate over wins and losses separately; the
difference between them is the story. What each field means is in
[references/stats-and-health.md](references/stats-and-health.md) (the API guide's sections on match
statistics, version health and heatmaps) and
[references/match-stats.schema.json](references/match-stats.schema.json).

| symptom in the stats (losses vs wins)                | likely cause                                    | direction to try                                                                   |
| ---------------------------------------------------- | ----------------------------------------------- | ---------------------------------------------------------------------------------- |
| `taken_by_source.zone` large, `zone_ticks` high      | caught outside the zone                         | leave earlier on `zone.shrinks_in`; avoid fighting on the edge late                |
| `taken_by_source.ranged` large                       | standing still near a shooter, or poor dodging  | keep moving at close range; dodge with `danger` entries for this tick and the next |
| `taken_by_source.frostburst` large                   | walking into or staying in areas                | leave `areas[].tiles` early; keep the dash for the last tick                       |
| `wall_slams`, `stunned`, `taken_by_source.wall_slam` | fighting next to walls against repulsor users   | keep a wall off your back when adjacent; step away first                           |
| low `weapons.ranged.hits / uses`                     | shooting at fighters who can move               | shoot when the target can't step (stunned, recovering, slowed) or where it must go |
| `weapons.frostburst.hits` near 0                     | casting where the enemy can walk out            | cast when its `dash_cooldown > 0` or it is slowed; cut off the short exit          |
| few `dashes`, deaths in areas                        | saving the dash too long, or wasting it earlier | dash only to escape something certain                                              |
| many `timeout_*` results, few hits either way        | parking: neither bot engages                    | keep moving and searching when the enemy is out of sight                           |
| `pickups.health` much lower than the opponents'      | losing the centre column                        | contest pads when ahead or even; time `ready_in`                                   |

Win rate per opponent and per map (`map` in each match) is the other split worth making: a bot that
loses only to Brawler, or only on `columns-21`, has one problem, not many.

## 4. Watch the games that matter

Numbers say what; replays say why. Pick two or three representative losses and:

- show them to your person with `watch_match` (`{"id": "<match>"}`): clients that display MCP Apps
  play the replay inline, others get the website link;
- open `watch_url` in the website viewer and choose your bot in the point-of-view menu to see
  exactly what it could see (fog of war included);
- for code-level study, download the replay and re-run it in the simulator: the Python package's
  `replay_trajectories(replay)` gives every observation your bot was sent and the turn the server took.
  A public match's `replay_url` needs no credential. For a private League's match, call
  `get_replay_download` (up to 100 match IDs at once) for links that work for an hour with none; a bot
  token is always refused there.

Look for the moment the game turned: a shot it stood still for, a dash spent on travel, a slam into a
wall, a late exit from the zone. Note the tick.

The **position heatmap** shows where a version spends its time, per map: `get_bot_heatmaps`, the bot
page, or `GET https://victrisarena.com/api/bots/<bot>/heatmaps?version=<label>`. Hot cells in corners or against walls, or a
version that never visits the centre column, are habits worth breaking.

## 5. Choose one change and prove it

1. Write the hypothesis in one sentence, tied to the evidence: "it loses to Brawler because it fights
   with its back to walls (12 slams in 20 losses, 1 in 20 wins)".
2. Make the smallest change that tests it.
3. Compare it with the shipped version offline over hundreds of games on every map (the
   `arena-simulator` skill's `compare` script). Don't ship a change that doesn't beat its baseline.
4. Ship it as the next version, with an alias and notes saying what changed and why: the version's
   page and its notes are your experiment log.
5. After 30 or more rated games, compare its rating and its stats with the previous version's. A
   regression shows as the new version settling below the old one; roll back by queueing the older
   label again.

## Notes

- The opponent's code isn't public. Champion and M-Bot are trained networks; Brawler presses and
  slams, Kiter keeps range. Learn them from their replays like any rival's.
- Bulk statistics can be slow for older matches: list without stats first, then fetch the games you
  need with `get_match` and `stats: true`.
- Public replays download while the match is among either bot's newest 200 games (1,000 with
  Arena+). Save the ones you want to keep.
