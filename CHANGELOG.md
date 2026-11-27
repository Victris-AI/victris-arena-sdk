# Changelog

What changed for players in each release of Victris Arena: the rules, the engine, the bot protocol, the simulator, the house bots and the website. Each release lists its versions and what bot authors need to do.

## Unreleased

## 0.95.0 — 2026-11-27

Release 0.95.0 · engine 0.24.0 · rules 0.22.1 · protocol 0.8

**Action for bot authors:** bots need no changes.

### Website

- **Sale codes for yearly plans.** On the League and Arena+ purchase panels, choose **Yearly**, then enter a sale code under **Have a promo code?** to take its discount off your first year. You pay the rest at Checkout as usual, and renewals are at the regular price. A sale code doesn't work on a monthly plan.

## 0.94.0 — 2026-11-27

Release 0.94.0 · engine 0.24.0 · rules 0.22.1 · protocol 0.8

**Action for bot authors:** bots need no changes. League owners: rosters no longer lock; use Admin-assigned to settle teams, and set **Ends** to end a League on a date.

### Leagues

- **End a League and reopen it.** Owners can set when a League ends in its Settings (**Ends**), or choose **End now** on its page. At the end, play stops and the standings are saved as a **Final standings** snapshot beside your other snapshots, outside the snapshot limit. **Reopen**, or a later end time, starts play again: ratings carry on and the Final standings stay. Manual and scheduled snapshots can't use the name Final standings.
- **League teams no longer lock for good.** The Lock rosters button is gone. To settle the teams before official play, set Team participation to Admin-assigned: participants can't change teams themselves, you can still place anyone who joins later, and you can switch back at any time. A League whose rosters were locked now shows Admin-assigned. In the HTTP API, `{"action":"lock"}` answers `invalid_team_request`, and a change to a closed League's teams answers `ladder_closed` instead of `roster_locked`. Over MCP, `manage_league_teams` no longer takes `lock`.

### Agents and MCP

- **A clearer screen for connecting an AI client.** When you connect Claude, ChatGPT or another client, the approval screen now shows where it sends you back, the account it will use (with a way to switch), and what it can do in five short lines: see your account, manage your bots, join and run Leagues, represent your school or organization, and send feedback. It also says what needs your approval and what it can never do. The client ID and scopes are under Details. Nothing changes for clients you've already connected.

### Website

- **Agent, university and organization pages show up in search results.** Search engines were told to skip them, so a search for an agent or a school's standings found nothing. Bot pages also have a shorter search description that fits in a result.
- **Standings pages list their entries without JavaScript.** With scripts off, the leaderboard lists its bots as links, the agent, university and organization boards list theirs, and each agent's or team's page lists its bots, so search engines can follow them to every bot's page.

## 0.93.0 — 2026-11-26

Release 0.93.0 · engine 0.24.0 · rules 0.22.1 · protocol 0.8

**Action for bot authors:** bots need no changes. Protocol 0.8 only adds `hello.engine_version`; clients that check the hello's `protocol_version` should accept 0.8. If your bot copies or ports the engine to search ahead, check `engine_version` at the start of each match, or switch to the simulator's new `forward` model.

### Bot protocol and simulator

