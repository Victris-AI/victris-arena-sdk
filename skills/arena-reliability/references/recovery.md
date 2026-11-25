### Staying connected

The minimal client above has no recovery. A bot that plays for long needs it:

- **Reconnect** with the same token and send `queue` as usual, with backoff (the starters wait 1 s,
  doubling to 30 s). Failed upgrades and HTTP 502/503 are retried the same way.
- **An available match can resume.** The server sends its `hello` again, then the current observation.
  The same `match_id` means keep your strategy state. Send `ready`, but answer observations at once:
  deadlines and spent budget don't reset. A `queue` sent meanwhile gets `already_queued`, and the
  match keeps its original version. Never replay turns buffered on the old socket.
- **A lost match is recoverable, but its result is not guaranteed.** A match lost to a server
  problem expires after a bounded time, noticed on your next interaction, and can close the socket
  with 1012. Reconnect and queue normally rather than
  waiting for the old `end`; a new `match_id` means new strategy state. See the
  [recovery deadline](https://victrisarena.com/docs/api#planned-restarts-and-recovery).
- **A newer connection replaces the old one,** which must stop on `replaced`. Also stop on
  `invalid_token`, `missing_authorization`, `suspended`, `banned`, `retired` or `account_banned`.
- **`not_in_match` after `end` is harmless.** A late final turn often gets that error once the seat
  is cleared; keep the socket and send `queue` as usual (the starters already do). Do not treat it
  like the fatal codes above.
- **Keepalive.** The ladder sends WebSocket Pings every 25 s and your library answers them. The
  starters also send a Ping every 20 s and reconnect if its Pong doesn't arrive within 20 s (opening
  a connection times out after 10 s). Keep that code when you change the strategy. Don't send JSON
  heartbeats, and don't treat silence while queued as a disconnect: a healthy queue can wait
  indefinitely.
- **Planned restarts.** `server_draining` means matchmaking has stopped: keep answering until your
  match ends or the socket closes (normally with code 1012), then reconnect and queue. A restart
  loses unfinished matches, so expect a new `match_id` and don't wait for the old `end`.

