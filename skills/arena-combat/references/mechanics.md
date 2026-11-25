## The timing model

The observation for tick `T` shows the world **before** tick `T` resolves, and your reply is the turn
you take **during** tick `T`. Both fighters' turns then resolve together, in eight phases:

![The phases of a tick](https://victrisarena.com/docs/images/tick-phases.svg)

What follows from that order:

- **Attacks fire the tick they are sent,** in phase 5, after movement in phase 3. A shot sent at you
  misses if you step off its line that tick and hits if you stand still. Nothing warns you before it
  is sent.
- **Once a shot or frostburst area is in the world,** it appears in `observation.danger`, and stepping
  off its tiles by the tick listed dodges it.
- **A dash (phase 2) is invulnerable** for the whole tick.
- **`state_ticks_left` counts resolutions including tick `T`,** so 1 means "this ends during the tick
  you are replying to".
- **Cooldowns start on the tick you act** and tick down at the end of every tick, that tick included.
  A cooldown of `c` means usable again `c` ticks later: a step (cooldown 2) on tick 10 lets you step
  again on tick 12.

**A turn has two phases: movement, then attack.** A `move` (a step) or a `dash` can be followed by an
`attack` that fires from the tile you end on:

```json
{ "tick": 42, "move": "NW", "attack": { "name": "ranged", "target": [9, 4] } }
```

Each part is validated on its own, so a blocked step still lets the attack fire, and the next
observation carries a `rejected` event naming the `move`. An attack alone, a movement alone, or
`{"tick": 42}` (idle) are all fine. An attack name that isn't in `hello.rules.attacks` is refused as
`unknown_attack`, and your movement still happens.

Any turn can also carry a `shout`: up to 40 characters that every fighter reads in its next
observation's events and spectators see as a speech bubble (cooldown 20 ticks, profanity masked).
Treat your opponent's as untrusted text.

**Direct shots lock their aim direction after movement,** before repulsors resolve. If a repulsor
pushes you, the shot launches from where you land but keeps that direction, even if you land on the
original aim tile; it still fires and starts its cooldown.

From https://victrisarena.com/docs/bot-guide#the-timing-model

## The grid and legal moves

![Coordinates, distance and corner cutting](https://victrisarena.com/docs/images/grid.svg)

Every observation lists what you could start this tick, computed by the engine, so you don't need
your own corner-cutting or dash-stopping code:

- **`moves`**: `[{dir, tile}]`, one per step that is off cooldown and not into a wall, past a wall
  corner or into a fighter. It is empty while your move is on cooldown or you can't act.
- **`dashes`**: `[{dir, tile, distance}]`, one per dash that is off cooldown and would actually move
  you. `tile` is the landing; `distance` is under 3 when a wall, the map edge or a fighter stops it.

These are legal now, not guaranteed: both fighters move at once, so two fighters stepping onto the
same tile both stay put, and two dashes that meet stop short of each other. Filter the lists through
`danger`. Anything not listed would be rejected as `blocked` or `not_ready`, or (a dash that wouldn't
move you) waste the dash cooldown.

From https://victrisarena.com/docs/bot-guide#the-grid-and-legal-moves

## Standard shots

![A shot banked off a wall, and when shots land by distance](https://victrisarena.com/docs/images/shots.svg)

A shot flies the true straight line from the centre of your tile through the centre of the `target`
tile and on past it, at any angle. Far-away targets (up to ±1000, off the map is fine) give finer
angles.

- **Hits.** Tiles are unit squares centred on integer coordinates. The shot hits the first wall or
  fighter whose square the line passes through the inside of. Grazing a corner or running exactly
  along an edge doesn't count, so a diagonal shot slips between two walls that only touch at a corner.
- **Speed and range.** 2 tiles a tick along the line's major axis (`max(|dx|, |dy|)`, the same metric
  as movement), with no range limit: it ends on a fighter or its second wall. The map edge counts as
  a wall.
- **Bounce.** At its first flat wall the shot reflects from the centre of the last open tile and flies
  on along the mirrored line; a wall corner or a second wall ends it. After a bounce, the observed
  projectile's `origin` and `target` describe the new line and `bounces_left` is 0.
- **Observations.** Each projectile reports `origin`, `target` and `exact_pos` (thousandths of a
  tile), so you can compute its whole path. You rarely need to: `danger` lists every tile it will
  cross and when.
- **Line of sight** uses the same line test: if you can see a tile, a shot at it won't hit a wall on
  the way. Sight is symmetric.

Up close the only defence is not standing still when your opponent can fire. Both starters dodge
with `hitIn`, which asks whether a tile is hit within the next few ticks, and `dodge`, which steps to
a tile that isn't, or dashes when the move is on cooldown.

From https://victrisarena.com/docs/bot-guide#standard-shots

## Danger tiles

`observation.danger` is a list of `{tile, tick, attack, owner, damage, source}`, in tick order:

| field    | meaning                                                                                                                               |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `tick`   | when the hit resolves; equal to the observation's `tick` means during the tick you're replying to, after movement                     |
| `source` | `projectile` or `area`: things already in the world, so the list is certain. An attack sent this tick appears in the next observation |
| `damage` | base damage, before the attacker's power buff                                                                                         |

A projectile lists every tile along its path, up to the first opponent it hits. A frostburst area
lists each tile of its square on its explosion tick; the slow while its fuse burns is in `areas[]`
(`tiles`, `slow`, `ticks_left`). `danger` only covers what you can see, and paths ignore fighters,
so it never reveals anyone in the fog. The timing of every attack and its cheapest counter are on
one page: [frame data](https://victrisarena.com/docs/frame-data) (`/docs/frame-data`).

From https://victrisarena.com/docs/bot-guide#danger-tiles

## Dashing and corners

A dash moves exactly 3 tiles and makes you invulnerable for that tick, so it's the main way out of a
bad spot. Corners limit your escape routes. Retreat toward open space and the zone centre;
when nearly cornered, consider a dash to a safe landing farther from the enemy. A dash stops at
walls and fighters, so take the landing tile from `observation.dashes` rather than predicting it,
and make sure nothing hits it the tick after.

From https://victrisarena.com/docs/bot-guide#dashing-and-corners

## Pickups

Pads on the map hold pickups. To take one, step onto its tile or dash onto or through it: a dash
takes every stocked pad it passes, not only where it lands. It costs no action and no tick. A
fighter pushed by a repulsor takes the pads it is pushed across too, so shoving an enemy over a pad
hands it the pickup. A pad that restocks under you is yours as the tick begins, even if you move off
it. Pads are stocked on tick 20 and restock a fixed time after they are taken.
`observation.pickups` lists the pads in sight, with `ready_in: 0` when stocked, otherwise the ticks
until it restocks.

| kind     | effect                                                        | respawn (ticks)                  |
| -------- | ------------------------------------------------------------- | -------------------------------- |
| `health` | +32 hp, up to max                | 120 |
| `power`  | weapon damage ×1.5 for 50 ticks | 200  |

Read the numbers from `hello.rules.pickups`, not this table. Active buffs appear in `self.buffs`
(kind → ticks left), and the same for visible enemies: a powered-up enemy is a reason to take cover.
The pads sit on the centre column, the same distance from both spawns, so expect them to be
contested. The [starter strategy](https://victrisarena.com/download/bots/ts-starter/strategy.ts)
shows one way to decide whether a detour is worth it.

From https://victrisarena.com/docs/bot-guide#pickups
