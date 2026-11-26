import { chebyshev } from "./geometry.ts";
import { mapCenter, pickupPads, type GameMap } from "./map.ts";
import { rngInt, rngSeed } from "./rng.ts";
import type { PickupKind, Rules } from "./rules.ts";
import type { Fighter, MatchResult, MatchState } from "./state.ts";
import { idiv } from "./util.ts";

/** A weapon cannot damage, drain, or apply status to its owner or a teammate. */
export function weaponCanAffect(state: MatchState, ownerId: number, target: Fighter): boolean {
  const owner = state.fighters.find((f) => f.id === ownerId);
  return target.id !== ownerId && (!owner || target.team !== owner.team);
}

export function createMatch(rules: Rules, map: GameMap, seed: number): MatchState {
  const rng = rngSeed(seed);
  // The seed decides which fighter takes which spawn.
  const swap = rngInt(rng, 2) === 1;
  const spawns = swap ? [map.spawns[1]!, map.spawns[0]!] : [map.spawns[0]!, map.spawns[1]!];
  const fighters: Fighter[] = spawns.map((pos, i) => {
    return {
      id: i + 1,
      team: i + 1,
      pos: [pos[0], pos[1]],
      hp: rules.stats.max_hp,
      state: "idle",
      state_end: 0,
      cooldowns: Object.fromEntries([
        ["move", 0],
        ["dash", 0],
        ...Object.keys(rules.attacks).map((a) => [a, 0]),
        ...(rules.shout ? [["shout", 0]] : []),
      ]),
      ticks_outside: 0,
      invulnerable: false,
      alive: true,
      damage_dealt: 0,
      buffs: {},
    };
  });
  for (const p of map.pickups) {
    if (!rules.pickups?.[p.kind as PickupKind])
      throw new Error(`match: map ${map.name} places a ${p.kind} pickup the rules don't define`);
  }
  return {
    rules,
    map,
    seed,
    rng,
    tick: 0,
    fighters,
    projectiles: [],
    areas: [],
    pickups: pickupPads(map).map((p) => ({
      ...p,
      available: false,
      respawn_tick: rules.pickups!.first_spawn,
    })),
    next_projectile_id: 1,
    zone: { center: mapCenter(map), radius: zoneRadiusAt(rules, map, 0) },
    events: [],
    result: null,
  };
}

/** Safe-zone Chebyshev radius in effect after phase 6 of `tick`. */
export function zoneRadiusAt(rules: Rules, map: GameMap, tick: number): number {
  const z = rules.zone;
  // "Whole map" is the smallest radius from the centre that covers every tile.
  const [cx, cy] = mapCenter(map);
  const full = Math.max(cx, map.width - 1 - cx, cy, map.height - 1 - cy);
  if (tick < z.start_tick) return full;
  const initial = idiv(Math.max(map.width, map.height) + 1, 2);
  const shrinks = idiv(tick - z.start_tick, z.interval);
  return Math.min(full, Math.max(z.min_radius, initial - z.step * shrinks));
}

/** The next tick after `tick` at which the radius changes, or null if it never does again. */
export function nextShrink(
  rules: Rules,
  map: GameMap,
  tick: number,
): { tick: number; radius: number } | null {
  const now = zoneRadiusAt(rules, map, tick);
  if (now <= rules.zone.min_radius) return null;
  let t: number;
  if (tick < rules.zone.start_tick) t = rules.zone.start_tick;
  else
    t =
      rules.zone.start_tick +
      (idiv(tick - rules.zone.start_tick, rules.zone.interval) + 1) * rules.zone.interval;
  // The first scheduled shrink can leave the radius unchanged (it still covers the map); skip those.
  for (let i = 0; i < 100; i++) {
    const r = zoneRadiusAt(rules, map, t);
    if (r < now) return { tick: t, radius: r };
    t += rules.zone.interval;
  }
  return null;
}

export function inZone(state: MatchState, pos: readonly [number, number]): boolean {
  return chebyshev(pos, state.zone.center) <= state.zone.radius;
}

export function aliveFighters(state: MatchState): Fighter[] {
  return state.fighters.filter((f) => f.alive);
}

/** Win check run at the end of phase 8. `resolvedTick` is the tick that just resolved. */
export function checkEnd(state: MatchState, resolvedTick: number): MatchResult | null {
  const alive = aliveFighters(state);
  if (alive.length === 1)
    return { winner: alive[0]!.id, reason: "last_standing", final_tick: resolvedTick };
  if (alive.length === 0) return { winner: null, reason: "all_dead", final_tick: resolvedTick };
  if (resolvedTick + 1 >= state.rules.max_ticks) return timeoutResult(state, alive, resolvedTick);
  return null;
}

function timeoutResult(state: MatchState, alive: Fighter[], tick: number): MatchResult {
  const max = state.rules.stats.max_hp;
  // hp as a percentage of max: compare hp/max across fighters by cross-multiplying (all share the same max).
  const byHp = [...alive].sort((a, b) => b.hp * max - a.hp * max);
  if (byHp[0]!.hp !== byHp[1]!.hp)
    return { winner: byHp[0]!.id, reason: "timeout_hp", final_tick: tick };
  const top = byHp
    .filter((f) => f.hp === byHp[0]!.hp)
    .sort((a, b) => b.damage_dealt - a.damage_dealt);
  if (top[0]!.damage_dealt !== top[1]!.damage_dealt) {
    return { winner: top[0]!.id, reason: "timeout_damage", final_tick: tick };
  }
  return { winner: null, reason: "timeout_draw", final_tick: tick };
}

/** Ends a match from outside the simulation (forfeit, disqualification). */
export function forceEnd(
  state: MatchState,
  loser: number,
  reason: "forfeit" | "disqualified",
): MatchResult {
  const winner = state.fighters.find((f) => f.id !== loser)?.id ?? null;
  state.result = { winner, reason, final_tick: state.tick };
  return state.result;
}