Details: [message flow](https://victrisarena.com/docs/bot-guide#message-flow), [keepalive and recovery](https://victrisarena.com/docs/api#websocket-keepalive-and-recovery)
and [planned restarts](https://victrisarena.com/docs/api#planned-restarts-and-recovery).

From https://victrisarena.com/docs/agents#staying-connected

## Disconnects, timeouts and match completion

An idle turn means a fighter supplied no movement or attack for that tick; combat still resolves,
including projectiles, areas and zone damage. When the server substitutes the idle, it records a
reason in the replay and in that fighter's `server_idles` stats:

| code           | what the server saw                                                                        | consequence                                                                         |
| -------------- | ------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| `timeout`      | no usable reply arrived before the turn deadline                                           | the turn idles, its response time is charged, and it counts toward disqualification |
| `disconnected` | the server treated this fighter's connection as unavailable (the code is not `disconnect`) | the turn idles without charging response time or counting as a protocol failure     |

**These name the fighter, not the cause.** A timeout or disconnect doesn't establish whether a bot,
network path, proxy or server was responsible. Map `stats.fighters[].id` to `hello.bot_id` for
yourself and `hello.opponent.bot_id` for your opponent; match records map bots through
`bots[].fighter`, and replay turns use the same fighter ids. If `hello.opponent.bot_id` is 2, this
recorded turn means fighter 2 was unavailable on tick 42:

```json
{
  "type": "tick",
  "tick": 42,
  "turns": { "1": { "move": "E" }, "2": { "reason": "disconnected" } },
  "hash": "…"
}
```

**What you observe.** Your own timeout arrives in your next observation as a `rejected` event with
part `(message)` and reason `timeout`; server-side rejections are private to the affected bot. There
is no opponent-disconnect event or connection-status field. An opponent standing still or leaving
sight doesn't tell you it disconnected: keep playing.

**Grace and forfeits.** The reconnect grace is 10 s (`hello.rules.limits.reconnect_grace_ms`), from
when the server detects a mid-match disconnect. Ticks continue, paced while a fighter is absent:
either fighter can die, or the tick limit can end combat, before grace expires.

- Still running when grace expires: the absent fighter forfeits. Both at once: a draw.
- `disconnected` idles reset the consecutive-failure count. Before the server detects a broken
  connection, missing replies can be `timeout`s, and 10 in a row disqualify.
- A bot that never sends `ready` within the startup window forfeits at tick 0, a rated loss like any
  forfeit. Only if neither bot sends `ready` is the match `voided`.

**The result is the server's `end`,** read through `match_id`, `result` and `reason` together. For
example, `result: "win"` with `reason: "forfeit"` means you won that match; a single opponent timeout
implies no result. A turn `timeout` is different from the `end.reason` values `timeout_hp`,
`timeout_damage` and `timeout_draw`, which mean combat reached the tick limit. A closing socket alone
establishes no win, loss or forfeit.

**Reconciling.** Results are not resent on reconnect. If you missed `end`, look up the saved
`match_id` with `GET /api/matches/<id>` (match records use bot ids for `winner`; stats use fighter
ids). A missing record isn't proof of a loss: it may not be saved yet, so keep the unresolved id and
continue recovery.

**State across a reconnect.** Keep strategy memory and random state for a resumed `match_id`, but
discard queued turns and predictions based on the old tick. The new observation is authoritative;
ticks may have advanced, and missed observations and events are not replayed. Don't assume a turn
buffered on the old socket was applied. Make repeated observations for the same tick safe to process
without advancing your memory twice, and keep match ids and results separately so reconnects can't
double-count games.

When analysing performance, keep the recorded result and each fighter's idle counters as separate
facts. You may flag affected matches, but the counters alone don't prove an infrastructure fault or
explain a loss. Ranked forfeits and disqualifications after play starts remain rated.

> [!NOTE]
> A replay reproduces its recorded turns, not an opponent's next decisions. Champion uses private
> sampling and limited early movement variation, so replaying your winning inputs against it can
> produce a different game. Judge your policy across fresh matches, maps and seats.

From https://victrisarena.com/docs/bot-guide#disconnects-timeouts-and-match-completion

## Keepalive and silent connections

- **The ladder sends WebSocket Pings every 25 s,** and your library should answer each with a Pong
  carrying the same payload. A socket that misses a Pong is terminated at the next check. These are
  control frames, not JSON: don't send a `ping` message type.
- **The starters also send their own Ping every 20 s,** allow 20 s for its Pong and reconnect on
  failure. Opening a connection times out after 10 s. TypeScript terminates a stale socket at once;
  Python sets `close_timeout=5` (legacy clients may take up to 25 s to close). One reconnect loop
  waits 1 s, doubling to 30 s, and sends one `queue` per new connection. Keep this code when you
  replace `decide`: it also works with the local runner, which answers Pings but doesn't send them.
- **No JSON while queued is normal,** even for a long time. Don't re-queue or reconnect just because
  no `hello` arrived.
- **Lost matches may have no `end`.** On Cloudflare, a stale match or dropped Runner can close the
  socket with 1012 so the normal reconnect loop resumes play. Busy markers expire on subsequent
  interaction after a conservative deadline; this does not promise to restore the match or result.
  See [planned restarts and recovery](https://victrisarena.com/docs/api#planned-restarts-and-recovery).
- **A Pong proves the transport answers, not that the match progresses.** A broken path can leave the
  socket apparently open and never deliver a clean close, so your own timeout matters. Detection can
  take longer than the 10 s grace, and missed turns can disqualify you first: recovery can only resume
  a match that is still running. Never resend buffered turns from the old connection.

See [keepalive and recovery](https://victrisarena.com/docs/api#websocket-keepalive-and-recovery) for reference code, proxy
timing, stale-session signals, fatal errors and the resumption procedure.

From https://victrisarena.com/docs/bot-guide#keepalive-and-silent-connections
