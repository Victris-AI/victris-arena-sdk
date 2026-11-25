# Frame data and counters (rules v0.22.1)

Generated from the rules table, so these numbers match `hello.rules`. Times are in ticks. Tick T is the tick you send the attack.

## Frame data

| attack | damage | cooldown | warning at 1 / 2 / 5 / 8 tiles |
| --- | --- | --- | --- |
| `ranged` | 12 | 6 | 0 / 0 / 2 / 3 |
| `frostburst` | 14 | 14 | 6 / 6 / 6 / – |
| `repulsor` | 5, push 3 | 12 | 0 / – / – / – |

- **Every attack fires the tick you send it**, after movement: projectiles launch and fly, frostburst creates its area and starts its fuse, repulsors shove. Nothing is telegraphed before it's in the world, so a target that stepped away that same tick escapes, and one that stood still doesn't.
- **No recovery**: an attacker can step, dash or fire on the very next tick, and can even move in the same tick it fires. There is no punish window after an attack; count its cooldown instead.
- **cooldown**: each attack has its own. The same attack can start again on tick T + cooldown; the others are unaffected, so a fighter can fire a different weapon on the very next tick (one attack per tick). Opponents' cooldowns are hidden, but every attack is an `attack` event naming the weapon, so you can count each one from the last time you saw it.
- **warning**: how many observations show the threat (in `danger`) before it hits a tile at that distance. 0 means it lands the tick it's sent: no warning, only the knowledge that the shooter could fire. "–" means out of range.

## Counters

Every threat, with its exact tiles and tick, is in `observation.danger`. The cheapest answer is usually to be somewhere else on that tick.

| attack | what it threatens | cheapest counter |
| --- | --- | --- |
| `ranged` | A line at any angle, 2 tiles a tick, that bounces once off a flat wall (a corner stops it), so it reaches angles a straight shot can't. The cheapest poke, on the shortest cooldown. Within 2 tiles it lands the tick it is sent. | At range, step off its path while it flies, reading the path after the bounce from `danger`. Up close there's no warning: don't stand still next to a shooter whose shot is off cooldown. Being out of the shooter's line of sight is not enough. |
| `frostburst` | A 3×3 area (walls shield tiles behind them) on a fixed tick, cast instantly on a tile you can see. Until it goes off, moving from inside it takes 2 ticks longer per step. | Walk out of `areas[].tiles` before `ticks_left` reaches 1, starting early: each step inside costs extra. Don't plan to cross it. Dash on the last tick if you're boxed in. |
| `repulsor` | All eight tiles around the attacker (no aim), landing the tick it is sent: 5 damage and a shove 3 tiles straight away. A wall stops the shove with a slam (10 more damage, stunned 3 ticks); the zone edge keeps hurting. | Don't stand next to an opponent whose repulsor is up, least of all with a wall or the zone edge behind you: a slam stuns you for 3 ticks, long enough for a guaranteed follow-up shot. Its cooldown is long, but spending it leaves their other weapons ready. |

## Your defensive tools

| tool | cooldown | notes |
| --- | --- | --- |
| step | 2 ticks, in any of 8 directions | Your move must be off cooldown on the impact tick. Movement resolves before attacks, so stepping out on that tick still dodges. |
| dash | 12 ticks; 1 tick of recovery | Moves 3 tiles and makes you invulnerable for that tick. Your landing tile must be safe on the following ticks. It's your only escape once your move is on cooldown, so don't spend it on travel. An opponent's is in `enemies[].dash_cooldown`: while it's above 0, they can't dash out of a well-placed frostburst. |
| cover | free | Walls stop shots and shield blast tiles. If a wall blocks the line of sight between you and a shooter, a shot can still bank off another wall to reach you, and a frostburst can be cast on a tile beside you. |

## Reading `observation.danger`

Each entry is one tile an opponent attack will hit on one tick: `{"tile": [x, y], "tick": 213, "attack": "ranged", "owner": 2, "damage": 12, "source": "projectile"}`.

- An entry whose `tick` equals the observation's `tick` lands during the tick you are replying to, after movement. Don't end this tick's move on that tile.
- Everything listed is already in the world (`source` is `projectile` or `area`), so it's certain. An attack sent this tick isn't listed until the next observation.
- `damage` is base damage, before the attacker's power buff.
- Only what you can see is listed. A shot fired from the fog appears once the projectile enters your sight.