- **`hello` names the match's engine.** A new field, `engine_version`, gives the engine version the match runs on, the same as `versions.engine` in `GET /api`. The engine can change in a release while `hello.rules.version` stays the same (0.91.0 changed how pickups are taken under the same rules version). If your bot copies the engine to search ahead, check this field at the start of each match. Bots that don't need it can ignore it.
- **Search ahead with the engine's own tick.** The simulator now has a supported forward model, `forward`, for bots that look ahead. `forward.start(hello)` builds a match's exact first state and `forward.fromObservation(hello, obs, assume)` builds the state your bot sees, with your guesses for what the fog hides. Then `clone`, `step`, `observe`, `options`, `validate` and `hash` let you try candidate turns against likely replies. `game.state()` gives a simulated game's whole state. In Python, `ForwardModel` does the same (`step_many` expands many turns in one call) and `Simulator.state(i)` gives a game's state. If your bot appends an `export` line to `arena-sim.mjs` to reach the engine's internals, switch to `forward`: it is versioned (`forward.api`) and stays stable between releases. See the simulator guide's [forward model](https://victrisarena.com/guide/simulator#look-ahead-the-forward-model). It refuses a `hello` from another engine version.
- **The engine's source is in the SDK repository.** The [Victris Arena SDK](https://github.com/Victris-AI/victris-arena-sdk) now carries the engine's TypeScript in `engine/` and the maps in `maps/`, under the MIT licence, at every release's tag. If you port the engine to another language, read and diff it there instead of unpacking the simulator's source map.
- **The Python package also warns about another engine.** `check_hello`, `Basic` and `ScriptEncoder` raise an `OutdatedSimulatorWarning` when a live match's `hello` names an engine version other than the simulator's, even when the rules are the same.

### Agents and MCP

- **Build a bot from Claude's chat app.** The agent guide has a new section, [Working from a chat assistant](https://victrisarena.com/guide/agents#working-from-a-chat-assistant): a chat app with a code sandbox can write a bot and test it in the simulator, then hand it to you with a launcher you double-click to start it. Create a Bot and My Bots link to it. Building and running a bot still works best in a coding agent such as Claude Code.
- **Agent entries say where each one runs.** In `GET /api/agents` and `get_agent_standings`, each `catalog` entry has a `description`, set where one maker has several entries (Claude Code and the Claude app, Codex and ChatGPT, Google's agents) and null elsewhere, so an agent credits the right one. If your bot was built in Claude's chat app but shows Claude Code, change it to `claude-app` with `update_bot` or on My Bots.
- **`watch_match` plays older matches in the conversation.** A match played on an earlier release used to show only a link to the website in clients that show MCP Apps; it now plays inline like any other.
- **League owners and organizers join the team they create with `join_league_team`.** Before, the team was made but they weren't on it. In the HTTP API, a `create` command joins an organizer to the new team when it sends `"join": true`; teams organizers make for others on the League's page still start empty.
- **`list_my_bots` says which ladder each bot is connected to.** Its new `online_ladder` field is public or a League's ID, or null when the bot is offline. `get_bot` and `get_ladder_status` still say whether a bot is online on the one ladder you ask about, so a bot playing in a League shows as offline on the public ladder.
- **The bot card and leaderboard no longer end in "Loading…".** In clients that show MCP Apps, `show_bot` and `show_leaderboard` drew their contents but left their loading message underneath.

## 0.92.0 — 2026-11-26

Release 0.92.0 · engine 0.24.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** bots need no changes. If your agent uses the Victris Arena MCP server, its tools have new names (listed below) and the old ones no longer work: if you allowed tools by name in your client, allow the new ones.

### Ladder and website

- **Forfeited replays show how they ended.** A replay that ends in a forfeit or disqualification now finishes on its result banner, like a knockout. When a bot wasn't ready before combat began, the replay has nothing to play: the viewer shows the result straight away and its stats name the bot that wasn't ready. Before, pressing play did nothing and gave no reason.
- **New contact address: hello@victrisarena.com.** The contact page, the terms, the privacy policy and replies to our emails now use it. Mail to the old address, hello@victris.ai, still reaches us.

### Agents and MCP

The MCP tools are reorganized into 39 with clearer names.

- **One tool changes a bot: `update_bot`.** It sets a new name, the agent credited, the color or the avatar, in any combination; only a rename needs your approval. It replaces `rename_bot`, `set_bot_agent` and `set_bot_appearance`.
- **`remove_bot` removes a bot.** It deletes a bot that has never played and retires one that has, keeping its history, and always asks first. `restore_bot` brings a retired bot back. They replace `delete_bot`, `retire_bot` and `unretire_bot`.
- **`list_matches` reads back through a League's whole history.** Follow its `next` cursor for older matches, which replaces `list_private_match_history`. New `opponent` and `version` filters show a bot's head-to-head record or one version's games. A page holds up to 30 matches, or 5 with statistics.
- **See charts, standings and bots in the conversation.** In clients that show MCP Apps, as `watch_match` does for replays: `show_rating_chart` draws the bot page's rating chart, `show_leaderboard` the public ladder's or a League's standings with every bot's avatar, and `show_bot` a bot's card with its animated avatar, rating and latest results.
- **Fewer, merged reads.** `whoami` now includes your school or organization and the site's announcements (it replaces `get_my_team` and `get_announcements`). `get_ladder_status` lists each connected bot in full (it replaces `get_lobby`). `list_my_ladders` shows your role in each League and the Leagues you own (it replaces `list_my_leagues`). `get_bot` no longer takes `rating_days`: use `get_bot_ratings`. `get_bot_ratings` returns about 150 points by default and up to 300, without empty fields, so it fits in an agent's reply limit.
- **Renamed.** `join_league` (was `enroll_ladder`), `get_ladder_recap` (`get_ladder_results`), `get_agent_standings` (`get_agents`), `get_affiliation_standings` (`get_teams`, with `affiliation` for one school's domain) and `join_affiliation` (`join_team`). Schools and organizations are now called affiliations everywhere in MCP, so "team" always means a League's team.
- **League tools split by what they do.** `approve_league_participant` and `remove_league_participant` replace `moderate_league_participant` and take a participant's handle. `join_league_team` (join, leave or create) and `manage_league_teams` (organizers) replace `change_league_teams`.
- **The same argument names everywhere:** `bot` for a bot, `match` for a match, and `matches` for `get_replay_download`'s list of up to 100. `get_leaderboard` returns up to 100 bots.
- **Two new prompts:** "How is my bot doing?" and "Check on my League".
- **In the HTTP API, `/api/affiliations` is the new name for `/api/teams`.** Leaderboard rows and bots carry `affiliation`, the school or organization their owner represents. `/api/teams` and the `team` field still work, marked deprecated, and will be removed in a later release.

## 0.91.0 — 2026-11-25

Release 0.91.0 · engine 0.24.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** pickups are now taken by passing through them, not only by ending a move on them. A dash takes every stocked pad it crosses, a repulsor's victim takes the pads it is pushed across, and a pad that restocks under you is yours even if you move off it. If your bot routes to pickups, a dash's whole path now counts (every tile from where you stand to `observation.dashes[].tile`); think twice before shoving an enemy across a pad. Install this release's simulator to practise with the change.

### Engine

- **Dashing through a pickup takes it.** A dash collects every stocked pad it enters on the way, its landing tile included; before, it passed over pads and only the landing tile counted. When two fighters dash across the same pad on one tick, the one that reaches it first takes it, and if both would reach it on the same step, both stop one tile short and neither takes it. A dash that crosses a pad also beats a fighter stepping onto it that tick.
- **A repulsor's victim takes the pads it is pushed across**, as it reaches each one. Health taken on the way counts before a wall slam at the end of the push; a fighter the hit already knocked out takes nothing. Power taken this way boosts the victim's shots and frostbursts later that tick, but not a repulsor fired the same tick.
- **A pad that restocks under you is yours as the tick begins**, whether you stay, step or dash off it. Before, you had to stand still that tick to take it.
- Replays recorded with an earlier engine need that engine to verify, and may diverge if re-simulated with this one.

### Bot protocol and simulator

- The simulator installs from the package registries: `npm install victris-arena-sim` or `pip install victris-arena-sim`, published with each release. The simulator guide shows how to pin one to the ladder's release; the download links still work.
- The reinforcement learning page's install line works again: it installs `victris-arena-sim[sb3]`. The old line named the package's previous name and pip refused it.

### Agents and MCP

- The MCP guide shows how to install the Victris Arena plugin for Claude Code (`claude plugin marketplace add Victris-AI/victris-arena-sdk`) and Gemini CLI, which add the MCP server and the Agent Skills in one step. `/llms.txt` names the plugin and the public SDK repository too.

### Ladder and website

- The home page and guide footers link to the SDK on GitHub.

## 0.90.0 — 2026-11-25

Release 0.90.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none for bots. If you train with the Python simulator, switch to the new package name: `pip uninstall arena-sim`, then install `victris-arena-sim` (your code still imports `arena_sim`).

### Bot protocol and simulator

- **The Python simulator is now `victris-arena-sim`** (it was `arena-sim`). You still `import arena_sim`, and its environments and functions are unchanged. If you have the old package, run `pip uninstall arena-sim` before installing the new one, since both install `arena_sim`. Downloads of earlier releases keep their old file names.
- The starter bots, the simulator in JavaScript and Python, the Agent Skills and schemas are on GitHub at [Victris-AI/victris-arena-sdk](https://github.com/Victris-AI/victris-arena-sdk), under the MIT License, updated with each release. It also installs as a plugin for Claude Code, Cursor and Gemini CLI that connects the Victris Arena MCP server.

### Agents and MCP

- `list_snapshots` takes a `ladder` and lists a League's snapshots; `get_leaderboard`, `get_teams` and `get_agents` take one of them as `snapshot`. On the HTTP API, add `?ladder=<id>` to `/api/snapshots` for the same.

### Ladder and website

- **Bot rating and rank charts show much more history.** All now covers your bot's whole time on the ladder, back to its first game, not just the last 30 days, and the time frame buttons read 1D, 1W and 1M, with 3M and 1Y added once your bot has played that long. Every frame is drawn as finely as it can: a day shows each game, longer frames show runs of games with their lowest and highest rating. Open the chart's large view with its expand button for more detail and your record, peak rating and best rank for the stretch shown, then drag across the chart to zoom in, down to each game for the past month; **Zoom out** goes back. `GET /api/bots/<name>/ratings` takes `since`, `until` and `points` (100–5,000) to read any stretch, and MCP's `get_bot_ratings` takes the same.
- **Leagues can save snapshots of their standings.** A League's owner, and its organizers on Premium, can open **Snapshots** to save the board now or at set times, once or every day or week ("Week 1", "Week 2"…), so a class can look back on each week and a hackathon on each round. Members pick a snapshot from the standings switcher on the League's leaderboard, with its report, matchups and, when the League has teams, its team standings. Play goes on and ratings never reset.
- Links in the guides and release notes that led to a page players couldn't open now go to the matching guide, and the API and spec guides no longer link to the tutorial's source notes. The tutorial itself is still at `/tutorial`.
- The home page's online and live counts now cover every ladder, Leagues included: each bot online counts once, and League house bots don't count. `GET /api/status` on the public ladder gives these totals as `all_ladders`.

## 0.89.0 — 2026-11-24

Release 0.89.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- A League's home page now shows everyone the `ARENA_LADDER=` setting that sends bots there, with its Copy button, and a League with a player limit shows a bar of how many spots are taken and how many are open. The League's leaderboard no longer repeats the setting above its standings; open **League home** to find it. `GET /api/ladders` gives the spots taken as `players`.
- On the leaderboard, the ladder, board and month menus moved out of the header into the row with the search box, just above the panels. The Universities, Organizations, Agents and League Teams boards have their board menu in the same place, at the top of the page. On a phone, the month menu now opens across the screen, so past months are easier to read.
- The home page menu now starts with **Create a Bot**, followed by the Tutorial and the leaderboard. The panel beside the menu is gone, so the house bots' match behind it is easier to see.

## 0.88.0 — 2026-11-23

Release 0.88.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. To keep a ranked bot's full score, keep it online (queued or playing) at least 4 hours a day.

### Ladder and website

- **Staying on the leaderboard now means staying online.** A ranked version keeps its whole score while it is queued or playing on that ladder for 4 hours in every 24, and a day away costs nothing. After that its score drops, by up to 400 points after three days away, so a bot that goes offline can no longer hold a top place. Only time online earns it back, at 50 minutes an hour, and playing one game a day doesn't count as being online. This replaces the old idle penalty, which counted hours without a rated game and was earned back 10 points a game. The new `online_owed_hours` field on the leaderboard, lobby, bot and profile APIs says how much online time a version owes, and the Score's tooltip says it too. To keep your place, leave your bot connected and queued.
- The match playing behind the home page is sharp and bright, without the scanlines, fog and embers that dimmed it.
- Pages and emails now say Victris Arena where they meant the site, such as "your Victris Arena account".
- League plans are now called **Standard League** and **Premium League** everywhere: on the purchase form, in your League's billing panel, and at checkout and on receipts, as "Victris Arena Premium League — 20 players".

### Agents and MCP

- Setup commands on Create a Bot, My Bots, the agent guide and `llms.txt` now add the MCP server as **victris-arena** instead of arena, so it shows under that name in your agent's server list. A server you already added as arena keeps working; nothing to change.

## 0.87.0 — 2026-11-22

Release 0.87.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- **Create a Bot is a short walk-through.** It shows one step at a time: create your account or sign in, choose your coding agent, add Victris Arena to it, copy the first task, then open your profile to watch your bot arrive and play. It now covers Claude Code, Codex, Antigravity, OpenCode, GitHub Copilot (VS Code or Copilot CLI) and Grok Build (formerly Cursor, or the Grok Build CLI), with **Add to VS Code** and **Add to Grok Build** buttons, plus the address for any other agent. The fight, the messages and the starter bots moved to a new page, How bots work.
- Your profile page shows who can see it in a slim bar at the top, with an **Only me / Everyone** toggle to change it right there. My Bots → Profile uses the same toggle in place of the Share my profile page checkbox.
- **Leaderboard** in the menu goes back to the leaderboard you were on in this tab. After opening a League's match, replay or League home, or a guide or your account, it returns to that League's leaderboard instead of the public ladder. Away from the leaderboard it shows the League's name, so you can see where it goes.
- League pages now look different from the public ladder. A League's leaderboard, bots, matches and home page are lit in the League's brand colour, or in violet for a League without one: the header line, panel corners and header glow, and the ladder switch, which has a pennant. The public ladder keeps its amber and has a globe on its switch.

## 0.86.1 — 2026-11-21

Release 0.86.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Agents and MCP

- The MCP server describes Victris Arena in new words: AI applications such as Claude show them when you connect it, and its website link now opens the home page.

### Ladder and website

- In a private League, clicking a bot's agent opens the agent's page again instead of an error asking you to sign in. Agent pages show the public leaderboard's standings.
- The footer under the guides and the public pages is redrawn to match the rest of the site: each group of links sits on its own row under a small label.

## 0.86.0 — 2026-11-20

Release 0.86.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. If you read match or leaderboard appearances over the API, `asset_version` can now be 2.

### Ladder and website

- Eight new animated avatars: **Knight** raises its visor to swear its oath again, **Glitch** wears a hoodie and a terminal for a face that tears now and then, **Kraken** curls six arms that reach out as it winds up, **Inferno** is a living flame that streams back as it moves, **Golem** is a block of rock whose runes flare before it strikes, **Voyager** fogs its space helmet's visor, **Mantis** raises its forelegs to strike and clicks its jaws, and **Slime** wobbles, squashes when hit and still has a sword inside. Pick one on My Bots, or with `set_bot_appearance` over MCP; like every custom avatar they need Arena+. `PUT /api/account/bots/<name>/avatar` accepts `knight`, `glitch`, `kraken`, `inferno`, `golem`, `voyager`, `mantis` and `slime`.
- The first twenty avatars are redrawn to fight like the new ones: each reacts in its own way as it winds up, takes a hit or moves. Ronin's eyes narrow and burn red as it draws, Reaper's scythe sweeps up behind it, Sentinel locks on with a targeting reticle, Shade vanishes in a puff of smoke when struck, Wyrm builds fire behind its teeth, and Monarch's crown is knocked off its head. Several gained new details: Monarch's cape, Alpha's ruff, Corsair's plume and Luchador's mask laces, and Berserker now scowls. Every avatar moves smoothly between poses: a windup, a hit or a stun eases in and out instead of snapping, and quick shakes and flickers are gone. Past matches and replays show the redrawn art too, still wearing the avatar and colour each was played in. New match and leaderboard appearances record `asset_version` 2; earlier ones keep `asset_version` 1.
- Every League now has its own page, linked from Browse Leagues and from its leaderboard: what the League is, when it runs, how to join, and an About section where its organizers can write the rules, prizes and schedule. Organizers edit it right on the page and see each change before saving. A Premium League's brand colour, headline and welcome message now appear on this page instead of on the leaderboard.
- The leaderboard page has one filter for all its panels. Signed in, choose **My bots** to see only your own bots on the leaderboard (at their real rank), in recent matches, in games being played and online, or **All** for everyone; this browser remembers the choice. The search box next to it narrows every panel by bot name, owner, version, map or mode.
- Signed in, the leaderboard chart flies a flag over each of your bots, with its rank, name and score, so you can find them among everyone else's. Flags stay clear of each other, even for bots side by side on the same score.
- The privacy policy now explains what happens when you connect an AI application such as Claude over MCP: what it can see and change, and how disconnecting it on your account page ends its access.

## 0.85.1 — 2026-11-19

Release 0.85.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

This release has no player-facing changes.

## 0.85.0 — 2026-11-19

Release 0.85.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. If you read a bot's rating history over the API or MCP, each game and run now also carries the bot's leaderboard place (see Agents and MCP).

### Agents and MCP

- Each game and run in `GET /api/bots/<name>/ratings` `points` (and MCP's `get_bot_ratings`) now has `rank`, the bot's place on the leaderboard after it, or null while the bot wasn't ranked. Runs also have `rank_best` and `rank_worst`. Games played before this release have null ranks; the nightly `ranks` still cover them.

### Ladder and website

- **The Rank chart follows every game.** On a bot's page, Rank now shows where the bot stood on the leaderboard after each of its latest 1,000 rated games, then in runs of 10 and 100 older games with their best and worst place shaded, just as the Rating chart shows its rating. Hover a game to see who it played; click it to open the match. Days before this release still show one place a night.
- **Bot charts open on the last day.** On a bot's page, the Rating and Rank charts now start on Day; pick Week, Month or All to look further back, and bot pages keep the one you picked next time.

## 0.84.0 — 2026-11-19

Release 0.84.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. Agent keys are deprecated but keep working; if your agent connects to MCP with one, you can switch to signing in (see Agents and MCP). A League player's bot queues there with `ARENA_LADDER=<id>`, now shown under **My Leagues**.

### House bots

- The lobby and League settings now label Starter as Easy and Kiter as Hard, matching how they actually play against the field. Brawler stays Medium and Champion Very hard.

### Agents and MCP

- **Connecting a coding agent is one step.** Create a Bot has a tab for Claude Code, Codex, Cursor and VS Code with the command (or, for Cursor, an Add to Cursor link) that adds Victris Arena, and what to do to sign in. My Bots shows the same commands under Connect an AI agent. Signing in is also where you create your account.
- **The task prompt starts from scratch.** If your agent isn't connected yet, the prompt on Create a Bot and My Bots has it add Victris Arena to itself, ask you to restart or reconnect it and sign in, and wait, instead of switching to the HTTP API or asking for a key. `/llms.txt` and the agent guide tell agents the same.
- In Claude Code, add Victris Arena with `--scope user` (`claude mcp add --transport http --scope user arena https://victrisarena.com/mcp`) so it is there in every folder, including a new bot's.
- **Agent keys are deprecated.** Keys you already have keep working over the HTTP API, the CLI and MCP until you revoke them. New setups connect a coding agent with OAuth: My Bots offers to make a key only if your account already has one. At `/mcp`, a key's responses now carry a `Deprecation` header and `whoami` returns a `credential_notice`. To switch, remove the `Authorization: Bearer owner_…` header from your client's setup for Victris Arena, reconnect and approve access in the browser; your bots, tokens and history are unchanged.
- **Rename a bot from MCP.** New tool `rename_bot` renames one of your bots between matches, keeping its token, versions, ratings and match history; the old name is freed at once. Your agent asks you first (or your client asks you for it). Agents can rename 5 bots a day per account; after that, rename on My Bots.
- **Download many replays at once.** MCP's `get_replay_download` takes `ids`, up to 100 match IDs, and returns a link for each match you may download in `links`, with the others and why in `refused`. Fetch them in a script instead of making one call per match. `id` for a single match works as before.
- Replay and statistics download links from `get_replay_download` now last an hour instead of 15 minutes. Access is checked when the links are made, so a link keeps working until it expires.

### Ladder and website

- **Find your League's `ARENA_LADDER` again.** Each League you play in now shows its `ARENA_LADDER=<id>` line with a Copy button under **My Leagues** in your account, above its leaderboard and on its Manage page, not only when you join.
- A League you started but never paid for now has a **Remove** button in My Leagues, so abandoned purchases no longer stay in your list. It appears once the League's Checkout has closed. Over the API, it is `DELETE /api/account/leagues/<id>`.
- Got a promo link for a League or Arena+? Open it and the plan and code are already filled in: sign in if asked, then select **Redeem code**. A League link shows what the code gives before you sign in; to pay normally instead, select **Don't use this code**.
- Starting a League now suggests a name for it, so you can go straight to checkout. Select **Suggest another name** for a different one, or type your own. You can rename a League any time in its settings.
- A bot that queues with a version it already registered, on another ladder or League, on the website or through MCP, now plays it instead of getting a `version_limit` error saying the version already exists.
- The replay viewer no longer stops a replay with "Public recording access could not be verified" after a brief error. It stops only if your access is refused or the check keeps failing.

## 0.83.0 — 2026-11-18

Release 0.83.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. If your tooling reads `definitions["<name>"]` from a file under `/docs/schema/`, read the file itself instead, and match a refused frame's `code`, not its message.

### Bot protocol and simulator

- The JSON Schema files under `/docs/schema/` are now one flat schema each, with its `title` and `$schema` at the top, instead of a `$ref` into `definitions`. They accept and refuse the same messages as before. If your tooling read `definitions["<name>"]`, read the file itself instead.
- When the ladder refuses a malformed frame, the `schema` error's message is worded differently (for example `tick: Invalid input: expected int, received number`). The `code` is unchanged; read the code, not the message.
- A turn's `tick` and attack `target` must be whole numbers no bigger than 9007199254740991. A larger one is now a `schema` error rather than a reply for the wrong tick.

### Agents and MCP

- MCP speaks protocol revision 2026-07-28: clients that support it connect without a handshake and call `server/discover` to learn about the server. Clients on earlier revisions keep working unchanged.
- On 2026-07-28, list results, the agent skill and `server/discover` carry `ttlMs` and `cacheScope`, so your client can reuse them for 10 minutes. `skills/list` and `skills/get` follow the final Skills extension.
- The MCP server card moved to `/mcp/server-card`, in the current Server Card format: name, version, description, icon, endpoint and protocol versions, without the tool list (call `tools/list` once connected). `/.well-known/ai-catalog.json` points to it, and the old `/.well-known/mcp/server-card.json` address serves the same card.
- Four new Agent Skills, over MCP (`skills/list`, `skill://<name>/SKILL.md`) and at `/.well-known/agent-skills/`: `arena-combat` (how to write `decide`: dodging, aiming, frostburst traps, slams, the dash, the zone), `arena-simulator` (compare a changed strategy with the shipped one before releasing it, with ready-made `compare.mjs` and `compare.py` scripts), `arena-match-review` (find out why a bot loses and choose the next change) and `arena-reliability` (deadlines, reconnecting, running unattended). Skills with more than one file are listed in the discovery index as `.tar.gz` archives. `arena new-bot` puts the same skills in the new bot's folder (`.claude/skills/` and `.agents/skills/`).
- New MCP tool `watch_match`: ask your agent to show you a match and clients that display MCP Apps (such as Claude and ChatGPT) play the replay inline in the conversation, with play, pause, scrubbing and speed. Other clients get the match and a link to watch it on the website.
- MCP has two prompts, which clients show as slash commands: `build_bot` (build, test, register and run a bot, then review its first matches) and `review_bot` (explain one of your bots' recent matches and propose one change; its `bot` argument completes from your bots).
- On protocol 2026-07-28, MCP asks you directly before a change to your account or League (retiring, unretiring or deleting a bot, replacing its token, joining a ladder or a team, sending feedback, or changing a League's participants, invitations or teams), when your client can show you a question and the agent leaves `confirmed` out. Declining changes nothing (`not_approved`). Agents can still send `confirmed: true` after asking you; without it and with no way to ask, those tools now return `confirmation_required`. A custom avatar without Arena+ opens the pricing page for you, if your client can open links, and goes through once you have it.
- An MCP request without credentials is told which scope to ask for (`scope="openid"` in `WWW-Authenticate`).
- **Download a League's replays from MCP.** New `get_replay_download` gives a match's replay and statistics links that work for 15 minutes with no credential, for League matches you may read and public matches in your replay window. `get_match` on a League match now says how to download it.
- **Clearer refusals for the wrong credential.** A bot token, MCP sign-in or agent key sent where it doesn't work now gets a refusal naming the credential that request takes (`bot_token_not_accepted`, `mcp_token_not_accepted`, `agent_key_not_accepted`, `session_not_accepted`, `invalid_key`), with a link to the new [credentials](https://victrisarena.com/guide/agents#credentials) table, instead of being asked to sign in. The bot token only connects your bot; it never opens a private League.
- **More MCP tools.** `get_bot_ratings`, `get_bot_heatmaps`, `get_lobby`, `get_ladder_status`, `list_snapshots`, `get_changelog` and `get_announcements` read what the website shows. `rotate_bot_token` replaces a lost or leaked token, and `send_feedback` reaches the team, both after you approve.
- **Run a League from MCP.** `list_my_leagues`, `get_league_participants`, `moderate_league_participant`, `list_league_invitations`, `create_league_invitation`, `revoke_league_invitation`, `get_league_report`, `get_league_teams` and `change_league_teams` let an agent help owners and organizers, with your approval for each change.
- **Pricing and Leagues in Markdown.** Send `Accept: text/markdown` to `/pricing` or `/leagues`, or read `/pricing.md` and `/leagues.md`: the same plans, sizes and prices as the pages. `/llms.txt` links them.

### Ladder and website

- You're now a member of a League you create as soon as it's activated, so you no longer have to join it before your bots can play there. You don't use up one of its player seats. If you already run a League, you become a member of it too, unless you removed yourself.

## 0.82.2 — 2026-11-17

Release 0.82.2 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

This release has no player-facing changes.

## 0.82.1 — 2026-11-17

Release 0.82.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. If you read `GET /api/bots/<name>/ratings`, its hourly points are gone: it lists recent games one by one again, older games in runs with `low` and `high`, and a new `ranks` list. A name or other text with profanity or slurs is now refused when you save it, so pick different wording.

### Ladder and website

- A bot's rating chart shows every game again: each of its latest 1,000 rated games is a point, so you can hover it to see who it played and click it to open the match. A bot that has played fewer games has every game shown. Older games appear in runs of 10, then of 100 further back, each shaded from its lowest to its highest rating so swings still show; hover a run for its record. Days before those show one point at the end of each day.
- The chart has a new **Rank** view: where the bot stood on the leaderboard at the end of each day, and where it stands now. Switch between **Rating** and **Rank** above the chart.
- `GET /api/bots/<name>/ratings` lists the latest 1,000 rated games one by one again, then older games in runs of 10 and 100, each with `low` and `high`; it no longer has points for hours of play. It also returns `ranks`, the bot's `rank` and `score` at the end of each `day` it was ranked.
- Names and text other players can see can no longer contain profanity or slurs: handles, bot names, the agent you name for a bot, version labels, aliases and notes, and League names, descriptions, branding, team names and share titles. If something is refused, the message says which one to reword. Names you already have keep working.

## 0.82.0 — 2026-11-17

Release 0.82.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

This release was never deployed; its changes shipped in 0.82.1.

## 0.81.1 — 2026-11-16

Release 0.81.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

This release has no player-facing changes.

## 0.81.0 — 2026-11-15

Release 0.81.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. If you read `GET /api/bots/<name>/ratings`, a point with no `match_id` can now stand for an hour of games: its `games`, `wins`, `losses` and `draws` say how many.

### Ladder and website

- Five new pages explain what you can do here: [train a reinforcement learning agent](https://victrisarena.com/reinforcement-learning), [benchmark your AI coding agent](https://victrisarena.com/ai-coding-agents), run a League [for your company](https://victrisarena.com/leagues/companies) or [for your school](https://victrisarena.com/leagues/schools), and [host a bot programming hackathon](https://victrisarena.com/hackathons). The site's footers link all five.
- A bot's rating chart now covers the whole of the Day, Week or Month you pick, not just its latest games. Each hour of play is one point, spaced by how many games it held, so time offline takes no room; hover an hour to see its record. The axis marks where each hour or day begins, the newest games appear one by one as they're played, and the hover card shows next to the point again. `GET /api/bots/<name>/ratings` returns these points, each with `games`, `wins`, `losses` and `draws`.

## 0.80.1 — 2026-11-15

Release 0.80.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- The Leagues guide is rewritten for players: joining and queueing in a League, running one, League teams, and university and organization standings, all at the same address.
- Every guide now ends with a next step for what you just read, and the guides page opens with four ways in: have an AI build your bot, code it yourself, train a model, or run a League.
- The About page explains what Victris Arena is for and how people, AI agents, teams and classrooms use it.
- The Spec and the other guides are shorter and stick to what players and bot authors need: the replay window, Arena+ and Premium Leagues, and the error codes your client can see.

## 0.80.0 — 2026-11-15

Release 0.80.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. Agents can now set a bot's look, and `arena_sim.download_replays` stops at the free replay window instead of failing.

### Agents and MCP

- AI agents can now set a bot's color and avatar with the new `set_bot_appearance` tool. Colors are free; custom avatars need Arena+, just as on My Bots. `whoami` now reports `custom_avatars`, so an agent knows which looks it can offer. Connections that already allow account actions can use it without reconnecting.

### Simulator

- `arena_sim.download_replays` stops a bot's list at its first match outside the free replay window (each bot's newest 200 public matches) and warns, instead of stopping with an HTTP 403 error. With `cache`, it remembers that refusal, so a rerun doesn't ask about the same match again.

### Ladder and website

- The leaderboard's month picker gets each new month again, with its final standings, report, opponent chart and team and agent standings. November arrives in early December. A bot's page lists its place in each month.
- Watch Live keeps playing when a replay briefly can't load, instead of skipping through every recent match at once.
- A brighter glint now sweeps across the home page's Victris Arena title, and small stars twinkle on the letters as it passes.
- Profile pages are private for new accounts. Turn on **Share my profile page** under **Profile** on your account page to show yours; until then only you can open it, and your handle beside your bots isn't a link. Profiles made before this stay shared, and you can hide yours the same way. Your bots and their records stay on the leaderboard either way.
- A shared profile shows each bot's record on every ladder, Leagues included, as totals only. On the public ladder, a shared owner's bot pages also list versions played only in Leagues, by version number. The account API has `PUT /api/account/profile-sharing` and `profile_shared`; `GET /api/users/<handle>` adds `combined` to each bot and answers `404 profile_private` for a private profile.
- The privacy policy now explains how the site counts page visits, without cookies.

## 0.79.4 — 2026-11-14

Release 0.79.4 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- The announcements bell is now always in the header, so the page no longer jumps on phones when announcements load. With nothing published, its tray says so.

## 0.79.3 — 2026-11-14

Release 0.79.3 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

This release was never deployed; its changes shipped in 0.79.4.

## 0.79.2 — 2026-11-14

Release 0.79.2 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- The home page now writes Victris Arena on one line, and its motto, "Play with AI before you work with AI", is larger and framed by gold rules instead of sitting on a dark band.
- The fighters' introduction before a replay now stays up twice as long, about five seconds, so there's time to read both corners' names, ranks and records before the fight. Watch Live now opens every match with it too; it plays through there, with no Skip button.
- Pages no longer jump around while they load. The header, its buttons and Sign in or your account menu appear in place at once, and figures still on their way (the leaderboard's counts, team and agent standings, a replay's fighter cards) hold their places with placeholders until they arrive. Below 1,500 pixels wide, the leaderboard header leaves out the online and live counts so it fits on one row; the Live and Online panels still show them.

## 0.79.1 — 2026-11-14

Release 0.79.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- Downloading or watching a public match's replay, or reading its stats, no longer sometimes fails with "Public recording access could not be verified; retry shortly" while its bots are playing.
- A replay now opens by introducing its fighters: each one sweeps in from its corner with its portrait, name, current ladder rank and record, a VS slams down between them, and then the match plays. It lasts under three seconds; press Space or click it to skip straight to the fight. With reduced motion turned on, the card shows still for a moment instead.
- While a replay link loads, the replay viewer now shows a loading screen instead of asking you to drop a replay file. Opening the viewer with no replay still shows where to drop one.

## 0.79.0 — 2026-11-14

Release 0.79.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. Tools that poll the public ladder can read its new live feed instead (see "The public ladder's live copy" in the API guide).

### Ladder and website

- Every League is now private. Its standings, matches and replays are only for its owner and members, and the public never sees it listed anywhere. Unpaid Leagues saved before Leagues became private are private now too, so a promo code or plan can be bought for them; until now they were refused because their history was public.
- The **List in Browse Leagues** setting is gone. Members always see their Leagues in their League lists and leaderboard menus, including Leagues that were unlisted before.
- Starting a League on the Leagues page reuses only a private unpaid League of yours with the same name.
- The header's account link is now a menu at its far right. Signed in, it shows your picture and handle; open it for My Bots, My Leagues, Arena+, your settings, your public profile and Sign out, from any page. Signed out, it says Sign in.
- Feedback is now in that account menu when you're signed in, instead of an icon beside the notifications bell. Signed out, it's the last link in the header's navigation.
- Choose which of your bots' portraits is your picture under **Profile** on your account page. It shows in the header and leads your public profile. Until you choose, it's your oldest active bot. The account API has `PUT /api/account/profile-bot`, and `profile_bot` in your account and on public profiles.
- Public `/api/status` now says where the public ladder's live copy is: one feed with the leaderboard, newest matches, status and lobby, and each public match's replay for about an hour after it ends. Neither counts against your API request limit. See "The public ladder's live copy" in the API guide.

## 0.78.4 — 2026-11-13

Release 0.78.4 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- When a League or Arena+ purchase can't start for a reason you can fix, such as a League that needs its join password set first, the purchase panel now says so instead of saying billing is unavailable.

## 0.78.3 — 2026-11-12

Release 0.78.3 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- Fixed promo codes for yearly League and Arena+ plans. Redeeming one said billing was unavailable. It now opens checkout with the first year free. If you saw that error, enter your code again.

## 0.78.2 — 2026-11-12

Release 0.78.2 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- Fixed League house bots stopping after one game each. A player bot that had played every house bot in its League waited forever for its next match. It now plays them again after the usual short pause between rematches.
- The leaderboard no longer says "No games played yet" when games have been played but no bot has enough of them to be ranked. It now says how many rated games a bot needs on that ladder. `GET /api/status` reports that number as `qualifying_games`.

### Agents and MCP

- `list_my_bots` now shows a bot as online when it's connected to a League. Before, it counted only connections to the Public ladder.

## 0.78.1 — 2026-11-12

Release 0.78.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. This release includes the changes from 0.78.0, which didn't finish deploying.

## 0.78.0 — 2026-11-12

Release 0.78.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- Leagues now have house bots, so players get matches even when few others are online. A new League starts with Starter, Brawler, Kiter and Champion. Owners and organizers can choose any of the house bots, M-Bot included, under **House bots** in the League's settings, up to four at once, and change them at any time, even while the League runs. Each house bot is rated in the League on its own, so its public rating doesn't carry over. Leagues that are already running get the four defaults.
- The website no longer signs you out about an hour after you open a page. Leaving My Leagues or the ladders page open, or in a background tab, used to end your sign-in in every tab. If your connection drops while your sign-in renews, the page now says so and recovers on its own.
- Emails now come from Victris Arena at `noreply@victrisarena.com`, instead of Arena Fighter at `noreply@victris.ai`.

## 0.77.0 — 2026-11-11

Release 0.77.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- League owners can now offer more than one way in. Invitations always work, and **How players join** in a League's settings adds a shared join password, join requests, or both. A player gets in by any one of them.
- One invitation link can now be shared with a whole community. When you create a link in **Invitations**, choose how many people can use it (one person up to 100, or no limit), when it expires (a day, a week, a month or never), and an optional label only organizers see. A link can also ask you to approve each person who uses it. Shared links stay in the list with how many times they've been used, so you can copy them again or revoke them. Revoking a link doesn't remove anyone who already joined.
- **Participants** shows how each player joined: which link, an invitation, the password or a request.

## 0.76.2 — 2026-11-11

Release 0.76.2 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- A League or Arena+ bought since 0.76.0, including one started with a promo code, could stay on **Checkout open** after checkout went through. It now finishes on its own; you don't need to buy again.

## 0.76.0 — 2026-11-11

Release 0.76.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- **Arena+ is here.** Subscribe from **Arena+** on your [account page](https://victrisarena.com/account#arena-plus), monthly or yearly, for animated personas for your bots and replays, stats and history search for each bot's newest 1,000 public matches. Free accounts keep each bot's newest 200. Custom avatars now need Arena+; accounts made before 11 November already have it. The [Terms](https://victrisarena.com/terms) cover Arena+.
- A new [Pricing page](https://victrisarena.com/pricing) shows what's free, what Arena+ adds and what Leagues cost, side by side. It's linked from the title screen's footer.
- Got a promo code for a League or Arena+? Select **Have a promo code?** when you start a League (on the Leagues page or in My Leagues), on its Billing section or on the Arena+ panel. The code picks the plan and size, and checkout asks for no card. When the free months end, so does the plan, unless you add a card in **Manage billing in Stripe** and keep it.

## 0.75.1 — 2026-11-11

Release 0.75.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. If your agent reads MCP tool errors, read the `{"code","error"}` JSON from the text content.

### Ladder and website

- Start a League right on the [Leagues page](https://victrisarena.com/leagues#start): pick monthly or yearly, Standard or Premium and a size, see the price, name your League and continue to payment. You can set it up before signing in, and your choice is still there when you come back. **Start a League** in **My Leagues** now opens this form, and backing out of Stripe's checkout returns to it with your League saved.
- The top-left corner of every page now reads **Victris Arena** and still takes you back to the main menu. Before, it changed to the page's name, such as Account, Leagues or Replay.
- A bot's page has a **Play history** button above its recent matches. It opens the replay viewer and plays those matches one after another, newest first, moving on a few seconds after each one ends. Use the arrows beside the match number, or the N and P keys, to skip to an older or newer match.
- **Play Game is now the Tutorial.** The title screen's first entry opens [/tutorial](https://victrisarena.com/tutorial): ten short animated chapters, narrated by Sage the owl, that show how bots fight on the real engine: ticks and turns, movement, the dash, each weapon, pickups, sight, the storm and how matches are won. Turn on **{ } Turns** to see each bot's turn as the JSON it sent, and every chapter ends with what to remember and the same rule as a bot writes it. Playing a bot by hand is gone; `/play` now opens the tutorial.
- The HTTP API answers `HEAD` like `GET`, with the same status and headers and no body: `/api/*`, `/api/me` with a bot token, your account's reads and the OAuth discovery documents. Before, `HEAD` returned 404 or 405.
- Pages, images and downloads answer `HEAD` requests, so link checkers see them as working. Before, every one returned 404.

### Agents and MCP

- Every MCP tool now declares an output schema for its result.
- A failed MCP call puts its `{"code","error"}` JSON in the text content only, with no structured content. Read the code from the text. Before, the TypeScript MCP SDK's client rejected these errors from `get_bot`, `get_match`, `get_leaderboard` and `get_ladder_results` as not matching the tool's schema.

## 0.74.0 — 2026-11-10

Release 0.74.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- League subscriptions are open. Select **Start a League** in **My Leagues**, pick League Standard or League Premium, a size from 20 to 2,000 players and monthly or yearly billing, and pay at Stripe's checkout to start it. Everything else is on the League's page once it's paid for, and Leagues you already saved stay in My Leagues. A League can move to a larger size or to Premium later. The [Leagues page](https://victrisarena.com/leagues) lists every price, and the [Terms](https://victrisarena.com/terms) and [Privacy Policy](https://victrisarena.com/privacy) now cover paid plans.
- **My Leagues** is now one short list of every League you play in, own or help run. **Manage** opens a League's own page, with a breadcrumb back to the list and one section at a time: Settings, Invitations, Participants, Report and the rest.
- League owners and organizers can change a running League's name, description, image, listing, join method and join password without deactivating it. Players see the change within seconds.

## 0.73.5 — 2026-11-10

Release 0.73.5 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- The bot health notice, sent when a bot is disqualified in three games within half an hour, now arrives. Before, a disqualification held back that match's result, replay and stats.

## 0.73.4 — 2026-11-10

Release 0.73.4 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** if your bot or agent follows a ladder's `history_url`, read `GET /api/ladders/<id>/history` instead. Nothing else is required.

### Ladder and website

- Some matches played since 2 November may appear in Ladder results late, with their replays and stats.
- Private Leagues no longer have a **Match history** button or a `view=history` page, and the ladder catalog no longer returns `history_url`. Bots and agents read a League's older matches with `GET /api/ladders/<id>/history` or the MCP tool `list_private_match_history`, and old replays still play in the replay viewer.

## 0.73.3 — 2026-11-10

Release 0.73.3 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- League owners have a **Participants** panel in **My Leagues**. It shows members against the League's capacity, waiting requests, bots online and matches running. From it, owners can admit, remove (with a reason the player sees) and reinstate members. Organizers can do the same, and reporters can read the list. The API routes are under `/api/account/leagues/<id>/participants`.
- A player waiting to join a League is now told that its organizer approves requests, not Arena staff.

## 0.73.2 — 2026-11-09

Release 0.73.2 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- The Leagues page's search description no longer quotes a price. Subscriptions aren't open yet.

## 0.73.0 — 2026-11-08

Release 0.73.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none for bots. Agents that call the MCP tools `list_events`, `get_event_achievements`, `request_house_opponent` or `cancel_house_opponent` should switch to `list_my_ladders` and `enroll_ladder`. Links to `/rankings`, `/ladder` and `/history` still work or redirect.

### Ladder and website

- The title screen slogan now reads “Play with AI before you work with AI”.
- The match behind the title screen is brighter: dark shading sits only behind the title, menu, preview and footer instead of over the whole screen, and the rays behind the crest no longer turn. The slogan is larger and easier to read, and the ARENA title is a little smaller. Its camera now glides after the fighters at a steady pace, without screen shake or zooming in and out, so it's easier to watch.
- The page dims behind the open announcements tray. Click anywhere outside it to close it.
- Events are retired: Leagues replace them. Old event achievement links open **Browse Leagues**, where finished competitions such as SAINTCON 2026 keep their standings and results. The achievement and event-reminder email settings are gone, and the events guide is no longer published.
- `/docs/schema/` lists the protocol schemas, `/ladder/` and other trailing-slash addresses go to their pages, and plain-HTTP requests go to HTTPS. Each public page has one main heading and a fuller search description.
- Drop the All versions card from the bot detail header; Rank, Score and Record keep the summary.
- Bot detail panel Expand/Close controls are icon buttons sized with the other header controls.
- **Leagues** replaces **Events** in the top bar. It opens a new [Leagues](https://victrisarena.com/leagues) page for companies, schools and clubs: what players learn, how a League runs in three steps, what the Standard and Premium plans include, and common questions. Subscriptions aren't open yet: create a free draft League and contact us to activate it.
- **Rankings** in the top bar is now **Leaderboard**, at `/leaderboard`. Old `/ladder` and `/rankings` links still work and go there, and the API's `leaderboard_url` and `history_url` now point there too. It no longer has a row of its own under the top bar. A **Bots** switcher beside the ladder picker opens the Universities, Organizations and Agents boards (or a League's Teams), and **Leaderboard** stays highlighted on all of them.
- **Feedback** in the top bar is now a speech-bubble icon beside the announcements bell. On phones it is the last item in the Menu. It still opens the contact page.
- Owner, school, organization and agent tags on the leaderboard and on a bot's page look like links, with an amber outline, and open their page wherever you tap them. Before, only the text worked: tapping a tag's edge on the leaderboard opened the bot instead. A bot's page now shows its owner's school or organization next to the owner, and `GET /api/bots/<name>` has a new `team` field: the owner's verified school or organization domain, or null.
- Your account has a new **My Leagues** tab, right below Bots. It lists the Leagues you play in and the ones you run, and it's where you create a League. Old links to **My leagues** open it.
- The League directory at `/ladders` is now **Browse Leagues**: current Leagues first, then past competitions with their results.
- Signing in from the home page, including a new account's first sign-in, now lands on your account page instead of going back to the home page. Signing in from any other page still returns you there.
- When a League ends, a connected bot receives its finishing match's `end` message before the ladder closes its connection.
- Following an emailed password-recovery link asks for a new password again. It had been signing people in without asking for one.
- New leagues are private. Only the league's owner and members see its standings, matches, replays and artwork, on the website, the HTTP API and MCP. Leagues that were public before keep their public history.
- League owners can publish a single match result or up to 20 standings rows as a public snapshot. They preview it first, and can revoke the link later.
- League members can browse a league's whole match history after games leave the 30-day window, including after the league ends: open **History** on the league (`/ladder?ladder=<id>&view=history`), call `GET /api/ladders/<id>/history`, or use the MCP tool `list_private_match_history`. Filter by bot and version, page through results and download each page as JSON. Old match pages, replays and stats keep working for members.
- Version aliases and notes recorded only in a private league stay off the bot's public profile.
- A match page shows each fighter's avatar and colour as they were when the match started, so changing your bot's look no longer repaints its past matches. Matches recorded before this change show plain orbs in classic colours, and the page says so.
- A changed avatar or colour shows on the leaderboard after that version's next rated game.
- Replays recorded by the 0.21.0 engine play again in the browser and the CLI, using that engine.
- The top bar no longer has a **Public history** button, and the `/history` search page is gone. Agents search older public matches with `GET /api/archive/public/history`, and old replays still play in the replay viewer.
- The Terms of Service and Privacy Policy explain that public games show your bots' names and results, how private league membership works, and what happens when a league owner shares a result.

### Agents and MCP

- MCP no longer offers `list_events`, `get_event_achievements`, `request_house_opponent` or `cancel_house_opponent`. Use `list_my_ladders` and `enroll_ladder` to join Leagues.
- The agent guide is published as an Agent Skill: `/.well-known/agent-skills/index.json` lists `victris-arena`, and MCP serves the same `SKILL.md` as `skill://victris-arena/SKILL.md` (`skills/list`, `skills/get`).
- Bot, match and live standings pages answer `Accept: text/markdown` with their record, result or table, and their HTML names the Markdown and JSON forms in `Link` headers. A bot page's summary includes its rated record.
- MCP `get_leaderboard`, `get_bot`, `get_match` and `get_ladder_results` declare output schemas.
- MCP's `initialize` answer gives the server's title, description, website, icon and instructions. Every tool has a display title, every input a description, and read-only tools are marked idempotent.
- New discovery documents: an MCP Server Card at `/.well-known/mcp/server-card.json` and an API catalog at `/.well-known/api-catalog`. An MCP request without credentials gets a 401 that links the setup guide.

## 0.72.2 — 2026-11-03

Release 0.72.2 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- A closed league's results page loads again. The SAINTCON 2026 results were unavailable for several hours on 2026-11-03.

## 0.72.1 — 2026-11-03

Release 0.72.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. This release includes the changes from 0.72.0, which was not deployed.

### Ladder and website

- League team managers see each member's handle, rather than an account ID, before the member has a bot in the league.

## 0.72.0 — 2026-11-03

Release 0.72.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. Bulk replay and stats packs now cover public matches only: for league matches, download each match from its own URL. This release was not deployed; its changes shipped in 0.72.1.

### Ladder and website

- Create and manage your own league from the Events page: a Markdown description, artwork, a player limit, password access, single-use links and email invitations.
- League owners can deactivate and reactivate their league.
- Leagues can have their own teams: assigned by the owner, chosen by players, or created on the fly. Owners manage rosters and team names, and can lock rosters. Team standings average each team's best five accounts, one bot per account, with empty places at 700. Closed leagues keep their team results.
- **Rankings** replaces the separate Leaderboard, Teams and Agents links. Bot rankings open first, with Organizations and AI Builders beside them and Teams inside leagues that use them. Existing links still work, and Account → Affiliation names your institutional affiliation.
- Organization teams show the organization's name from its website, falling back to the domain.
- A closed league's bot, match and profile pages show the records saved with its final standings, so a bot's record there stays what it was at the close.
- Bulk replay and stats packs cover public matches only, and league matches no longer list a `pack_url`. Download league matches one at a time from their own URLs.
- Bots reconnect cleanly when the ladder loses track of a match in progress.
- The title screen slogan is now “Play with AI before working with AI”.

## 0.71.6 — 2026-11-02

Release 0.71.6 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- Closed leagues load their final standings and results quickly again.

## 0.71.5 — 2026-11-02

Release 0.71.5 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- The ladder list and a closed league's final standings load faster.

## 0.71.4 — 2026-11-02

Release 0.71.4 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- `www.victrisarena.com` now goes to `victrisarena.com`, keeping the rest of the address.
- A bot page's Health table covers each version's latest 500 matches among the bot's latest 2,000, so a version that shared its time with others can cover fewer.
- A public status page is at https://victris-arena-status.netlify.app.

## 0.71.3 — 2026-11-02

Release 0.71.3 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- The HTTP API allows 6,000 requests a minute per address again, as documented.
- A client far beyond any normal rate is stopped: about 20,000 `/api` requests or 3,000 `/replays/` downloads a minute from one address. Whole packs aren't limited.

## 0.71.2 — 2026-11-02

Release 0.71.2 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. This release has no player-facing changes.

## 0.71.1 — 2026-11-02

Release 0.71.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. This release has no player-facing changes.

## 0.71.0 — 2026-11-02

Release 0.71.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. If you download many replays or stats, download whole minutes instead: it's much faster, and `arena_sim.download_replays` now does it for you. Upgrade the simulator, or see [Downloading matches in bulk](https://victrisarena.com/docs/api#downloading-matches-in-bulk).

### Ladder and website

- `GET /archive/packs/<scope>/<pack>.pack` downloads a minute's matches on a ladder at once, replays and stats together. Each match in a list gains `pack_url`.
- `GET /api/matches?after=<match id>` returns the matches after that one, oldest first, to follow a ladder or walk its 30-day window without downloading the same ones again.
- `GET /api/matches?stats=1` answers long lists much faster.

### Bot protocol and simulator

- `arena_sim.download_replays` fetches each pack once, rather than each replay.

## 0.70.1 — 2026-11-01

Release 0.70.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- MCP match lists with stats answer much faster. Results don't change.

## 0.70.0 — 2026-11-01

Release 0.70.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. The ladder had one planned outage. Your tokens, ratings and records came with it, and the addresses stay the same. A bot that reconnects after a dropped connection needs nothing else.

### Ladder and website

- An update no longer interrupts a match or takes the site down.
- Event reminders and the weekly digest arrive once a day; the digest arrives early Monday UTC.
- Event ladders follow the same 30-day window as Public: ratings, records and matchmaking count the last 30 days, and older days join lifetime totals. A closed ladder keeps its final standings and results.
- Matchmaking stays quick on ladders with many versions waiting.

## 0.69.0 — 2026-10-31

Release 0.69.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- A bot's Versions table shows each version's alias on its own line. The Opponents, Maps and heatmap version pickers include the alias when it fits.
- Those pickers list only versions with games on the ladder being viewed, and an empty panel says the bot hasn't played on that ladder.

## 0.68.0 — 2026-10-31

Release 0.68.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** no bot code changes required unless your tools read seasons. The public leaderboard no longer resets each month: `/api/seasons` becomes `/api/snapshots`, `?season=` becomes `?snapshot=` on `/api/leaderboard`, `/api/teams` and `/api/agents`, and `/api/matches` and the MCP `list_matches` tool drop it. Keep playing to keep your place: ratings and records count the last 30 days. Match stats gain an optional `occupancy` per fighter; gameplay and replays don't change.

### Ladder and website

- Seasons are gone: Public counts the last 30 days and never resets, so a bot keeps its place by playing, across any month boundary. Past months stay as final standings at `/snapshots`. A rating can move a little overnight as the oldest day leaves, and a version with no games for 30 days leaves the board until it plays again.
- Every bot page shows lifetime stats: when it started competing, days active, rated games, W-L-D and best rank.
- Match pages older than 30 days answer "not found".
- Matches interrupted by a restart are no longer recorded as voids.
- Bot listings show equipped avatar icons throughout the site. Rank badges appear in standings and matchup views, and unranked bots show a dash.
- Player versions are named automatically (`v1`, `v2`, …). Existing versions are numbered, and their old names stay as aliases in the bot's Versions section; notes remain the longer description. The CLI creates the next number with `arena version --alias ... --notes ...`. Existing keys, ratings and records keep working.
- Emails open with a shorter header, so the message shows without scrolling.
- Match and replay stats explain forfeits, disqualifications, disconnects and idle turns. Bot Health replaces “Drops / DQ” with labelled interruption counts. Information buttons show definitions on hover, keyboard focus or tap.
- A bot page's header has a position heatmap for each version (click for the large view), with map walls, a map selector and tick counts. Gameplay and replays are unchanged.
- The bot page's opponent and map version filters load that version's own recent games, so older versions still show records. `GET /api/matches` accepts `version` with `bot`.

## 0.67.1 — 2026-10-29

Release 0.67.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. M-Bot is back on every ladder as `mbot-refresh-1028-int8-varied`. 0.67.0's version label was one character over the protocol's 32-character limit, so M-Bot stayed offline.

## 0.67.0 — 2026-10-29

Release 0.67.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. M-Bot plays a refreshed network as a new version, and no longer repeats a match move for move, so replaying a recorded win against it rarely works again.

### House bots

- M-Bot plays the refreshed `mbot-refresh-20261028` network. Close movement choices vary at random for the whole match, so a recorded winning input sequence stops working. Its attacks are unchanged.

## 0.66.2 — 2026-10-29

Release 0.66.2 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. This release brings 0.66.0's M-Bot on every ladder.

## 0.66.1 — 2026-10-29

Release 0.66.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. This release was not deployed; its changes shipped in 0.66.2.

## 0.66.0 — 2026-10-29

Release 0.66.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. M-Bot (`house-mbot`), a larger trained opponent, now plays on every ladder alongside Champion. It is rated outside the house anchor and is not an event achievement opponent. This release was rolled back shortly after deploying; its changes shipped in 0.66.2.

### Ladder and website

- Bot pages fit narrow desktop windows without scrolling a few pixels.

### House bots

- M-Bot (`house-mbot`) plays on every ladder.

## 0.65.0 — 2026-10-29

Release 0.65.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- Expand any bot detail panel into a large dialog, with filters and sorting kept, and return with Close or Escape.
- Bot detail panels stay readable in short desktop windows: the page fits the window only when each panel has room for a few lines, and scrolls otherwise.
- The announcements tray shows only unread announcements by default, with mark-read controls for one or all and a toggle to show read ones. Opening the bell no longer marks messages read.
- The navigation bar reads "Victris Arena" instead of "Arena Ladder" on the ladder pages.

## 0.64.0 — 2026-10-26

Release 0.64.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. Champion plays as `l4-7860-int8-varied`, with the same trained weights and a little early movement variation; its rating starts separately.

### House bots

- Champion keeps its `l4-7860` network, but varies its movement at most twice between ticks 4 and 79, choosing moves close to its preferred one. Its attacks are unchanged. This makes repeated winning lines against it much less likely.

## 0.63.1 — 2026-10-26

Release 0.63.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. This release brings 0.63.0's changes, which were not deployed. Team API and MCP clients can request `kind=organization`; the default remains Universities.

## 0.63.0 — 2026-10-25

Release 0.63.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. Team API and MCP clients can request `kind=organization`; the default remains Universities. Each account keeps one affiliation across both boards. This release was not deployed; its changes shipped in 0.63.1.

### Ladder and website

- Search the leaderboard by bot name, owner, team domain or credited agent; ranks stay as they are. On My Bots, names and portraits link to bot pages; open Edit to rename a bot.
- Play leaves the site Menu. Practice stays at `/play`, from the title screen's Play Game entry.
- The `/play` tutorial starts on dash, then weapons, dodge, pickups and the storm, and adds a ricochet lesson with a dotted bounce preview.
- Create a Bot and the title-screen menu say that you run a bot yourself, instead of “send it in”. The main path has an AI assistant build and run the bot; building it yourself is a secondary link.
- The bot guides, Create a Bot, the agent task prompt and the agent discovery page explain agent attribution and university and organization teams.
- University and organization leaderboard rows show each team's total verified players, apart from the best five who score.
- An Organizations leaderboard sits beside Universities. Verify an organization email by code, or by signing in with it. Subdomains group under their registered domain, `.edu` addresses stay in Universities, and shared or disposable email providers are refused. Each account picks one affiliation, with the existing 30-day switching lock and yearly renewal.

## 0.62.0 — 2026-10-25

Release 0.62.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. Download this release's simulator for the new replay tools. New recordings identify the release that made them.

### Bot protocol and simulator

- New replays record the release and replay format that made them. The viewer, Watch Live, and the CLI's replay and stats tools load the matching simulator, verify it, and check the recorded results. A replay they can't play says so.

## 0.61.0 — 2026-10-25

Release 0.61.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. Existing rosters now follow the bots-per-owner limit: extra bots are retired, keeping the ones with the best public ranks. Owners can unretire a bot after freeing a slot.

### Bot protocol and simulator

- Python fast environments can profile their phases on request (`profile()`), with worker readiness and timing totals. It's off by default and doesn't change games or replays.

### Ladder and website

- Send feedback from the form on `/contact`, linked as Feedback from the site Menu and the title screen.
- The bots-per-owner limit applies to existing rosters: extras are retired (keeping the best public ranks) when the limit drops. Owners can unretire a bot after freeing a slot, from My Bots or MCP `unretire_bot`.
- Failed bot or version creation no longer uses up a name or a place in your quota.
- Long bot summaries scroll within short desktop windows, leaving room for every stats panel.
- Pages show loading immediately when you change ladder or rating range, and keep what they showed during a brief connection error.

## 0.60.2 — 2026-10-24

Release 0.60.2 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. This release brings 0.60.1's results-page fix.

### Ladder and website

- The announcements tray closes reliably when you press outside it right after opening it.

## 0.60.1 — 2026-10-24

Release 0.60.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. This release was not deployed; its changes shipped in 0.60.2.

### Ladder and website

- Opening a ladder's results no longer pauses matches. It could disconnect bots with short heartbeats.
- A match's result and replay link show as soon as the match loads, while its full stats load separately.

## 0.60.0 — 2026-10-24

Release 0.60.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. Existing HTTP clients keep the same API. This release was rolled back after deploying.

### Ladder and website

- The ladder no longer pauses matches every few minutes, which could drop bots with tight heartbeats.

## 0.59.1 — 2026-10-24

Release 0.59.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. This release brings 0.59.0's changes, which were not deployed.

## 0.59.0 — 2026-10-23

Release 0.59.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. This release was not deployed; its changes shipped in 0.59.1.

### Ladder and website

- Replay damage numbers keep their place as they rise instead of flickering between spots. Hits on the same fighter at once fan outward and up, and numbers stay on the board by sliding along its edge.
- Watch Live and replays share a knockout finish: a close-up on the lethal hit, bullet time, an impact hold, then a large portrait of the winner's avatar and the victory stinger. Pause freezes it; scrubbing, stepping and reduced motion skip it. Watch Live holds the result before moving on, and replay stats wait until the reveal.
- Watch Live's game fills the window, with navigation and fullscreen in a compact bar below it.

## 0.58.2 — 2026-10-23

Release 0.58.2 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. This release brings 0.58.0's changes: the champion plays in int8 as `l4-7860-int8`.

## 0.58.1 — 2026-10-23

Release 0.58.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. This release was not deployed; its changes shipped in 0.58.2.

## 0.58.0 — 2026-10-23

Release 0.58.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. The champion plays the same network in int8, as a new version (`l4-7860-int8`) rated apart from `l4-7860`. This release was not deployed; its changes shipped in 0.58.2.

### Ladder and website

- Title-screen fighters are named after their avatars (such as Titan and Specter) instead of both being TS-Starter. The backdrop uses only Columns and Pillars.
- Bot detail names get the full space beside the portrait, with the four stat cards below the title. The avatar is 15% larger.
- Recent matches keep each bot's name and version on one line.
- Recent matches on the leaderboard and bot pages show each bot's ladder position as a small badge, with a dash for unranked bots.
- The desktop bot page fits shorter windows: Opponents and Maps share the middle column, and each panel scrolls on its own.
- Account handles and bot names accept letters, numbers and combining marks from every script. Equivalent spellings and case variants count as the same name, and length limits count characters. Invisible characters, emoji and URL separators are refused. Existing names stay valid.
- The top of Create a Bot is rewritten for people who don't code: a shorter intro, plainer "Let an AI build it" and "Write it yourself" cards, three short steps for connecting an AI assistant, and the full prompt behind a "See the prompt" toggle.

### House bots

- The champion's network runs much faster, in int8, and plays as `l4-7860-int8`, a new version rated apart from `l4-7860`. In simulation it scored 50.4% against the original over 16,384 games and changes about 0.2% of its moves.

## 0.57.3 — 2026-10-23

Release 0.57.3 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. This release brings 0.57.2's changes, which were not deployed.

## 0.57.2 — 2026-10-23

Release 0.57.2 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. This release was not deployed; its changes shipped in 0.57.3.

### Ladder and website

- Version colour marks on a bot's page are a compact bar matching the rating chart.
- `/play` opponent cards sit together in the middle of the page and size to their content.
- On `/play`, clicking a map starts the match. The arena step shows Arena, Columns and Pillars as matching cards and drops Random; Pace stays above the board during a game.
- `/play` practice opponents act on only half the ticks. The shot preview stops at a wall and no longer draws the ricochet.
- On a controller, `/play` dashes with LB; RB still shoves.

## 0.57.1 — 2026-10-23

Release 0.57.1 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required.

### Ladder and website

- The leaderboard fits a 320px-wide phone again.

## 0.57.0 — 2026-10-23

Release 0.57.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** public downloads now ship only the TypeScript and Python starters plus Random. If you trained against bundled Brawler or Kiter, switch to those or a registered opponent. The ladder's house Brawler (`brawler-19`) and Kiter (`kiter-18`) are stronger. Bot tokens no longer transfer account ownership: replace an accountless hosted bot with one registered under your account. MCP with browser sign-in is the recommended setup; existing agent keys still work.

### Bot protocol and simulator

- Public bot downloads provide one starter in TypeScript and Python, plus Random. The simulator bundles, Python wheels and browser practice include `ts-starter` and `random`; Brawler and Kiter play only on the ladder. Practice at `/play` offers Random (Easy) and Starter (Hard). Offline code naming `brawler` or `kiter` must use a public or registered opponent, or self-play.

### House bots

- Brawler (`brawler-19`) and Kiter (`kiter-18`) are stronger, keeping their close-pressure and range-control styles. They weigh visible danger, avoid exposed wall slams, plan pickups and check firing lanes after moving.

### Ladder and website

- The leaderboard's **View Chart** button opens a standalone, auto-refreshing avatar graph for event screens: rank across, score up, with a raw-rating option, details on hover, tap or focus, and fullscreen. **Watch Live** on Recent matches opens a full-page, muted playlist of recent matches, with fullscreen and large portraits above the health bars.
- AI-agent setup leads with MCP and browser sign-in. Create a Bot and My Bots share a task prompt that has the agent find your account, build and test a fighter, register it through MCP, and review a match to improve it. Agent keys move under **Advanced connection options**.
- Claiming legacy bots is gone. Bot tokens no longer transfer account ownership; existing histories and tokens stay. An accountless bot must be replaced by one registered under an account to play on the hosted ladder.
- Creating a bot asks only for a name. **Edit → Built with** picks the AI agent that built it from a searchable list, including hand-coded and custom names.
- My Bots has a Create bot button that opens a short form, disabled with an explanation at the bot limit.
- Click a bot's name on My Bots to rename it inline.
- Appearance changes save automatically, with Retry on failure. Reset restores the look from when the editor opened.
- Bot editors close from a × or a **Close** button, and open and close smoothly, respecting reduced motion.
- Owners get an **Edit bot** link on their bot's page. **Built with**, New token and Retire/Delete live inside the editor.
- AI agents show monochrome logos beside their names in the picker, attribution and standings, one size larger than before.
- Bot detail headers show a larger avatar.
- Account settings tabs have icons, and delete buttons use a trash-can icon.

## 0.56.0 — 2026-10-22

Release 0.56.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.7

**Action for bot authors:** none required. A `quota_exceeded` error now says which quota holds your bot back and when it frees (`retry_after_s`): stay connected and queued, and wait that long rather than reconnecting. Protocol 0.7 only adds these optional fields; clients that validate the hello version must accept 0.7. Owners can pick their bot's colour on My Bots, and practice at `/play` runs in real time by default.

### Bot protocol and simulator

- A `quota_exceeded` error says which quota holds the bot back and when it frees, so a bot can wait instead of retrying blindly: `quota` (its name in `GET /api` `quotas`), `limit`, `used` and `retry_after_s`, the seconds until a place frees (`null` for the owner's concurrent matches, which free as a match ends).

### Ladder and website

- Replays play at half their old speed, so a fight is easier to follow. The viewer's 1× is now half real time and 2× is the old 1×.
- Retired bots are hidden by default on My Bots and profiles, with a **Show retired (N)** checkbox.
- Bots show their avatar as a small icon beside their name on the leaderboard, in recent matches, in the Online list and on university pages. An online bot wears a green dot. Leaderboard rows (`GET /api/leaderboard`, MCP `get_leaderboard`) and each school's top bot in `GET /api/teams` gain `avatar`.
- Scrolling fast down the leaderboard on a phone no longer crashes the page.
- Bots wear a colour of their owner's choosing: one of 14, or Classic for the corner's blue or red. My Bots' avatar picker is a locker, with the bot on a pedestal, Persona and Color tabs, and tiles you can try on. The colour shows everywhere the bot is drawn. When both fighters wear the same colour, one switches to classic blue or red. New `PUT /api/account/bots/<name>/color`; bot, match, lobby, leaderboard and results records gain `color`.
- Practice at `/play` runs in real time by default, like a twin-stick shooter at 5 ticks a second. Walk with WASD or the left stick, aim with the mouse or right stick, click or RT to shoot, Space or A to dash, hold right-click or LT to aim a frostburst, and E or RB to shove. Esc or Start pauses. **Pace** switches to **Fast**, the ladder's 10 ticks a second, or **Turn by turn**. Touch screens start turn by turn.

## 0.55.0 — 2026-10-22

Release 0.55.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.6

**Action for bot authors:** none required. A ranked version that stops playing now slips down the leaderboard after 12 hours idle and earns its place back by playing rated games, so keep the version you want ranked connected. You can name the AI agent that built your bot (`agent` on registration, `arena register --agent`, MCP `set_bot_agent` or `PUT /api/me/agent`) to appear in the new `/agents` standings.

### Ladder and website

- Opening the announcements tray clears the unread badge, and notices published since it last opened are labelled **New**. The tray takes focus when it opens, returns it on Escape, and closes on a press outside it. `GET /api/announcements` sends an `ETag` and answers an unchanged list with `304`.
- MCP sign-in that fails because of a sign-in configuration problem says so, instead of asking you to sign in again.
- A bot can name the AI agent that built it, and `/agents` compares the agents.
  - Pick from a catalog of 34 agents or type your own: on My Bots, as `agent` in `POST /api/bots` and `POST /api/account/bots`, with `arena register --agent`, MCP `register_bot` and `set_bot_agent`, or `PUT /api/me/agent` with the bot's token. Bot pages, profiles and the leaderboard show it.
  - `/agents` ranks agents by the average score of their best five players' bots (one bot each, empty places at 700), with each agent's top bot, median, popularity and head-to-head record. `/agents/<id>` lists an agent's ranked bots and matchups. `GET /api/agents`, `GET /api/agents/<id>` and MCP `get_agents` return the same data. A custom name stands alone once three accounts use it; until then it counts under Other agents.
  - Leaderboard rows gain `agent`.
- A ranked version that stops playing slips down the leaderboard. After 12 hours without a rated game its score loses `((hours idle − 12) / 12)²` points, up to 200: 1 after a day, 25 after three days, 169 after a week. Each rated game earns back 10 points. Ratings and matchmaking are unchanged. Leaderboard rows, bot versions, user standings and the lobby add `idle_penalty` (and rows and versions `last_played`); scores show the points lost as ↓N.
- Tapping a leaderboard row on iPhone or iPad opens that row's bot again.
- On a wide screen, a bot's page puts Recent matches under the rating chart and gives Versions and Health the right-hand column, each scrolling on its own.

## 0.54.0 — 2026-10-21

Release 0.54.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.6

**Action for bot authors:** none required. Subscribe to `/changelog.atom` to hear about releases. The Python simulator now warns (`OutdatedSimulatorWarning`) when a live match or downloaded replays were played on other rules than its own; download this release's to get it. Agents can read the ladder's live limits from `quotas` in `GET /api`, and MCP has 12 new tools for events, achievements, house opponents, standings and teams.

### Bot protocol and simulator

- The Python package warns, once per rules table, when a live match's `hello` or downloaded replays were played on other rules than its own (checked by `Basic` and `ScriptEncoder` at match start, or by `check_hello(hello)` for your own encoder). It makes no requests of its own to do it. `python -m arena_sim check` defaults to `$ARENA_SERVER`, else the public ladder.
- `python -m arena_sim changelog` (`changelog()`) prints the ladder's release notes since this release. The package carries its own release's `CHANGELOG.md`.
- Each release ships the TypeScript it was built from: the bundles have source maps, and `python -m arena_sim source <dir>` writes the sources out.
- Every release's downloads stay available under `/download/<release>/`.

### Ladder and website

- `GET /api` publishes `quotas`: the live fair-use limits to plan around (bots per owner, matches per bot per hour and per owner per day, new versions per day, match interval, concurrency, agent keys, API requests), each with its label, value, unit and a note.
- The limits tables in the agent and API guides, MCP's `get_agent_guide` and the `/guide` pages show the ladder's current values. The guides say which limits send `quota_exceeded` and which refuse the request.
- `GET /api/ladders` adds each ladder's `effective` match capacity.
- Achievement emails arrive during an event. They have their own limit of five a day, apart from other optional emails. A new award waits 10 minutes, then one email lists every pending award in that event.
- MCP has 12 new tools: `list_events` and `get_event_achievements` for event schedules and your progress; `request_house_opponent` and `cancel_house_opponent` for house-bot matches; `get_leaderboard`, `get_bot`, `list_matches`, `get_match` and `get_ladder_results` for public ladder data; `get_teams`, `get_my_team` and `join_team` for university standings. Flags are revealed only in the browser. The opponent and team tools need account-actions consent. See [docs/MCP.md](https://victrisarena.com/docs/mcp).
- `/changelog.atom` is an Atom feed of the releases, linked from `/changelog`, `GET /api` (`changelog.feed`) and the guides. A release that changes the rules says so in its title.

## 0.53.0 — 2026-10-19

Release 0.53.0 · engine 0.23.0 · rules 0.22.1 · protocol 0.6

**Action for bot authors:** none required. Shouts cool down in 10 ticks instead of 20; read `hello.rules.shout.cooldown` rather than hard-coding it, and download this release's simulator to practise with the new table. Agents calling the HTTP API should read the new `RateLimit` headers and wait out a `429` for its `Retry-After` seconds.

### Rules and balance

- Shouts cool down in 10 ticks instead of 20, so a bot can talk once a second. Rules version 0.22.0 → 0.22.1. No combat numbers changed. Older replays re-simulate unchanged.

### Ladder and website

- Sign-in buttons show the Google and GitHub marks.
- Agents can read the site as Markdown: `/`, `/guide/<name>` and `/changelog` answer `Accept: text/markdown` with the page's Markdown (`/llms.txt` for the home page), send `Vary: Accept`, and name it in a `Link` header. A missing address answers a Markdown request with a 404 that links to `/llms.txt`, the guides, `/api` and the sitemap.
- `/llms.txt` says when to use Victris Arena and how to call it.
- New `/about` and `/contact` pages, linked from the title screen and the guides.
- The HTTP API has a version: every `/api` response carries `Arena-Api-Version: 1`, and a request pinning an unsupported version gets `400 unsupported_api_version`. The policy is in [docs/API.md](https://victrisarena.com/docs/api#versioning-and-deprecation).
- `/api` requests are limited per client address (6,000 a minute by default). Responses carry `RateLimit` and `RateLimit-Policy` headers; past the budget the ladder answers `429 rate_limited` with `Retry-After`.
- MCP clients that look for `/.well-known/oauth-authorization-server` at the ladder's address find the sign-in server's metadata there.

## 0.52.0 — 2026-10-19

Release 0.52.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required. This release has no player-facing changes.

## 0.51.1 — 2026-10-19

Release 0.51.1 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required.

### Ladder and website

- `/account` is organized into Bots, School, AI connections, Profile and Email preferences, one section at a time. School links open verification directly. Switching sections keeps unsaved form values and newly created tokens.

## 0.51.0 — 2026-10-18

Release 0.51.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required. University standings are optional and don't change individual ratings or matchmaking.

### Ladder and website

- University standings at `/teams`. Represent your school by verifying an address at its `.edu` domain, with an emailed code or, if you signed in with one, a click; departments and alumni count for the root domain. Each school scores the average leaderboard score of its best five members, one bot each, with empty places at 700. Each leaderboard row names its owner's school. The address isn't stored, only a keyed hash and the school. School names come from the MIT-licensed Hipo university domains list.

## 0.50.0 — 2026-10-18

Release 0.50.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required. Agents that read `GET /api/seasons/<id>` for the live season now get `{season, pending: true}`: a season's report is published once, when it closes.

### Ladder and website

- Rating charts and season reports no longer pause matches. A season's report (highlights, specialists, rivalries, styles and matchups) is built once, when the season closes, and archived with its final standings. The live season shows standings only, and `GET /api/seasons/<id>` answers `{season, pending: true}` until its report is ready (matchups: 404 `season_pending`).

## 0.49.0 — 2026-10-18

Release 0.49.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required. This release has no player-facing changes.

## 0.48.3 — 2026-10-18

Release 0.48.3 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required.

### Ladder and website

- The title menu keeps its height when you hover its entries. The online and live counts move to the topbar beside the crest.
- The replay viewer's timeline no longer lists `collision` twice.

## 0.48.2 — 2026-10-18

Release 0.48.2 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required.

### Ladder and website

- A bot's Versions panel shows every row in short windows.

## 0.48.1 — 2026-10-18

Release 0.48.1 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required beyond 0.48.0's notes, which this release delivers: 0.48.0 was not deployed.

### Ladder and website

- The finished SAINTCON 2026 precon event and its ladder keep their original name and text.

## 0.48.0 — 2026-10-18

Release 0.48.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required. The ladder's address is now https://victrisarena.com (bots connect to `wss://victrisarena.com/bot`); bots configured with arena.victris.ai keep connecting, but switch when convenient. This release was not deployed; its changes shipped in 0.48.1.

### Ladder and website

- The game is now Victris Arena. The title screen and emails read VICTRIS above ARENA, and the crest has a chiselled gold V. Page titles, emails, the CLI, the starters and the docs use the new name.
- The ladder moves to https://victrisarena.com (bots connect to `wss://victrisarena.com/bot`). Pages opened at arena.victris.ai move to the same page at the new address; the API, sockets, docs and downloads still answer there.
- One navigation bar across every page. Phones use a Menu dropdown. Pages keep working navigation without JavaScript.
- Monthly public seasons with UTC month boundaries, fresh ratings and records, permanent final standings, and a season report with upsets, streaks, close finishes, rivalries, combat specialists and an opponent win-rate chart. Existing public history becomes Pre-season until the next month. Matches interrupted by a restart are recorded as voids.
- A navbar dropdown beside the ladder switcher opens current and past season standings and reports.
- The leaderboard is a four-column table at every screen size. The whole row opens its bot; owner links still open profiles.

## 0.47.5 — 2026-10-17

Release 0.47.5 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required.

### Ladder and website

- Busy closed ladders' results pages finish loading instead of hanging on Loading….

## 0.47.4 — 2026-10-17

Release 0.47.4 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required.

### Ladder and website

- Long map names in a bot's Maps panel are cut short with an ellipsis, like bot names.

## 0.47.3 — 2026-10-17

Release 0.47.3 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required.

### Ladder and website

- A long bot name in the Opponents or Maps panel is cut short instead of widening the panel.

## 0.47.2 — 2026-10-16

Release 0.47.2 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required.

### Ladder and website

- Opponents and Maps columns no longer crush together, which made sort headers unclickable and wrapped W–L–D.
- The `/results` intro is readable without JavaScript.

## 0.47.1 — 2026-10-16

Release 0.47.1 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required. Python training loops that call `close()` should upgrade so interpreter shutdown can't hang.

### Bot protocol and simulator

- The guides explain that a late turn after `end` gets the non-fatal `not_in_match` notice (while an attached match still ignores old-tick replies), and that clients should keep queueing.
- The Python simulator's `close()` disposes its embedded V8 engines (`FastVectorEnv` and `FastSelfPlayEnv` in single-process mode, the Gymnasium and PettingZoo environments, and `Simulator`), and worker processes close on teardown. Without that, Python 3.13 and later could hang on interpreter shutdown.

### Ladder and website

- A shareable ladder results page at `/results?ladder=<id>` (and `GET /api/ladders/<id>/results`): podium, volume, map mix, rivalries, achievement tallies and highlight matches. Past event cards on `/ladders` link to it.
- A bot page's Opponents and Maps keep each summary on one row.
- Events can require a join password: enter it to enroll on the website or through MCP. SAINTCON 2026 uses password enrollment instead of staff approval.
- Simulator downloads have versioned links in `GET /api` and the docs.

## 0.47.0 — 2026-10-16

Release 0.47.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required.

### Ladder and website

- `/play` is offline practice in the browser: the simulator and house bots (Kiter, Brawler, Starter) run in the page, with no account and no match records. Champion isn't offered. Practice turns have no timer.
- Tutorial is the first opponent card. The coach overlays the board on wide screens and docks under it on phones, with a Goal / Done banner per lesson. `?` and in-game Controls remain.
- `/play`'s announcements bell sits in the topbar with Sign in / My Bots.
- Human games played on the server before this release are removed.

## 0.46.2 — 2026-10-16

Release 0.46.2 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required.

### Ladder and website

- `/play` opponent blurbs no longer cover the Select button.

## 0.46.1 — 2026-10-16

Release 0.46.1 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required.

### Ladder and website

- Avatar portraits return to their still pose when reduced motion is turned on.

## 0.46.0 — 2026-10-16

Release 0.46.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required.

### Ladder and website

- `/play` is a two-step picker: choose a house bot (with its animated avatar and a playstyle line), then an arena, then Fight. The Sound control appears only during a match.
- A Discord link to the Victris AI community on the landing page.
- The bot page's ladder picker offers only ladders where that bot has played.
- The ladder and bot pages drop their footnotes; the definitions stay in the API guide.
- Bot pages show the 100 most recent opponents from their last 500 games in a scrolling panel.
- Opponents and Maps each have a version filter, defaulting to the current version on the selected ladder.

## 0.45.1 — 2026-10-15

Release 0.45.1 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required. This release brings 0.45.0's changes, which were not deployed.

## 0.45.0 — 2026-10-15

Release 0.45.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required. This release was not deployed; its changes shipped in 0.45.1.

### Ladder and website

- The guides at `/guide` are redesigned in the game's look: every guide is listed beside the page, each page has its contents alongside, code blocks have a copy button, and notes and warnings stand out.
- The agent, bot and ranged-attack guides are shorter and easier to scan. Diagrams show the message flow, the phases of a tick, the grid and corner cutting, shots and bounces, frostburst, the repulsor and the zone; Markdown readers get them at `/docs/images/<name>.svg`.
- My Bots is streamlined: event shortcuts, a prominent Create bot action, AI connections with expandable setup, and email preferences under Account settings.

## 0.44.1 — 2026-10-14

Release 0.44.1 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required.

### Ladder and website

- Leaderboard owner names and profile links stay visible on phones.
- On iPhone, W–L–D records refresh cleanly instead of showing duplicated numbers.
- Bot avatars have deeper team-colour lighting, reflective armour, cloth folds, braided beards, faceted gems and clearer eyes. Personas have their own idle rhythms and react to movement, attacks and hits.
- Large records, long bot and version names, and health figures stay readable inside ladder and bot panels.

## 0.44.0 — 2026-10-14

Release 0.44.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required. This release has no player-facing changes.

## 0.43.1 — 2026-10-14

Release 0.43.1 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required.

### Ladder and website

- Bot pages fit a tall desktop window even when the summary wraps.
- Click a column heading to sort the leaderboard and a bot's versions, health, opponents and maps, ascending or descending.

## 0.43.0 — 2026-10-14

Release 0.43.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required. The house champion is a new, stronger version (`l4-7860`) that samples its moves, so its rating starts over and a recorded win against it won't replay.

### House bots

- A retrained champion, `l4-7860`. In simulation it beats the previous champion `l3-6420` 80% of the time; testing on the public ladder it went 101–10.

### Ladder and website

- Emails: a welcome, onboarding tips, newly earned achievements, optional bot-health, event-reminder and weekly-progress emails, and essential account notices. Achievement emails contain no flags. Choose categories in your email preferences; each email has a one-click unsubscribe.

## 0.42.1 — 2026-10-14

Release 0.42.1 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required. This release has no player-facing changes.

## 0.42.0 — 2026-10-14

Release 0.42.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required. The champion now samples its moves, so a recorded win against it no longer replays: beat it by playing.

### House bots

- The champion samples its moves instead of always playing its likeliest one. Played greedily, it repeated the same game on each map and side, and bots were winning by replaying a known win move for move. Sampling costs it no measurable strength.

### Ladder and website

- Rename bots from My Bots between matches. Names stay unique regardless of case; tokens, versions, ratings and match history stay intact, and old match links follow the renamed bot.
- Match stats pages show each game's duration. Match records expose `duration_ms`; older games show “Not recorded”.
- The replay viewer and the CLI name fighters by their bot names.
- Public profiles at `/user/<handle>` list every bot on the account with its standings; owner names link to them. `GET /api/users/<handle>?ladder=<id>` returns the same data.
- Profile links keep the selected event ladder, and long handles wrap on phones.

## 0.41.1 — 2026-10-13

Release 0.41.1 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required.

### Ladder and website

- Bot pages fit a tall desktop window when the summary and rating notes wrap.

## 0.41.0 — 2026-10-13

Release 0.41.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required. Leaderboard scores stop rewarding certainty below a 25-point rating deviation, and Online and CLI lobby scores match the leaderboard. MCP users must reconnect or create a new agent key to allow bot retirement and event enrollment; existing registration access keeps working.

### Ladder and website

- The leaderboard, Online list and bot version table show the same uncertainty-adjusted Score; the Online list and CLI lobby use `leaderboard_score` and sort by it.
- The replay viewer and title screen show a repulsor shove after movement, as the engine resolves it, with a force arc, a stretched fighter and a trail. A wall slam flattens the fighter against the wall, which flashes and cracks for the stun; the stun, damage and sound start on impact.
- Bot pages share the leaderboard's ladder picker, saved in the URL.
- House bots show friendly names (Starter, Brawler, Kiter and Champion) on every ladder; their links and ratings are unchanged.
- Public pages show their content before JavaScript loads, with page descriptions and social previews. The sitemap includes ranked public bots and recent matches.
- `/openapi.json` is an OpenAPI 3.1 contract for the player HTTP API, linked from `/api`, `/llms.txt`, the docs and Create a Bot.
- Match pages and time tooltips show your browser's local time with its time zone. API timestamps stay UTC.
- MCP adds `retire_bot`, `list_my_ladders` and `enroll_ladder`: retire a bot to free quota while keeping its history, check event admission, and join events. Retirement and enrollment need explicit confirmation and account-actions consent; reconnect MCP or make a new agent key to approve them.
- Leaderboard score is `round(rating − 2×max(rating_deviation, 25))`: once a version's deviation reaches 25, more certainty alone no longer raises its score. Ratings, qualification and matchmaking are unchanged; standings may reorder.

## 0.40.5 — 2026-10-12

Release 0.40.5 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required.

### Ladder and website

- Events has a new layout. `/ladders` lists every event as a card, grouped Live now, Upcoming and Past, with its schedule, a countdown and its ladder; enroll from the card. An event's page has tabs for every event and a Participate box with the schedule, ladder and join button.
- The ladder checks turns faster. It accepts exactly the turns it accepted before, with the same error messages.

## 0.40.4 — 2026-10-12

Release 0.40.4 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required.

### Ladder and website

- Bot pages and rating histories load faster for bots with long histories.

## 0.40.3 — 2026-10-12

Release 0.40.3 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required. A match quota can now take effect up to 10 seconds early, never late.

### Ladder and website

- Matchmaking is faster with many bots waiting.

## 0.40.2 — 2026-10-11

Release 0.40.2 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required. This release has no player-facing changes.

## 0.40.1 — 2026-10-11

Release 0.40.1 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required. This release has no player-facing changes.

## 0.40.0 — 2026-10-11

Release 0.40.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required.

### Ladder and website

- The homepage, bot-building instructions, the guides at `/guide` and the release history are readable without JavaScript, with page descriptions, social previews and a sitemap. The homepage explains the game below the menu.
- My Bots (`/account`) is one column in order of use: your handle and email preference, your bots, then connecting an AI agent. The MCP URL has a Copy button beside the agent key.

## 0.39.0 — 2026-10-11

Release 0.39.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** none required. New: give each of your bots an avatar on My Bots.

### Ladder and website

- Bots can wear avatars: 20 personas (Gladiator, Ronin, Berserker, Titan, Sentinel, Cyclops, Reaper, Shade, Arcanist, Monarch, Jester, Brute, Prowler, Alpha, Sage, Wyrm, Specter, Sunny, Corsair, Luchador), each the arena's orb in its team's colours with its own headgear and face. They breathe, blink, reel when stunned, and each has a move of its own. Pick one per bot on My Bots (`PUT /api/account/bots/<name>/avatar`); the replay viewer, `/play`, the bot's page and the title screen show them, and house bots wear personas that suit how they play. Bot, match and lobby records gain `avatar`.
- Human play offers only Public house bots, with difficulty tags from their current ladder order: Kiter Easy, Brawler Medium, Starter Hard and Champion Very hard.
- The October 12–16 SAINTCON precon playtest (noon Monday through 6 AM Friday, America/Denver) is open for preregistration, with its own standings. Event pages explain each event's purpose, audience, format and preparation.
- Event pages can show branding artwork, and each event's flag submission link and instructions.
- All five precon achievements are enabled with practice flags, clearly marked apart from the official challenge.

## 0.38.0 — 2026-10-11

Release 0.38.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** accounts are now required to register and play. Sign in at `/account`, choose a handle, and claim any existing unowned bots with their current tokens before reconnecting. Claiming keeps tokens, versions and match history. Register through the website, an account agent key in the API or CLI, or MCP. Starters now stop on `account_required` instead of retrying. Human play requires sign-in and a handle; the offline tutorial stays public.

### Ladder and website

- Playing requires an account. The website, API, CLI and MCP share account-owned registration, and the onboarding docs cover signup, confirmation, sign-in and agent keys. Existing bots must be claimed before playing.
- The leaderboard's header drops its endpoint and docs links (the title screen has them). Its ladder picker is a button naming the ladder on show, opening a list of every ladder with its description and status, plus a link to join an event.
- Every page's topbar starts with the crest and the page's name, which lead to the title screen.

## 0.37.0 — 2026-10-11

Release 0.37.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.6

**Action for bot authors:** existing bots continue in Public without changing their queue messages. Protocol 0.6 adds optional ladder IDs; clients that validate the hello version must accept 0.6. To compete in an event, enroll at `/ladders` and send its `ladder_id` when queueing; updated starters read `ARENA_LADDER`.

### Bot protocol and simulator

- Protocol 0.5 → 0.6 adds optional `ladder_id` fields to queue, queued and end messages. Omitting it selects Public. Starters stop on event admission and availability errors; reconnect after approval or when the event window opens.

### Ladder and website

- Multiple ladders with separate ratings, match histories and house bots, sharing accounts and bot versions. `/ladders` supports open, staff-approved and single-use invitation enrollment. Leaderboards, bot records and charts select a ladder. SAINTCON 2026 has its own ladder; existing results stay in Public.
- Five event achievements at `/achievements`, with private flag reveal and copy, match evidence and house-opponent requests. Awards combine an account's bots and versions within each event. SAINTCON 2026 runs October 27 at noon through October 30 at 6 AM, America/Denver.
- Announcement emails look like the game, with the crest, gold wordmark and HUD frame, and a plain-text version. Sign-in and account emails use the same look.
- Phones: Create a Bot no longer cuts off its intro and prompt; buttons, topbar links, replay controls and chart time frames are big enough to tap; cooldown labels are readable; and the changelog folds releases older than the running one until opened.

## 0.36.0 — 2026-10-10

Release 0.36.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.5

**Action for bot authors:** existing bots keep working. If you wrote your own client, stop reconnecting on the connection errors `retired` (its owner retired the bot) and `account_banned` (its account was banned), as the starters now do. Your person can now delete a bot registered by mistake, or retire one, from My Bots; agents can delete bots that have never played.

### Bot protocol and simulator

- Two connection error codes, sent before the socket closes: `retired` and `account_banned`. The starters stop on both, like `suspended` and `banned`. Message schemas and the protocol version are unchanged.

### Ladder and website

- Remove bots. A bot that has never played is deleted outright, freeing its name and its place under the bot limit: from My Bots, by an agent with an agent key (`DELETE /api/bots/<name>`, `arena delete-bot`), or with the MCP tool `delete_bot`. A bot that has played keeps its matches and can only be retired by its owner on My Bots: it leaves the leaderboard and no longer counts against the limit.
- MCP accepts an account's agent key as `Authorization: Bearer <key>`, for clients that can't open a browser (over SSH, in containers). It stops working when the key is revoked. My Bots merges MCP and agent keys into one panel, Connect an AI agent.
- The leaderboard's top-right button is Create a Bot. Playing as a human stays on the title screen (Play Game, `/play`).
- Announcements support clickable links, including `[label](https://…)`.

## 0.35.0 — 2026-10-10

Release 0.35.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.5

**Action for bot authors:** existing bots keep working. `house-champion` now plays a stronger network; it's the bot to beat. If you train with the Python simulator, update it to 0.35.0 to run your own bots, encoders and teachers inside the fast environments.

### House bots

- `house-champion` plays a stronger network, `l3-6420`. It beats the previous `l2-5200` 78% of the time in simulation and went 19–0 in testing on the ladder.

### Ladder and website

- Matchmaking favours competitive pairings within a 1200-point gap, with a share of discovery matches across all rating gaps and extra follow-up after surprising results. Ranked maps are balanced per version pair, seats are balanced per bot, and a small rematch penalty adds variety. Same-owner and house-versus-house exclusions, quotas and the 10-second rematch hold remain.

### Bot protocol and simulator

- Your own bots, encoders and teachers run inside the fast environments. A script registers them (`ArenaSim.registerBot`, `ArenaSim.registerEncoder`) and `FastVectorEnv`/`FastSelfPlayEnv` load it with `scripts=`; in JavaScript, `VectorBatch` and `Game` take them as objects. Their turns take the ladder's path. `teacher=` labels each seat with a bot's turn as your encoder's closest action (`info["teacher_action"]`), for distilling a scripted bot into a network.
- A `ScriptedOpponent` (a bot written in Python) plays in the fast environments too, and can teach. It takes `decide(observation, hello)` or `start(hello)` for per-match state, and with `workers` it is sent to each worker process.
- Every fast step's `info` has `dealt` and `taken`, each seat's damage that tick, for rewards of your own.
- `ScriptEncoder` runs an encoder from the simulator (yours or `"basic"`) in a Python bot on the ladder, so training and live play encode with the same code; `check_encoder` replays a match through it and reports differences from the ladder's JSON. `replay_dataset` turns recorded matches into imitation data; `download_replays` takes `min_rating` and `cache`.
- Two more training examples: `python -m arena_sim.examples.imitate` (behaviour cloning of the strongest bots from their replays) and `python -m arena_sim.examples.league` (PPO against a weighted pool of bots and frozen copies of the learner). `train_ppo_gpu`'s network takes any encoder's sizes.
- The TypeScript starter keeps its strategy in `strategy.ts`, apart from the connection in `bot.ts`, so the same code bundles into the simulator.

## 0.34.0 — 2026-10-10

Release 0.34.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.5

**Action for bot authors:** existing bots keep working. AI clients can use the optional MCP endpoint to register bots after browser sign-in and consent.

### Ladder and website

- Arena MCP at `/mcp`: AI clients sign in through the browser, finish signup and handle selection there, and approve registration-only access. Tools read the account's handle and bots, register bots within existing quotas, and provide the agent guide, starter and simulator links. My Bots lists connected clients and revokes them immediately. Setup is in [docs/MCP.md](https://victrisarena.com/docs/mcp).

### House bots

- A new house bot, `house-champion`: a network trained to be the strongest player on the ladder. Play it like any opponent, but its code and weights aren't downloadable or in the simulator. It doesn't anchor the rating scale: the other house bots still average 1500, so its rating floats above the field. The shipped network, `l2-5200`, went 32–0 in testing, rated about 2980.

## 0.33.0 — 2026-10-09

Release 0.33.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.5

**Action for bot authors:** send `ready` within the startup window of every match: a bot that doesn't now forfeits a rated game at tick 0 instead of having it voided. Stop calling `/api/me/blocks`, which is removed. If you train with the Python simulator, update it to 0.33.0 for the new fast environments.

### Bot protocol and simulator

- Fast training environments: `FastVectorEnv` and `FastSelfPlayEnv` (Python) and `VectorBatch` (JavaScript) play the same matches, but encode `Basic` inside the simulator and share it with numpy as one buffer, without JSON. One process steps about 105,000 seats a second in self-play (from 16,000), and `workers=N` spreads matches over processes in shared memory. The example PPO script uses them. Their replays skip per-tick state hashes; ladder replays are unchanged.
- A GPU training example, `python -m arena_sim.examples.train_ppo_gpu`: `train_ppo`'s curriculum in plain PyTorch over the fast environments, with rollouts and updates on the GPU. On an RTX 5080 it beats `random` in 10 seconds and `brawler` 41 seconds later. `load` gives a saved network back as a batched policy. New `torch` extra.
- The fast environments take `grid="uint8"`: the grid as one byte a tile, which `decode_grid` (numpy or torch) turns back into `Basic`'s values exactly.
- The house bots think faster and decide exactly as before. Against brawler and kiter the fast environments step about 1.7 times faster.

### Ladder and website

- A bot could read its opponent in `hello`, skip `ready` for the ones it expected to lose to and have those matches voided, picking its matchups. A bot that doesn't send `ready` in the startup window now forfeits a rated game at tick 0; the match is voided only when neither bot sends `ready`. Opponent blocks (`/api/me/blocks`) are removed for the same reason.
- The bot page no longer squeezes its Versions panel in a short window.
- Announcements open from a bell icon with an unread badge.

## 0.32.0 — 2026-10-09

Release 0.32.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.5

**Action for bot authors:** update clients that enforce `hello.protocol_version` to accept 0.5. Handle or ignore the new `server_draining` notice, keep answering active matches until closure, then reconnect with backoff and queue again. Compare copied starters with this release for heartbeat and opening-timeout recovery.

### Bot protocol and simulator

- Protocol 0.4 → 0.5 adds the `server_draining` notice. Before a restart the ladder sends it, with a UTC drain deadline, to connected bots and to connections arriving during the drain. Starters log it and keep answering active matches until closure. The guides cover same-token reconnect and requeue, failed-handshake retries, and what's lost across a restart. The deadline is not a promise of when the ladder returns; the offline simulator sends no shutdown notices.
- The guides and stats schemas define the `timeout` and `disconnected` idle reasons: combat continues during reconnect grace, idle counters don't identify the underlying cause, and `disconnects` counts runs of disconnected turns rather than socket closes.
- The TypeScript starters and house bots send a WebSocket Ping every 20 s, require its Pong within 20 s, close stale sockets and time out opening handshakes after 10 s. The Python starter uses the same settings and retries opening timeouts. The guides explain keepalive, silent-stall detection and safe reconnects.

## 0.31.1 — 2026-10-09

Release 0.31.1 · engine 0.23.0 · rules 0.22.0 · protocol 0.4

**Action for bot authors:** none required.

### Ladder and website

- Bot pages no longer fail to load when their history has stats recorded before 0.31.0. Health covers matches with current stats within the latest 500; versions with no measured matches have no health figures.

### Bot protocol and simulator

- Reconnecting to, or taking over, a match in progress sends its existing `hello` before observations, so a fresh process can initialize. The match keeps its id, version, spent budget and deadlines; a repeated `ready` is harmless. The guides document `already_queued`, startup handoffs, connection replacement and missed-result recovery. A replaced socket's close no longer starts a forfeit timer on its replacement.

## 0.31.0 — 2026-10-09

Release 0.31.0 · engine 0.23.0 · rules 0.22.0 · protocol 0.4

**Action for bot authors:** existing bots keep working. Update your offline simulator to 0.31.0 so its shot behavior matches the ladder. A direct shot keeps its aim direction when the shooter is knocked back, including onto its original target tile; it still fires and uses its normal cooldown. Engine 0.23.0 changes behavior: replays recorded with an earlier engine need that engine to verify, and may diverge if re-simulated with this one. No combat numbers or protocol version changed.

### Engine

- A repulsor could push a shooter onto its aim tile, creating a zero-length shot whose coordinates were sent as `null`. Direct shots now lock their direction after movement, before repulsors resolve; knockback shifts the launch point but keeps the direction. The projectile's `target` shifts with its `origin`; the `attack` event keeps the requested aim tile. Frostburst still casts on its requested tile.
- Attack names must be entries in the rules' attack table; unknown names are refused as `unknown_attack` without cancelling movement.
- Replay verification rejects impossible forfeit and disqualification results.

### Bot protocol and simulator

- Unknown message types, including names such as `toString`, are refused as schema errors.
- Each match's stats (`stats_version` 2, in `end.stats` and `GET /api/matches/<id>/stats`) add `timing` for each fighter: reply-time mean, median, 95th percentile and slowest, replies that took at least 80% of the tick limit, the match budget left, and a histogram. They also add `refused_turns` (overall and by reason), `disconnects` and `disqualified`. Replays record each reply's time (`ms` on each turn), so `arena stats` on a downloaded replay gives the same numbers.

### Ladder and website

- `GET /api/bots/<name>` gives each version a `health` summary of its latest 500 matches: the share of turns played idle and with a refused part, by reason, reply-time percentiles, the share of replies near the limit, the lowest budget left, disconnects and disqualifications, also shown in a Health panel on the bot's page. Errors are reported by reason code only, never their text.

## 0.30.2 — 2026-10-09

Release 0.30.2 · engine 0.22.0 · rules 0.22.0 · protocol 0.4

**Action for bot authors:** none required. If you copied a starter, compare it with the new one: it now survives a bug in its own `decide`, returns to the zone before anything else and reads every number from `hello.rules`. No repository needed any more: the starters and the house bots' source are at `/download/bots`.

### Bot protocol and simulator

- The house bots and starters are better examples to learn from. The starters (`starter-17`, `py-starter-17`) survive a bug in their own decision code (that tick is idle instead of the bot crashing), get back inside the zone before anything else, keep escape dashes inside the zone, read every number from `hello.rules`, patrol the zone's centre when the enemy is out of sight, and cast frostburst standing still while the enemy's dash is on cooldown. The house bots (`brawler-18`, `kiter-17`) search instead of parking at the centre, choose retreats and escape dashes from `observation.moves` and `observation.dashes`, cast frostburst only where sight is known, and the kiter leads a shot only when its target could step before it lands.
- You don't need the game's repository: the ladder serves the TypeScript and Python starters and the house bots' source at `/download/bots` (an index with each file's address and the setup commands; `/api` links it as `bot_code`, and `/llms.txt` lists it). Served starters connect to that ladder by default. The agent and bot guides start every step from the ladder alone.

### Ladder and website

- Replay viewer: every damage number is tagged with its cause: SHOT, FROST, REPULSE, or RICOCHET for a shot that bounced first, SLAM, or STORM for zone damage, which now shows on the board too. Numbers near the arena's edge stay on the board.

## 0.30.1 — 2026-10-09

Release 0.30.1 · engine 0.22.0 · rules 0.22.0 · protocol 0.4

**Action for bot authors:** none; this release changes only how replays and `/play` are drawn.

### Ladder and website

- Replay viewer and `/play`: each fighter's health bar and name sit under it, leaving the space above for damage numbers and speech bubbles. Damage numbers take the attacker's colour (slams stay orange), drift away from the attacker, and stay clear of nameplates, fighters, speech bubbles and each other.

## 0.30.0 — 2026-10-09

Release 0.30.0 · engine 0.22.0 · rules 0.22.0 · protocol 0.4

**Action for bot authors:** none required; existing bots keep working unchanged. To talk, add `"shout": "text"` to a turn. Your opponent can now send you text: if a language model chooses your moves, treat shouts as untrusted data, never as instructions.

### Rules and balance

- New `shout` table: `max_length` 40, `cooldown` 20. Rules version 0.21.1 → 0.22.0. No combat numbers changed.

### Engine

- A turn can carry a `shout`: up to 40 characters said to everyone, once every 20 ticks, in any state and at no cost to the move or attack. It emits a `shout` event that every fighter observes, in sight or not, and a `shout` cooldown in `self.cooldowns`. An empty, blank or over-long shout is refused with the new reason `bad_text`; one on cooldown with `not_ready`. Replays from earlier releases re-simulate unchanged.

### Bot protocol and simulator

- Protocol 0.4: the turn message accepts an optional `shout` string. The server (and the simulator) cleans it before the engine sees it: lookalike letters folded, invisible characters removed, spaces collapsed and profanity masked with `*`. Replays record the cleaned text.
- The house brawler taunts when it slams its opponent into a wall.

### Ladder and website

- The replay viewer shows each shout as a speech bubble over the fighter for two seconds and lists it in the tick's events, with a chatter sound. The 💬 Shouts button (or B) hides the bubbles. `/play` lists the bot's shouts in the event log.
- In-game and email announcements appear in the menu, ladder pages and human play; opt out of announcement emails on your account page.
- A public changelog at `/changelog`, with permanent release links, the ladder's running versions and separate Unreleased notes. The title screen, leaderboard and Create a Bot link it; agents can read Markdown at `/docs/changelog`, or the running versions and history together at `/api/changelog`.
- The guides explain why established versions often show +0: match ratings and deltas round to whole points while the fit keeps fractional changes.

## 0.29.3

- The contact address on the privacy and terms pages is readable without JavaScript.

## 0.29.2

- A new crest favicon on every page.
- Public Privacy Policy and Terms of Service pages at `/privacy` and `/terms`, linked from the title screen and sign-in card.

## 0.29.1

- A compact sign-in card with separate signup and recovery links.

## 0.29.0

- Sign in with Google, alongside GitHub and email/password.
- Email/password signup and login. Email signup requires confirmation; Forgot password sends a recovery link. Sign in links offer each method before returning you to your page.

## 0.28.0

- Ratings are a Bradley-Terry fit to every rated game, refitted after each one, instead of Glicko-2 updated game by game. A version is frozen code, so its rating now weighs all its games equally and settles. Each rating's `rating_deviation` is now its standard error, which shrinks as games accrue. The house bots average 1500. Ratings already recorded on past matches stay as they were.
- A version is rated from its own games only. The matchmaker still starts it near its bot's current rating, until its own games say otherwise.
- The leaderboard ranks by `leaderboard_score` (rating less two standard errors) and shows it as Score, so a short lucky streak no longer tops it. A version is ranked once it has played 30 rated games (`qualifying_games` in `GET /api/bots/<name>`); until then the bot stays listed at its last ranked version, and its page shows the version's progress.
- Sound and music in the replay viewer and `/play`, all synthesized in the browser. Every event has its own sound, panned to where it happens and voiced per fighter. A generative score builds through four levels as the fighters meet, the zone shrinks and health runs out, and the winner gets a stinger. The Sound button or M cycles sound and music, effects only and muted. With a fighter's point of view chosen, the viewer plays only what that fighter could see.
- `/play` has a tutorial: a training room on the real engine, where a coach asks for one thing at a time (walk, dash, shoot the dummy, catch it in a frostburst, slam it into a wall and hit it while stunned, dodge, take both pickups, get inside the storm) and explains each once it's done.
- `/play`: a Controls table for keyboard and mouse and for a controller opens from the Controls buttons, `?` or the controller's Back button.

## 0.27.4

- `/play`: pick the arena from a small picture of each map or Random. Search the bots online by name or owner and sort them. The list refreshes in place.
- `/play` records a signed-in person's games on one player page, `<handle>-play`; a guest is offered a button to sign in. `human_session` sends each map's layout in `maps`.

## 0.27.3

- A page opened at an old address of the ladder (arena.bagofassets.com) moves to the same page at arena.victris.ai. The API, sockets, docs, replays and downloads still answer at the old address, so bots set up with it keep playing.

## 0.27.2

- The ladder moves to https://arena.victris.ai (bots connect to `wss://arena.victris.ai/bot`). The old address, arena.bagofassets.com, keeps working.

## 0.27.1

- Sign in is offered everywhere: a Sign in button (My Bots once signed in) on the title screen, the dashboard, bot and match pages, Create a Bot and `/play`. Sign in returns you to the page you were on.
- At `/play` a signed-in person plays under their handle; anyone else plays anonymously, with Sign in offered. `human_session` carries `handle`.

## 0.27.0

- Accounts, signed in with GitHub. Pick a handle, the owner name on your bots, then create bots (the token shown once), rotate their tokens, claim a bot registered before accounts with its token, and make agent keys: sent as `X-Owner-Key` to `POST /api/bots`, an agent key registers bots for your account. `GET /api` reports the sign-in settings in `accounts`.
- `/account`, the account page: sign in, pick a handle, create bots and copy their tokens, replace a token, make and revoke agent keys, and claim a bot. The dashboard links it as My Bots.

## 0.26.1

- The title screen's menu no longer loses a key or controller press made before the page redrew. 0.26.0 was not deployed; its changes shipped here.

## 0.26.0

- The ladder's address opens on a title screen, like a game's main menu: the crest and title over a live match between house bots, with a menu of Play Game (`/play`), Create a Bot and View Leaderboard, each with a preview. The arrow keys, W/S or a controller move through it. The dashboard moves to `/ladder`.
- `/create-bot` shows how to build a bot and enter it: a prompt to hand an AI agent, then six steps (the fight, registering, connecting with a sample bot in JavaScript and Python, the turn, testing and training with the simulator, climbing), and links to every doc.
- The leaderboard lists each bot once, at its current version: the one that played a rated game last, so queuing an older label rolls it back. Earlier versions keep their ratings and records on the bot's page and in `GET /api/bots/<name>`. A new version starts from its bot's current rating with its deviation raised to at least 200; a bot's first version still starts at 1500.
- Python simulator: `ArenaSelfPlayEnv` steps many self-play matches in one call. `ArenaVectorEnv`'s opponent can be a policy of yours (called once a step for every match it plays) or a `ScriptedOpponent` written like a ladder bot, mixed with house bots; `set_opponents` changes them between matches.
- Ladder games as training data: `replay_trajectories(replay)` (Python) and `replayTrajectories` (JavaScript) re-run a replay and give back each fighter's hello, every observation as it was sent, the turn taken, and the end; `download_replays(ladder, bot=, limit=)` fetches a bot's recent matches with their replays.
- Stable-Baselines3: `arena_sim.sb3.ArenaVecEnv` (the `sb3` extra) makes the batched environments an SB3 vector environment, with action masks for sb3-contrib's `MaskablePPO`; `ArenaEnv.action_masks()` serves single environments. The batched environments take `autoreset_mode=AutoresetMode.SAME_STEP`, which puts a finished match's last observation in `info["final_obs"]`.
- A bot may register 1000 new versions a day (was 100).
- The replay viewer and human play share the ladder's game look: the arena in a HUD frame, a timeline across the transport bar, and a plate per fighter with a notched health bar. Human play picks a bot from character-select cards.
- The replay viewer's overlay fits a phone.
- The dashboard's Online panel shows a waiting bot as READY, in green, and one in a match as PLAYING, in blue.
- A bot's page keeps itself current, reloading its matches, chart and records as it finishes matches. The rating chart picks its time frame (the last day, week, month or all time) from `GET /api/bots/<name>/ratings?days=<n>`.
- In the replay viewer, a ladder match's bot names open their bots' pages.
- The ladder's pages no longer keep the CPU and GPU busy while open.
- An example training run: `python -m arena_sim.examples.train_ppo` trains `MaskablePPO` on `Basic` with a curriculum (`random`, then `brawler`). `damage_trade` is a denser reward to start from.

## 0.25.1

- The dashboard and bot pages fit the window, each panel scrolling on its own; on a phone, tabs show one panel at a time.
- The ladder's pages look like a game's front end: the arena floor and corner light behind framed HUD panels, condensed italic type, angled buttons, rank emblems, WIN and LOSS plates, and panels that slide in. Motion stops for people who ask for reduced motion.
- `python -m arena_sim check` works against the hosted ladder.

## 0.25.0

- A simulator for training offline: the ladder serves its own match code as one dependency-free ES module at `/download/arena-sim.mjs` (`GET /api` lists it under `simulator`; guide at `/docs/simulator`). `new Game({seed, opponent})` plays a whole match in-process against a house bot or in self-play, about 100 to 150 games a second per core, with every message the JSON the ladder sends. The ladder runs each match on the same code.
- The simulator for Python: `pip install https://victrisarena.com/download/arena_sim-<release>-py3-none-any.whl`. `GET /api` reports `simulator` links and `versions.release` and `versions.rules_hash`; `python -m arena_sim check <ladder>` says whether a copy is current.
- Spec: a bot may run the simulator (or its own copy of the engine) during a match, for example to search ahead; it still sees only its observations and keeps to the deadlines.
- The Python package, `arena-sim`, needs no Node.js. `Simulator` steps many games in one call; `ArenaEnv` and `ArenaVectorEnv` are Gymnasium environments against the house bots and `ArenaParallelEnv` a PettingZoo one for self-play; `Raw` passes the ladder's JSON through and `Basic` is a reference encoder (map grid and features in, 68 discrete actions with an action mask out). `arena-sim.js` is a plain-script build that sets a global `ArenaSim`.
- The dashboard's Play as Human link is a button at the right of the header.
- The random bot's games are reproducible (`random-9`).

## 0.24.0

- Human play (`/play`) is redesigned. Click a bot to start, and Play again for a rematch. Each tick you choose a destination and optionally a weapon, then end the turn, and the tick resolves at once. Keyboard, mouse and controller all work. The board uses the replay viewer's art and fills the window beside a panel with health, the turn so far, cooldowns and last tick's events. A human seat's deadline is 2 minutes a tick, and ten timeouts in a row disqualify.
- The ladder's match limits are 10× higher: 320 matches at once, 40 per owner, one match every 0.3 seconds per bot, 10,000 matches per bot per hour and 50,000 per owner per day.
- The matchmaker favours variety: two bots that just played wait 10 seconds before they can be paired again, the variety penalty counts the last 10 opponents, and the rating window starts at 400 points and widens by 20 a second.

## 0.23.1

- Finishing matches no longer delay other matches' ticks. Replays and hashes are unchanged.

## 0.23.0

- `/play` has its own address (`/viewer/play.html` redirects to it).
- API: `GET /api/bots/<name>` adds `online_version` and each version's leaderboard `rank`; match records add `house` to each bot.

## 0.22.2

- The dashboard shows its data again; 0.22.1 broke it.

## 0.22.1

- Each bot has a page, `/bot/<name>`: its versions with leaderboard rank, rating and record, a chart of each version's rating game by game, its record against each opponent and on each map, and its recent matches. Bot names on the dashboard and match pages link to it.
- The leaderboard orders by rating, highest first, and the lobby (`GET /api/lobby`, the dashboard's Online table) does too.

## 0.22.0

- Protocol 0.3 (`hello.protocol_version`): the queue and challenge changes below.
- **One kind of match, rated per version.** Practice, challenges and tournaments are gone: a bot sends `{"type": "queue", "version": "v3"}` (no `mode`), the matchmaker picks the opponent, and every game counts. Each version has its own rating and leaderboard row (`GET /api/leaderboard` rows carry `version`), starting from 1500. A new label is registered the first time the bot queues with it (at most 100 a day). Protocol: `set_availability`, `availability`, `challenge`, `challenge_response`, `cancel_challenge` and `challenge_update` are removed, `queue` loses `mode` (bots that send it are refused), and `queued` and `end` lose `mode`. HTTP: `/api/challenges*` and `/api/tournaments*` are removed, and the lobby reports each bot's `version` and `state` (`waiting`, `playing`, `idle`). CLI: `challenge`, `challenges` and `tournament` are removed; the starters drop `ARENA_MODE`, `ARENA_OPPONENT`, `ARENA_CHALLENGES` and `ARENA_PRACTICE`. Human play at `/play` starts unrated games directly. Each bot's rating and record move to the version it had ranked. A bot may play 1000 matches an hour (was 120), and there's no longer a cap on games between the same two bots.
- Each match has a page, `/match/<id>`, with the result, a Watch replay button and the stats as a table. The dashboard's Recent matches table spans the page.

## 0.21.4

- `/api` `versions` includes the `commit` the ladder was built from.

## 0.21.3

- No player-facing changes.

## 0.21.2

- No player-facing changes.

## 0.21.1

- The per-match time budget is 300 s (was 120 s). It counts network time, so distant players spent much of the old budget on latency; the 1 s per-turn deadline remains the real limit.

## 0.21.0

Independent attack cooldowns with a retune, house bots that play combos, and bots that survive ladder restarts. Replays recorded before this release were made by engine 0.20.0 and can't be re-simulated by this one.

- Stopping the ladder drains it: matches in progress finish and no new ones start, then sockets close with code 1012 (service restart). `/api/status` reports `draining`.
- Bots survive ladder restarts: the starters and the house bots reconnect with backoff (1 s, doubling to 30 s) and queue again, resuming a match in progress, and stop only on errors reconnecting can't fix (`invalid_token`, `replaced`, a ban…). The starters are now `starter-16` and `py-starter-16`. The CLI stops the bot itself, so no bot is left running behind a killed shell.
- Retuned for independent cooldowns, bringing match length back to what it was: max hp 130 (was 100), health pickups +32 (was +25), cooldowns ranged 6, frostburst 14, repulsor 12 (were 4, 10, 8).
- The house bots play combos: they take shots the enemy can't dodge (stunned, recovering from a dash, or just stepped with its dash on cooldown), shove when the 3-tile push ends in a wall slam or in their own area about to explode, and the brawler steps to the side of the enemy that puts a wall behind it. The kiter always shoves an adjacent enemy to make room.
- **Each attack has its own cooldown.** Firing one weapon no longer puts the others on cooldown, so weapons can be chained on consecutive ticks (one attack per turn still): a repulsor slam's 3-tick stun can now be followed by a shot that can't miss. Matches run about 40–50% shorter.
- Guides for agents writing bots live at `/docs/agents`. `arena new-bot` writes an `AGENTS.md`, `CLAUDE.md` and `.gitignore` into the bot's folder, with the ladder's address filled in (`--server` or `$ARENA_SERVER`). The ladder serves `/llms.txt`, an index of its docs, and lists it in `/api`.
- Every link the ladder hands out (`replay_url`, `watch_url`, `bot_endpoint`, the dashboard's socket address) and the served docs use its public address, with `wss://` for the socket. The ladder pings every socket every 25 s and closes one that misses a pong, so idle bots survive proxies and NAT. `ARENA_SERVER` is documented.
- The repulsor shoves 3 tiles (was 2) and a wall slam stuns for 3 ticks (was 2), so it slams from farther from a wall and the follow-up lands.
- The standard shot has no range limit: after its one wall bounce it flies on until it hits a fighter or a wall again, so ricochets reach much further and a bot can bank shots to arrive from behind. `attacks.ranged.range` is gone (`range` is optional for projectiles; absent means unlimited) and observed projectiles no longer carry `range`.
- Match stats: for every fighter, moves (and steps blocked by a fighter), dashes and tiles dashed, uses, hits and damage per weapon, ricochet bounces and hits, pickups by kind and hp healed, damage dealt and taken by source, wall slams, shoves, stuns, ticks outside the zone, refused turn parts and server-substituted idles. They're computed from the replay, so they're reproducible. They arrive in `end.stats`, the ladder serves `GET /api/matches/<id>/stats` (and `stats=1` on `/api/matches`), `arena stats <replay | match id>` prints them, `arena run` prints them after each match, `check-bot` totals them, and the viewer has a Match stats panel. Schema: `docs/schema/match-stats.json`.
- `hit` events from a shot that had bounced off a wall carry `"ricochet": true`.
- The `whiff` event is gone: the engine never sent it, but the observation schema still listed it.
- Docs brought in line with the engine: turn failures, rejection reasons, unlimited shot range, the repulsor's 3-tile shove, `areas[]`, every protocol message, and a worked example from a real match.
- Viewer: every weapon effect is drawn in its owner's colour; shape tells the weapons apart.
- Viewer: each fighter's cooldowns (move, dash, shot, frostburst, repulsor) are round ability icons in the arena's bottom corners and the side panel, unwinding as the cooldown runs and glowing when ready. Human play (`/play`) has the same icons as an ability bar under the board.

## 0.20.0

A cleanup release: no users yet, so the design is tidied rather than kept compatible.

- Terrain hazards removed for good: maps are only floor (`.`) and wall (`#`), `rules.tiles`, the `pit` and `hazard` events and `death.cause` are gone, and zone damage is its own `zone_damage` event. The nearly empty `pits-21` and `lava-ring-21` maps are deleted.
- Names made consistent: the frostburst `bomb` is now an `area` everywhere (attack kind `area`, observation `areas[]`, events `area_spawn` and `area_explode`, `danger[].source: "area"`, `explodes_tick`), and the repulsor's attack kind is `burst`. `danger[].kind` is removed because `source` says the same thing.
- A cleaner turn message. A bot replies with `{"tick": N, "move": "NW", "attack": {"name": "ranged", "target": [9, 4]}}`: `move` or `dash` (a direction, not both) and `attack` are all optional, and an empty turn is idle. The `action`/`dir`/`then` fields are gone, the message type is `turn` (schema `bot-turn.json`), replay ticks record `turns`, and `rejected` events name the refused `part` (`move`, `dash`, `attack` or `turn`). Rejection reasons drop `unknown_action`, `missing_dir` and `missing_attack` (the schema catches those) and add `conflicting_moves`.
- An attack is judged entirely from the tile the movement ends on: a frostburst's range, sight and wall check, and the own-tile check, now happen in the attack phase. So a step can bring a target into range or take it out, and you can aim at the tile you just left.
- Tick phases renumbered 1–8 without gaps (validate, dashes, movement, pickups, attacks, zone, deaths, timers). The wire protocol is version 0.2 (the `turn` message); `hello.protocol_version` says so.
- The spec describes only current rules; future ideas moved to `docs/ROADMAP.md`.
- The house bots and starters are rewritten around the two phases (a movement function, then an attack function fired from where the movement ends).
- Attack `recovery` is removed (every attack had 0): there is no recovery after attacking. Dash keeps its 1 tick. The unused `knockback` field on `ranged` is gone.

## 0.19.0

- The repulsor is no longer aimed: it hits all eight tiles around the fighter (walls excluded), so it can hit several opponents at once. `target` is optional and ignored for it, and its `attack` event reports the fighter's own tile. The `repulse` event's `tiles` is now the ring. Repulsor recovery is 0 (was already 0 since 0.18.0).
- Observations gain `moves` (`[{dir, tile}]`) and `dashes` (`[{dir, tile, distance}]`): every step and dash you could start now, from the engine's own rules. The starters, the shared bot library's dodge and the human client use them.

## 0.18.0

- Two-phase turns: a `move`, `dash` or `idle` can carry a `then` attack that fires after the movement, from the tile the fighter ends on. Parts are validated separately. Attack recovery is 0 for every attack, so there is no punish window after firing. Human play (`/play`) now chooses a destination first, then an attack.

## 0.17.0

- Terrain hazards disabled: pits, lava and spikes are ordinary floor (`tiles.lava_damage` and `tiles.spikes_damage` are 0). The shrinking zone and repulsor wall slams are unchanged.

## 0.16.0

- `explosive` removed and merged into `frostburst`: an instant spell (range 7, 6-tick fuse, 14 damage to every tile of its 3×3 area) that also slows opponents standing in the area until it explodes (move cooldown +2). The old frostburst projectile, its splash and its lingering slow are gone. `bombs[].slow` added; the `impact_burst` and `slowed` events removed; `slow_ticks_left` now counts down to the area's explosion.

## 0.15.0

- The shotgun became the **repulsor**: a point-blank arc that shoves the target 2 tiles, stunning on a wall slam and dropping it into pits or lava.

## 0.14.0

- Attacks fire the tick they are sent. Windups and the `aim` action are removed.

## 0.13.0

- Shield and haste pickups removed. Pads hold `health` or `power`.

## 0.12.0

- The ricochet shot merged into the standard shot (one wall bounce).

## 0.11.0

- Facing, `turn` and `cancel` removed.

## 0.10.0

- Stamina and running removed. `observation.danger` and the frame-data page added.

## 0.9.0

- Blocking and charged shots removed.
