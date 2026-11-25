### Match stats

Use the simulator's `verifyReplay` to check a downloaded replay's tick hashes and combat result.
For a forfeit or disqualification, it checks that combat was still running, the ending is at the
next unresolved tick, and the winner is a living fighter (or a draw for a forfeit). The server's
reason for the external ending remains trusted; combat inputs do not record socket decisions.

On the public ladder, a replay downloads while its match is in either bot's newest 200 public games, or newest 1,000 with Arena+ (see [historical public recordings](#historical-public-recordings)); on a ladder you run yourself, while its match is in the 30-day feed. Temporary outages return `503` with `Retry-After: 5`.

From https://victrisarena.com/docs/api#match-stats

### Version health

`GET /api/bots/<name>` gives each version a `health` summary of up to its latest 500 matches among the bot's 2,000 up to the version's last, counting only matches with current (`stats_version` 2) stats, or null when none are available. `matches` and `turns` report that measured subset; older stats remain stored but do not contribute missing measurements as zero. Check it after deploying a version: it shows what your bot's own logs may not.

```json
"health": {"matches": 500, "turns": 214300,
  "idle_pct": 1.6, "idle_pct_by_reason": {"timeout": 1.4, "schema": 0.2},
  "refused_pct": 3.4, "refused_pct_by_reason": {"not_ready": 3.1, "blocked": 0.4},
  "reply_ms": {"replies": 213000, "mean": 410, "p50": 400, "p95": 900, "max": 1004},
  "near_limit_pct": 6.2, "lowest_budget_ms_left": 120000, "disconnects": 2, "disqualifications": 1}
```

- Percentages are of turns (one a tick), to two decimals. `idle_pct`: turns the server played as idle for the version because its reply was late, malformed or missing, and `idle_pct_by_reason` the same by reason. `refused_pct`: turns with at least one part the engine refused, and `refused_pct_by_reason` the same by reason (a turn refused for two reasons counts under each). Reason codes only, never error text.
- `reply_ms`: reply times over those matches. `p50` and `p95` come from the summed histograms, so each is the upper bound of its bucket (never above `max`); `mean` and `max` are exact. Null when no match timed a reply.
- `near_limit_pct`: replies that took at least 80% of the tick limit, as a % of replies. Anything above 0 means the version runs close to timing out.
- `lowest_budget_ms_left`: the least response-time budget any of the matches ended with.
- `disconnects`: sum of the match stats' runs of recorded `disconnected` idle turns; `disqualifications`: matches lost by failing too many ticks in a row.

The bot's page shows the same, per version, in its Health panel. Its Match interruptions column labels disconnects and disqualifications explicitly. Idle turns are percentages of turns, while disconnects count recorded interruptions and disqualifications count matches lost. Reply-time and Near limit statistics describe replies and can look healthy even when a bot disconnects. A disconnect that outlasts the reconnect grace period causes a forfeit; it does not count as a disqualification. Match and replay stats summarize these endings above the combat table. Information buttons beside the relevant metrics explain the details, including why a forfeiting fighter can still have HP. Tooltips open on hover, keyboard focus or tap and dismiss with Escape or a tap outside.

From https://victrisarena.com/docs/api#version-health

### Position heatmaps

The bot page header has a compact **Position heatmap**; click it for the large view, with a map selector.
Hover or tap a cell for its tick count and percentage of sampled ticks. The grid shows the
map’s walls. Colors scale to the selected grid’s busiest cell; compare percentages when
versions have different play time.

`GET /api/bots/<name>/heatmaps?version=<label>&ladder=public` returns
`version`, `eligible_games`, `recorded_games` and `buckets`, over the version's whole life on that
ladder: heatmaps don't age out of the window. Each bucket contains `map`, `mode`, `width`,
`height`, `games`, `ticks` and row-major `counts` (`y * width + x`). Maps and match modes stay
separate. Unknown bots, versions and ladders return 404. A missing version
is treated as unknown. Voided matches are excluded.

Each living fighter contributes one sample at the start of each resolved tick, including
idle and stunned ticks. Dashes do not count intermediate tiles. Unvisited cells have zero
counts; unavailable historical matches contribute to `eligible_games` but not `recorded_games`.
Older match statistics may omit `fighters[].occupancy`; new statistics include its `width`,
`height` and `counts`. Existing statistics retain version 2 because the existing fields keep
their meanings.

From https://victrisarena.com/docs/api#position-heatmaps
