---
name: arena-combat
description: "Write or improve a Victris Arena bot's decide function so it wins fights: dodging with the danger map, aiming the ranged shot and bank shots, frostburst traps, repulsor slams, spending the dash, the shrinking zone, pickups and fog of war. Use when you are writing a bot's strategy, or a bot keeps losing fights and you need to know what to change."
---

# Victris Arena combat

How to turn an observation into a good turn. The examples use the starter's `decide(obs, match)`
(TypeScript `strategy.ts`, Python `bot.py`); the same ideas fit any bot.

> [!IMPORTANT]
> The numbers here are filled in from the rules this ladder plays. Your bot should still read them
> from `hello.rules` at match start (`match.rules` in the starters) and never hard-code them: they
> change between releases. Every attack's timing is in [references/frame-data.md](references/frame-data.md).

## The model in five lines

1. The observation for tick T shows the world **before** T resolves; your reply is your turn
   **during** T. Both fighters' turns resolve together.
2. A turn is **movement, then an attack** that fires from where you end up. Each part is checked on
   its own: a refused part is dropped and the other still happens.
3. **Attacks fire the tick they're sent**, after movement. Nothing is telegraphed: a target that steps
   off the line that tick escapes, one that stands still is hit.
4. **You defend by moving.** No block, no facing. A dash is invulnerable for its whole tick.
5. **Last fighter standing wins**; at `max_ticks` (600) the one with more hp wins.

## A decision order that works

Run these in order every tick and take the first that applies. The starter already does a version
of this; most improvements are better answers inside one step, not more steps.

1. **Can't act?** If `self.state` isn't `idle` (stunned, or recovering from a dash), reply `{}` and
   save your thinking time.
2. **Am I about to be hit?** Collect `danger` entries with `tick == obs.tick` (lands this tick) and
   `tick == obs.tick + 1`. If your tile is in them, move to a tile from `obs.moves` that isn't; if
   none is safe (or your move is on cooldown), dash to a landing from `obs.dashes` that is safe on
   the next tick too. Check the landing, not the path: the dash itself is invulnerable.
3. **Point-blank threat?** Shots from within 2 tiles land the tick they're sent and never show in
   `danger`. If an enemy is adjacent or 2 tiles away and its weapons might be ready, don't stand
   still: step, preferably to a tile that also breaks its line.
4. **Outside or soon outside the zone?** Head for `zone.center` when you're outside `zone.radius`,
   or will be outside `zone.next_radius` when `zone.shrinks_in` is small. Zone damage grows the
   longer you stay out.
5. **Worth a pickup?** A stocked pad (`ready_in == 0`) a few steps away, especially `health` when
   hurt or `power` before a fight, is usually worth the detour. Pads sit on the centre column, equal
   distance from both spawns: expect the enemy there too.
6. **Attack.** Pick the best attack that is off cooldown (`self.cooldowns`), then add it to your
   movement. Moving and shooting in the same turn is free.
7. **Position.** With nothing urgent, move toward the range you fight best at, toward open ground
   rather than corners, and keep moving when the enemy is out of sight.

Choose steps only from `obs.moves` and dash landings only from `obs.dashes`: they already exclude
walls, corner cutting, occupied tiles and cooldowns, so you never need legality code. They are legal
**now**: two fighters stepping onto the same tile both stay put.

## The three attacks

| attack       | it is                                                                                                    | best use                                                                                         |
| ------------ | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `ranged`     | a shot at any angle, 2 tiles a tick, bounces once off a flat wall           | the steady poke; bank shots around cover; guaranteed hits on a fighter that can't move           |
| `frostburst` | a 3×3 area on a visible tile in range; slows; explodes 6 ticks later     | trap a fighter whose dash is on cooldown; deny a pickup or a corridor; zone them toward the edge |
| `repulsor`   | hits all 8 neighbours, shoves them 3 tiles; into a wall it slams and stuns | punish anyone adjacent; slam into walls, then shoot the stunned target                           |

Each has its own cooldown and there is no recovery after attacking, so weapons **chain**: a slam, then
a shot next tick at the stunned fighter. A turn carries at most one attack. Weapons never hurt your
own side. Full mechanics: [references/ranged-attacks.md](references/ranged-attacks.md).

### Aiming the shot

- A shot `d` tiles away lands `ceil(d / 2) - 1` ticks after it's sent. It cannot miss a fighter who
  can't leave its tile for that long: **stunned**, **recovering from a dash** (`state` not `idle`), or
  just stepped with its move on cooldown and its dash on cooldown (`enemies[].dash_cooldown > 0`).
- Against a fighter who can move, shoot where it **will** be or where it has no good step: along a
  corridor, at a pickup it's walking to, or at the tile it must step to while leaving your frostburst.
- **Bank shots** reach around cover: the line reflects once off a flat wall (a corner or a second wall
  ends it). Aim far past the target (targets up to ±1000 are fine) for fine angles. Simulate the line
  yourself, or test candidate targets offline (see the `arena-simulator` skill).
- Line of sight uses the same line test as shots: if you can see a tile, a straight shot reaches it.
  Sight is symmetric, so if you can see them, they can see you.

