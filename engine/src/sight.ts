// Line of sight and the footprints that depend on it: blasts.

import { SUB, chebyshev, eq, makeRay, rayTiles } from "./geometry.ts";
import { inBounds, isWall, type GameMap } from "./map.ts";
import type { Fighter, MatchState } from "./state.ts";

/**
 * Line of sight uses the same straight line as projectiles: the segment between the
 * two tile centres is blocked by any wall whose interior it crosses. Grazing a wall's
 * corner does not block. The test is symmetric: A sees B exactly when B sees A.
 */
export function hasLineOfSight(
  state: MatchState,
  a: readonly [number, number],
  b: readonly [number, number],
): boolean {
  if (eq(a, b)) return true;
  const map = state.map;
  if (!inBounds(map, a) || !inBounds(map, b)) return traceSight(map, a, b);
  // Walls never change, so sight between two tiles is a property of the map. Every observation
  // and blast asks for it, and tracing the ray is most of their cost: remember each answer, per
  // map, in a byte per ordered pair of tiles (0 unknown, 1 blocked, 2 clear).
  const n = map.width * map.height;
  let seen = sightCache.get(map);
  if (!seen) sightCache.set(map, (seen = new Uint8Array(n * n)));
  const i = (a[1] * map.width + a[0]) * n + b[1] * map.width + b[0];
  if (seen[i] === 0) seen[i] = traceSight(map, a, b) ? 2 : 1;
  return seen[i] === 2;
}

const sightCache = new WeakMap<GameMap, Uint8Array>();

function traceSight(
  map: GameMap,
  a: readonly [number, number],
  b: readonly [number, number],
): boolean {
  const ray = makeRay(a, b);
  for (const { tile } of rayTiles(ray, 0, ray.major * SUB)) {
    if (eq(tile, a) || eq(tile, b)) continue;
    if (isWall(map, tile)) return false;
  }
  return true;
}

export function canSee(
  state: MatchState,
  viewer: Fighter,
  pos: readonly [number, number],
): boolean {
  return (
    chebyshev(viewer.pos, pos) <= state.rules.stats.sight_radius &&
    hasLineOfSight(state, viewer.pos, pos)
  );
}

/** Exact blast footprint: square radius, with solid walls shielding tiles behind them. */
export function blastTiles(
  state: MatchState,
  pos: readonly [number, number],
  radius: number,
): [number, number][] {
  const tiles: [number, number][] = [];
  for (let y = pos[1] - radius; y <= pos[1] + radius; y++)
    for (let x = pos[0] - radius; x <= pos[0] + radius; x++) {
      const tile: [number, number] = [x, y];
      if (!isWall(state.map, tile) && hasLineOfSight(state, pos, tile)) tiles.push(tile);
    }
  return tiles;
}
