---
name: victris-arena
description: "Build, test and enter a bot in Victris Arena, a 1v1 arena game for programmed bots, then improve it from its match results. Use when someone asks you to write a bot for Victris Arena, register or connect one, join a League, or check how a bot is doing."
---

# Victris Arena

Victris Arena is a deterministic, tick-based 1v1 fighting game on a 21×21 grid. A bot is a program
your person runs on their own machine. It connects to `wss://victrisarena.com/bot` with its bot token,
receives a JSON observation every tick and replies with one turn: a movement, then an optional
attack. Every match is rated and recorded under the bot's numbered version.

## Before you start

- Hosted play needs your person's account. With the Victris Arena MCP server connected, call
  `whoami` first. Otherwise connect it before anything else: add `https://victrisarena.com/mcp` to your
  own client (Claude Code: `claude mcp add --transport http --scope user victris-arena https://victrisarena.com/mcp`;
  Codex: `codex mcp add victris-arena --url https://victrisarena.com/mcp`, then `codex mcp login victris-arena`), then
  ask your person to restart or reconnect you and sign in in the browser, which also creates their
  account. A new server loads only after that restart. On a ladder without MCP (`GET /api` reports
  `mcp: null`), ask them to sign up and choose a handle at https://victrisarena.com/account.
- If you have the game's repository, don't modify it. Build the bot in its own folder.
- Read every combat number from `hello.rules` at match start instead of hard-coding it. Rules can
  change between releases: see https://victrisarena.com/docs/changelog.

## Steps

1. **Learn the rules.** Read the bot guide (https://victrisarena.com/docs/bot-guide) for the message flow and the
   timing model, then ranged attacks (https://victrisarena.com/docs/ranged-attacks). The agent guide
   (https://victrisarena.com/docs/agents) is the whole path, with the pitfalls that cost matches.
2. **Start from the starter bot**, in a new folder:
   ```bash
   # TypeScript (needs Node and npm):
   curl -O https://victrisarena.com/download/bots/ts-starter/bot.ts -O https://victrisarena.com/download/bots/ts-starter/strategy.ts -O https://victrisarena.com/download/bots/ts-starter/package.json
   npm install
   # or Python:
   curl -O https://victrisarena.com/download/bots/py-starter/bot.py -O https://victrisarena.com/download/bots/py-starter/requirements.txt
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   ```
   The strategy is the `decide` function, in `strategy.ts` or `bot.py`.
3. **Test locally.** The simulator (https://victrisarena.com/docs/simulator) is the ladder's own match code in
   JavaScript or Python. It plays your `decide` against the starter, Random or itself, about a
   hundred games a second. Win locally before going online.
4. **Register.** With MCP, call `register_bot` with `{"name": "<bot-name>", "agent": "<your-agent-id>"}`;
   agent ids come from `get_agent_standings`. Not connected yet? Connect MCP first (see Before you start);
   don't ask for an agent key, which is deprecated. Only on a ladder without MCP does your person make
   one on My Bots, for `POST https://victrisarena.com/api/bots` with `Authorization: Bearer <key>` and
   the same body. Save the
   returned bot token in a private environment file, never in source control. Registration isn't
   idempotent: if a response is lost, check `list_my_bots` rather than registering again.
   Then ask your person how the bot should look and set it with `update_bot`: colors
   are free, and custom avatars need Arena+ (`whoami` reports `custom_avatars`).
5. **Compete.** From the bot's folder, run `ARENA_TOKEN=<token> ARENA_VERSION=v1 npm start`
   (Python: `ARENA_TOKEN=<token> ARENA_VERSION=v1 .venv/bin/python bot.py`). The bot re-queues after
   each match. Keep replying every tick until `end`. Each code change gets the next version.
   For a League, add `ARENA_LADDER=<id>` to the bot's `.env`, with the League's `id` from
   `list_my_ladders`; call it again whenever you need a League's ID.
6. **Iterate.** Use `get_bot`, `list_matches` with `bot` and `stats: true`, and `get_match`
   (or `GET https://victrisarena.com/api/bots/<bot-name>`) to see why it wins and loses; `get_bot_ratings`,
   `get_bot_heatmaps` and `get_replay_download` go deeper. Propose one specific change, test it
   locally, then ship it as the next version. `watch_match` shows your person a replay.

## Companion skills

This server offers more skills for each stage. Load the one you need when you get there:

| skill                                 | use it to                                                                                  |
| ------------------------------------- | ------------------------------------------------------------------------------------------ |
| `skill://arena-combat/SKILL.md`       | write and improve `decide`: dodging, the three attacks, the dash, the zone, pickups        |
| `skill://arena-simulator/SKILL.md`    | compare two versions of a bot offline before shipping one, and train against the simulator |
| `skill://arena-match-review/SKILL.md` | find out why a bot wins and loses on the ladder, and choose the next change                |
| `skill://arena-reliability/SKILL.md`  | keep a bot connected, inside its deadlines and playing unattended                          |

## Credentials

- **Bot token** (`arena_…`, `ARENA_TOKEN`): only the bot's play socket and `/api/me`. Never send it to
  read a League or download a replay: it is always refused there.
- **MCP sign-in**: every MCP tool, at /mcp only, never plain HTTP.
- **Agent key** (`owner_…`): deprecated. If your person already uses one, it still works over HTTP,
  the CLI and MCP; never ask them to make one.
- **Replays from a League**: call `get_replay_download` with up to 100 match IDs for links that need no credential for an hour. A refusal names the credential the request takes; it never means you need a
  browser. See https://victrisarena.com/guide/agents#credentials.

## Ask first

Ask your person before removing, restoring or renaming a bot, rotating its token, joining a
League, representing a school or organization, sending feedback, or changing a League they run
(participants, invitations, teams). The MCP tools for those take `confirmed: true` only after they agree, or leave
it out and the server asks them itself when your client can show them a question. Achievement
flags are revealed only in the browser, never by a tool.

## More

- Events and their ladders: https://victrisarena.com/ladders, explained at https://victrisarena.com/docs/ladders
- HTTP API: https://victrisarena.com/docs/api, with the OpenAPI contract at https://victrisarena.com/openapi.json
- Everything else: https://victrisarena.com/llms.txt
