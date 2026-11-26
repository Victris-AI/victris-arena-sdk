// The moves and dashes a fighter could legally start this tick, computed with the same
// rules the engine resolves with. Observations carry this so bots and the human client
// don't each reimplement corner cutting and dash stopping.

import { DIRS, DIR_VEC, add, eq, type Dir } from "./geometry.ts";
import type { Fighter, MatchState } from "./state.ts";
import { stepBlocked } from "./map.ts";

export interface MoveOption {
  dir: Dir;
  tile: [number, number];
}

export interface DashOption extends MoveOption {
  /** tiles the dash covers: the full dash distance, less if a wall or fighter stops it early (never 0) */
  distance: number;
}

export interface MoveOptions {
  moves: MoveOption[];
  dashes: DashOption[];
}

/**
 * Every step and dash the fighter can start now. Empty when it can't act (recovering, stunned) and
 * for whichever of move and dash is on cooldown. A step into an occupied tile is left out, and a
 * dash stops in front of the first wall, map edge or fighter; a dash that would not move is left out
 * because it would waste the cooldown. This is what is legal now, not what is certain: simultaneous
 * moves are still resolved against each other, so two fighters stepping onto one tile both stay put.
 */
export function moveOptions(state: MatchState, f: Fighter): MoveOptions {
  const out: MoveOptions = { moves: [], dashes: [] };
  if (!f.alive || f.state !== "idle") return out;
  const occupied = (p: readonly [number, number]) =>
    state.fighters.some((o) => o.alive && o.id !== f.id && eq(o.pos, p));
  const stepsFrom = (from: [number, number], dir: Dir): [number, number] | null => {
    if (stepBlocked(state.map, from, dir)) return null;
    const to = add(from, DIR_VEC[dir]);
    return occupied(to) ? null : to;
  };
  for (const dir of DIRS) {
    if ((f.cooldowns.move ?? 0) === 0) {
      const to = stepsFrom(f.pos, dir);
      if (to) out.moves.push({ dir, tile: to });
    }
    if ((f.cooldowns.dash ?? 0) === 0) {
      let p: [number, number] = [f.pos[0], f.pos[1]];
      let distance = 0;
      for (; distance < state.rules.dash.distance; distance++) {
        const next = stepsFrom(p, dir);
        if (!next) break;
        p = next;
      }
      if (distance > 0) out.dashes.push({ dir, tile: p, distance });
    }
  }
  return out;
}
