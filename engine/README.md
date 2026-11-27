# The engine's source

This is the Victris Arena game engine, engine 0.24.0, exactly as release 0.95.0 of the
ladder runs it. The simulator in `../sim` and `../python` is built from it. It is here to read, to
port, and to diff between releases. You don't install it: to call it from your bot, use the
simulator's forward model (`forward` in JavaScript, `ForwardModel` in Python, see the
[simulator guide](https://victrisarena.com/guide/simulator#look-ahead-the-forward-model)).

Every match's `hello` names its engine as `engine_version`, and `GET https://victrisarena.com/api` reports it as
`versions.engine`. The engine can change while `rules.version` stays the same, so a bot that
copies the engine should refuse a match on another engine version. To see what changed between
two releases, compare this folder across their tags.

## Files

| file                                                       | what it does                                                                                                        |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `step.ts`                                                  | one tick, in the spec's order: validation, dashes, movement, pickups, attacks and projectiles, zone, deaths, timers |
| `validate.ts`                                              | how a turn is read: which parts are played and which are refused, and why                                           |
| `observe.ts`                                               | what each fighter is told: fog of war, `moves` and `dashes`, pickups, zone warning, `danger`, events in view        |
| `sight.ts`                                                 | line of sight and blast tiles                                                                                       |
| `flight.ts`                                                | a shot's flight for one tick: walls, the one bounce, range                                                          |
| `geometry.ts`                                              | directions, rays and tile maths, all in integers (`SUB` = 1000 to a tile)                                           |
| `danger.ts`                                                | the tiles each visible attack will hit, and when                                                                    |
| `options.ts`                                               | the legal steps and dashes                                                                                          |
| `match.ts`                                                 | a match's start (the seed picks who takes which spawn), the zone and the end of a match                             |
| `state.ts`                                                 | the match state, the turn and every event                                                                           |
| `replay.ts`                                                | the replay format, `stateHash` and replay verification                                                              |
| `util.ts`                                                  | integer division, canonical JSON and the cyrb53 hash `stateHash` uses                                               |
| `rng.ts`, `rules.ts`, `map.ts`, `stats.ts`, `framedata.ts` | the seeded generator, rules and map loading, match statistics, frame data                                           |

The maps are in `../maps`: a hello names its map and sends its tiles, but not its spawn points.

## Porting

- Work from the [spec](https://victrisarena.com/guide/spec), including its Implementation rulings, and from this
  source. Most porting bugs are in the order things resolve within a tick, and in geometry.
- Read every number from the match's rules (`hello.rules`), never as constants.
- The engine uses integer maths only, with `Math.floor` division (`idiv`) and no randomness after
  the start.
- Prove a port exact with replays: each replay tick records `stateHash` of the whole state after
  it, cyrb53 over canonical JSON (keys sorted, no whitespace). Re-simulate the recorded turns and
  compare every tick.

Released under the MIT licence, like the rest of this repository.