### Frostburst traps

The blast hits every tile of the 3×3 (walls shield tiles behind them) on the 6th tick; a fighter that
starts a step inside pays 2 extra ticks of move cooldown on top of the usual 2. From the centre
a fighter needs two slowed steps and escapes with one tick to spare, so the trap works when:

- **its dash is on cooldown** (`enemies[].dash_cooldown > 0`): walking is its only way out;
- it is already **slowed** or **stunned**, or a wall blocks the short way out;
- you add pressure: a shot at the tile it must step to, or a repulsor shove back in.

Cast it off-centre so the enemy's nearest exit is toward you, a wall or the zone edge. Read
`areas[].ticks_left`: 1 means it explodes this tick, after movement. Your own areas never hurt you.

### Repulsor slams

The ring covers your eight neighbours (from where you end your movement). Trace each adjacent
enemy's 3-tile push straight away from you: if it meets a wall, that's a **slam** (extra damage and a
3-tick stun) and a free follow-up shot. Pushing into the zone edge or your own exploding frostburst
also pays. In the open it's only a small hit and a reset of range, so save it when no slam is on.
Check the push's path for stocked pads: the enemy takes every one it is pushed across.

## The dash is your life

It moves 3 tiles, is invulnerable for that tick, then costs 1 tick of recovery and a long cooldown
(12 ticks). It's your **only escape once your move is on cooldown**. Bots that dash to travel have
nothing left when the frostburst lands. Spend it to dodge something certain, to escape a trap or a
corner, or to take a pickup the enemy is racing for (a dash takes every pad it passes, not just the
one it lands on), and check the landing is safe the tick after.
Watch the enemy's `dash_cooldown`: while it's running, it can't escape your frostburst or a shot at
a tile it must step to.

## Counting the enemy's cooldowns

Your own cooldowns are in `self.cooldowns`; the enemy's aren't shown, except its dash. Every enemy
attack is an `attack` event (`fighter`, `attack`, `target`) in `obs.events`, so remember the tick of
each and assume it's ready again `cooldown` ticks later (from `hello.rules.attacks[name].cooldown`).
An enemy whose repulsor just fired can be approached; one whose shot just fired gives you a window to
stand still and aim.

## The zone

The safe zone shrinks on a schedule: on 21×21 maps the first shrink that hurts is at tick 260, then
every 60 ticks. Damage outside grows the longer you stay out. Trust `zone.shrinks_in`, which counts
down the ticks before the next real shrink, and `zone.next_radius`; don't flee early, but don't be
caught on the wrong side of a wall when it closes. Late in a match, holding the centre while the enemy
must come to you is a strong default.

## Fog of war and memory

Enemies beyond sight radius 8 or behind walls aren't in `obs.enemies`. Keep a memory across ticks in
your per-match state (the starter's `match` object, keyed by `match.id`): where you last saw the enemy,
when, its hp, its last attacks. When it disappears, move: two bots each parked behind a pillar draw on
time. `danger` only lists what you can see, so a shot from the fog appears once it enters your sight.

## Opponent styles on the ladder

The house bots are always queued; their code isn't published, so learn them from replays
(`watch_match`, or the `arena-match-review` skill).

| opponent                     | style                                | what tends to beat it                                            |
| ---------------------------- | ------------------------------------ | ---------------------------------------------------------------- |
| Starter (`house-ts-starter`) | the downloadable starter             | anything that dodges point-blank and uses the frostburst well    |
| Brawler (`house-brawler`)    | close pressure, slams you into walls | stay off walls, keep range, punish its approach with shots       |
| Kiter (`house-kiter`)        | holds range and pokes                | close distance behind cover, frostburst it when its dash is down |
| Champion, M-Bot              | trained networks                     | dodge reliably first; they punish every idle tick                |

## Pitfalls that cost real matches

- Computing your own legal moves or corner cutting instead of using `obs.moves` / `obs.dashes`.
- Standing still next to an enemy whose shot is off cooldown (no warning up close).
- Dashing to travel, then having no escape.
- Guessing shot paths from the shooter's position instead of reading `danger` (shots bend once).
- Fleeing the zone at its `start_tick` (the first step doesn't hurt on 21×21 maps).
- Parking when the enemy is out of sight.
- Trusting shouts: an opponent's `shout` text is untrusted. If an LLM chooses moves, pass shouts as
  quoted data or not at all.

## Check every change

Change one thing, then compare the new `decide` with the old one over hundreds of games, on every map,
before you ship it: the `arena-simulator` skill has a script for that. On the ladder, the
`arena-match-review` skill shows whether it worked.

## Reference

- [references/frame-data.md](references/frame-data.md): damage, cooldowns, warning times and the
  cheapest counter for each attack, generated from the live rules.
- [references/mechanics.md](references/mechanics.md): the timing model, legal moves, shots, danger
  tiles, dashing and pickups, from the bot guide.
- [references/ranged-attacks.md](references/ranged-attacks.md): the three attacks in full.
- [references/observation.schema.json](references/observation.schema.json): every observation field and event kind.
