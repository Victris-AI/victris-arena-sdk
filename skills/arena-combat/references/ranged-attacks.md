# Ranged attacks

Three weapons, each with its own cooldown and no ammo. All three are the `attack` part of a turn,
and they fire the tick they are sent:

```json
{"tick": 40, "attack": {"name": "ranged", "target": [9, 4]}}
{"tick": 41, "attack": {"name": "frostburst", "target": [12, 6]}}
{"tick": 42, "attack": {"name": "repulsor"}}
```

| attack       | damage                              | cooldown                              | what it does                                                                                                                                                                                                                  |
| ------------ | ----------------------------------- | ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ranged`     | 12     | 6     | A shot at any angle, 2 tiles a tick, with no range limit. Bounces once off a flat wall; a corner or a second wall stops it.                                                                      |
| `frostburst` | 14 | 14 | An instant spell on a visible tile within 7. A 3×3 area slows opponents inside it, then explodes 6 ticks after the cast.                                     |
| `repulsor`   | 5   | 12   | No aim: hits all eight tiles around you and shoves each opponent 3 tiles. Into a wall: a slam for 10 more and a 3-tick stun. |

These are the numbers this ladder plays. Read them from `hello.rules.attacks` rather than hard-coding them.

> [!NOTE]
> Brawler and Kiter now make better use of shots and frostburst while preserving their close-pressure
> and range-control styles. Champion varies a few early movements while retaining its network
> and conditional attack sampling. Weapon numbers, timings and counters on this page are unchanged.

## Firing

- **Fire on send.** Every attack fires in the tick it is sent, after movement: projectiles launch and
  fly their first segment, frostburst creates its area and starts its fuse, and repulsors shove.
  Nothing is telegraphed, so a target that stepped off the line that tick escapes and one that stood
  still is hit.
- **Move and attack together.** An attack can follow a move or a dash in the same turn and fires from
  where you end up: `{"tick": 40, "move": "E", "attack": {"name": "ranged", "target": [9, 4]}}`.
- **Chain weapons.** Sending one attack puts only that attack on cooldown, and attacks have no
  recovery, so a different weapon can fire on the very next tick. A turn carries at most one attack.
- **Targets** can be any tile except the one you end your movement on. Frostburst targets must also be
  visible, non-wall tiles within range, judged from where you end up; otherwise the attack is rejected
  as `not_visible`, `blocked` or `out_of_range`. Names must be entries in `hello.rules.attacks`;
  others are `unknown_attack`.
- **No friendly fire.** Weapons never damage, slow or shove their shooter or teammates.
- **Defend by moving,** dashing (invulnerable for its tick: shots pass through, blasts and repulsors
  miss) or using cover.

## Standard shot: `ranged`

![A shot banked off a wall, and when shots land by distance](https://victrisarena.com/docs/images/shots.svg)

The cheapest, fastest-cycling weapon. A shot flies the straight line from your tile's centre through
the target tile's centre, and on past it. Aim at distant tiles (up to ±1000) for precise angles.

- **Speed 2, no range limit.** It ends on the first fighter it hits, at a corner, or at its second wall.
- **One bounce.** On its first flat-wall contact (the map edge counts), it reflects from the centre
  of the last open tile and continues along the mirrored line on the next tick. A hit after the
  bounce is a ricochet: the `hit` event carries `"ricochet": true`. The bounce shows in a
  `projectile_bounce` event, in later projectile observations and in `danger`.
- **The aim locks after movement,** before repulsors resolve. If a repulsor pushes you on the tick you
  fire, the shot launches from where you land but keeps its direction, even if you land on the aim
  tile. It still fires and starts its cooldown. The projectile's `target` shifts with its `origin` to
  express the same direction; the `attack` event keeps the tile you asked for.

> [!TIP]
> A shot `d` tiles away lands `ceil(d / 2) - 1` ticks after it is sent. Against an enemy that can't
> leave its tile for longer than that (stunned, recovering from a dash, or just stepped with its dash
> on cooldown), it can't miss.

## Frostburst: deny an area

![A frostburst's fuse, and the way out of it](https://victrisarena.com/docs/images/frostburst.svg)

An instant spell with no flight time. Cast on tick T, its area exists from that tick and explodes on
T+6.

- **The fuse.** The observations for T+1 to T+6 show `areas[].ticks_left` of 6, 5, 4, 3, 2 and 1.
  A value of 1 means it explodes this tick, after movement.
- **The blast.** Every tile in `areas[].tiles`, corners included, takes the full 14 damage. Walls and
  map edges are left out, and walls shield tiles behind them with the same line-of-sight test as
  shots. A dash avoids the blast. The area persists even if its caster dies.
- **The slow.** From the tick after the cast until the blast, an opponent who starts a step inside
  the area pays `areas[].slow` (2) extra move cooldown: a step costs 4 ticks instead of 2. Leaving the
  square still costs the extra, since the tile you start on decides. Nothing lingers after the blast,
  dashes and attacks are unaffected, and where areas overlap the largest slow counts.

**Why a 6-tick fuse:** it denies an area, so there must be an easy way out but no way through. A
fighter in the centre needs two slowed steps, the first on T+1 and the second on T+5, and is out one
tick before the blast: it can afford one wasted tick, but not two. Crossing the square takes about 10
ticks, so nobody gets through it before it goes off.

> [!TIP]
> Cast it on an enemy whose `dash_cooldown` is running: without a dash, its only way out is walking.

## Repulsor: punish anyone adjacent

![The repulsor's ring, a shove in the open and a slam into a wall](https://victrisarena.com/docs/images/repulsor.svg)

A point-blank burst with no aim. It covers the eight tiles around you (walls left out), measured from
where you end your movement. Send it without a `target`; a `target`, if given, is ignored.

Every opponent in the ring takes 5 damage and is shoved 3 tiles straight away from you (the direction
from you to its tile), one tile at a time:

| the shove meets                                          | result                                                                                                                                                    |
| -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| nothing                                                  | pushed the full 3 tiles                                                                                                     |
| a wall, or a wall corner a diagonal shove can't cut past | a **slam**: 10 more damage and `stunned` for 3 ticks (no moving, dashing or attacking) |
| another fighter                                          | a **collision**: 5 damage to both                                                                              |

- **Timing.** Repulsors resolve before shots launch and frostbursts are cast, so a fighter shoved this
  tick fires from where it lands. Movement resolves first, so stepping out of the ring on the tick it
  is sent escapes it. A dashing fighter is neither hit nor shoved.
- **The zone** still hurts at the end of the tick, so a shove out of the zone costs the target too.
- **Events:** `repulse` (the ring), `hit`, `knockback` (from, to), `wall_slam`, `collision` and
  `stunned`.

> [!TIP]
> Shove when the 3-tile push ends in a wall (trace the push along its direction), or into your
> own frostburst about to explode. A slam stuns for 3 ticks: slam, then shoot.

## What you observe

- **`danger`** lists every tile each visible opponent projectile and area will hit, and on which tick,
  including bounced shots. See the spec's Danger tiles, and [frame data](https://victrisarena.com/docs/frame-data) for timing and
  counters.
- **`projectiles[]`** include `attack`, `speed`, `origin`, `target`, `exact_pos` and `bounces_left`.
- **`areas[]`** include `attack`, `owner`, `pos`, `damage`, `radius`, `slow`, `ticks_left` and `tiles`.
  Your own projectiles and areas are visible too. `area_spawn` announces the explosion tick and
  `area_explode` reports its footprint.
- **Fighters** expose `slow_ticks_left`: the ticks until the frostburst area they stand in explodes,
  or 0.

## In the viewer

New recordings select their producing release's simulator, including the gameplay helpers used
for targeting and effects. See [replay loading](https://victrisarena.com/docs/simulator#replays) if an archived simulator
cannot be loaded. Older files still require a compatible engine.

Every weapon effect is drawn in its owner's colour, and shape tells the weapons apart:

- **Shots** leave a single trail; bounces and hits throw sparks.
- **Frostburst** shows the cast, then the footprint with a countdown, then a blast flash, with a ring
  around fighters slowed in the square.
- **Repulsor** flashes the ring around the fighter with an expanding wave; a shove leaves skid marks.

Each fighter's cooldowns (move, dash and the three weapons) are round icons in the arena's bottom
corners and the side panel.

## Achievements
