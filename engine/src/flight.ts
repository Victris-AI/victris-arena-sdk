// One tick of projectile flight: walls, the one wall bounce and max range. Shared by
// the engine (phase 5) and the danger predictions in observations, so a prediction
// can't drift from what the engine does.

import { SUB, makeRay, rayPoint, rayTiles, subToTile } from "./geometry.ts";
import { tileAt, type GameMap } from "./map.ts";
import type { Projectile } from "./state.ts";

/** `max_travel` of a shot with no range limit: far longer than any map. */
export const UNLIMITED_TRAVEL = 1_000_000 * SUB;

export type Flight =
  /** `stopAt` accepted a tile: the projectile ends there */
  | { end: "hit"; tile: [number, number] }
  /** stopped by `wall`; `lastOpen` is the last open tile before it */
  | { end: "wall"; wall: [number, number]; lastOpen: [number, number] }
  /** reflected off `wall`; it continues from its new origin next tick */
  | { end: "bounce"; wall: [number, number] }
  /** reached max range this tick */
  | { end: "range" }
  /** still flying */
  | { end: null };

/**
 * Advances `p` one tick along its line, mutating it. The segment swept includes the
 * tile the projectile starts the tick in. `stopAt` is asked about each open tile in
 * order; returning true ends the flight there.
 */
export function advanceProjectile(
  map: GameMap,
  p: Projectile,
  stopAt: (tile: [number, number]) => boolean,
): Flight {
  const ray = makeRay(p.origin, p.target);
  const to = Math.min(p.traveled + p.speed * SUB, p.max_travel);
  let lastOpen: [number, number] = [p.pos[0], p.pos[1]];
  for (const { tile, entry } of rayTiles(ray, p.traveled, to)) {
    if (tileAt(map, tile) === "#") {
      const wx = tile[0] - lastOpen[0];
      const wy = tile[1] - lastOpen[1];
      if (p.bounces_left > 0 && Math.abs(wx) + Math.abs(wy) === 1) {
        const dx = p.target[0] - p.origin[0];
        const dy = p.target[1] - p.origin[1];
        const remaining = p.max_travel - Math.ceil(entry.n / entry.d);
        if (remaining > 0) {
          p.origin = [lastOpen[0], lastOpen[1]];
          p.target = [lastOpen[0] + (wx ? -dx : dx), lastOpen[1] + (wy ? -dy : dy)];
          p.pos = [lastOpen[0], lastOpen[1]];
          p.exact_pos = [lastOpen[0] * SUB, lastOpen[1] * SUB];
          p.max_travel = remaining;
          p.traveled = 0;
          p.bounces_left -= 1;
          return { end: "bounce", wall: tile };
        }
      }
      return { end: "wall", wall: tile, lastOpen };
    }
    if (stopAt(tile)) {
      p.pos = tile;
      return { end: "hit", tile };
    }
    lastOpen = tile;
  }
  p.traveled = to;
  p.exact_pos = rayPoint(ray, to);
  p.pos = subToTile(p.exact_pos);
  return to >= p.max_travel ? { end: "range" } : { end: null };
}
