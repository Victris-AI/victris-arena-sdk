# Victris Arena SDK

[Victris Arena](https://victrisarena.com) is a live, ranked 1v1 arena where you and your AI agent
build battle bots and climb the ladder. Your bot runs on your own computer and connects over a
WebSocket; every match has a replay to learn from.

This repository holds everything public you need to build one:

| Folder                    | What it is                                                                                     |
| ------------------------- | ---------------------------------------------------------------------------------------------- |
| `bots/ts-starter`         | The TypeScript starter bot: connects, queues and fights. Put your strategy in `strategy.ts`.   |
| `bots/py-starter`         | The same starter in Python.                                                                    |
| `bots/random`, `bots/lib` | Random, an easy practice opponent, and its client code.                                        |
| `sim/`                    | The simulator: the ladder's own match code as one JavaScript module, about 100 games a second. |
| `python/`                 | `victris-arena-sim`, the simulator for Python, with Gymnasium and PettingZoo environments.     |
| `skills/`                 | Agent Skills for coding agents: onboarding, combat, the simulator, match review, reliability.  |
| `schemas/`                | JSON Schemas for every message on the bot's socket.                                            |
| `rules/rules.json`        | Every combat number the ladder plays by.                                                       |
| `maps/`                   | The maps the ladder plays, with their spawn points and pickup pads.                            |
| `engine/`                 | The game engine's TypeScript source, to read, port or diff between releases.                   |

It is also a plugin for Claude Code, Cursor and Gemini CLI that connects the Victris Arena MCP
server (`https://victrisarena.com/mcp`) and installs the skills.

This is release 0.93.0. The full guides are on the website:
[agent guide](https://victrisarena.com/guide/agents), [bot guide](https://victrisarena.com/guide/bot-guide),
[simulator](https://victrisarena.com/guide/simulator), [HTTP API](https://victrisarena.com/guide/api) and
[MCP](https://victrisarena.com/guide/mcp).

## Connect your AI agent

The MCP server signs you up, registers your bots and reads your matches and replays. It signs in
through your browser; there is no key to copy.

**Claude Code**

```bash
claude plugin marketplace add Victris-AI/victris-arena-sdk
claude plugin install victris-arena@victris-arena
```

**Gemini CLI**

```bash
gemini extensions install https://github.com/Victris-AI/victris-arena-sdk
```

**Cursor:** add this repository as a plugin, or add `https://victrisarena.com/mcp` as a remote MCP server.

**Any other MCP client:** add `https://victrisarena.com/mcp` (streamable HTTP). Setup steps for each client are at
[https://victrisarena.com/guide/mcp](https://victrisarena.com/guide/mcp).

## Start a bot

Register a bot (through MCP, or on the website's My Bots page) to get its token, then:

```bash
cp -r bots/ts-starter my-bot && cd my-bot
npm install
ARENA_TOKEN=<token> npm start
```

Or in Python:

```bash
cp -r bots/py-starter my-bot && cd my-bot
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
ARENA_TOKEN=<token> .venv/bin/python bot.py
```

The starters connect to `wss://victrisarena.com/bot`. Keep the token in a private environment file, never in
source control.

## Train offline

The simulator plays the ladder's own match code on your machine, against the starter, Random,
your own opponents or itself.

```bash
npm install victris-arena-sim     # JavaScript: import { Game } from "victris-arena-sim"
pip install victris-arena-sim     # Python 3.10+: import arena_sim
```

Both are this repository's `sim/` and `python/` folders, published with each release.

The [simulator guide](https://victrisarena.com/guide/simulator) covers both. A new release can change the rules:
`python -m arena_sim check https://victrisarena.com` says whether your copy matches the ladder.

## About this repository

This repository is a read-only mirror, published with each Victris Arena release from the
project's own source. Pull requests and issues aren't read here: send bugs and ideas through
[https://victrisarena.com/contact](https://victrisarena.com/contact), or the MCP server's `send_feedback` tool.

Released under the [MIT License](LICENSE). What changed in each release is in
[CHANGELOG.md](CHANGELOG.md).
