// Danger tiles: where, and on which tick, each visible opponent attack will land.
// Attacks fire the tick they are sent, so only what is already in the world can be
// predicted: projectiles in flight and areas on their fuse. Built from what the viewer
// can see plus the static map, and projectiles are flown with the engine's own flight
// code. Paths ignore fighters, so they never reveal someone hidden in the fog.

import { advanceProjectile } from "./flight.ts";
import { weaponCanAffect } from "./match.ts";
import { blastTiles } from "./sight.ts";
import type { Area, Fighter, MatchState, Projectile } from "./state.ts";
import { clone } from "./util.ts";

export interface Danger {
  tile: [number, number];
  /** tick the hit resolves on; the observation's own tick means during the tick you reply to */
  tick: number;
  attack: string;
  owner: number;
  /** base damage, before the attacker's power buff */
  damage: number;
  source: "projectile" | "area";
}

type Base = Pick<Danger, "attack" | "owner" | "source">;

/** Every tile the given visible projectiles and areas will hit, in tick order. */
export function dangerTiles(
  state: MatchState,
  viewer: Fighter,
  visible: { projectiles: Projectile[]; areas: Area[] },
): Danger[] {
  const out: Danger[] = [];
  for (const p of visible.projectiles) {
    if (!weaponCanAffect(state, p.owner, viewer)) continue;
    fly(
      state,
      clone(p),
      state.tick,
      { attack: p.attack, owner: p.owner, source: "projectile" },
      out,
    );
  }
  for (const b of visible.areas) {
    if (!weaponCanAffect(state, b.owner, viewer)) continue;
    addArea(
      out,
      { attack: b.attack, owner: b.owner, source: "area" },
      blastTiles(state, b.pos, b.radius),
      b.explodes_tick,
      b.damage,
    );
  }
  return out.sort((a, b) => a.tick - b.tick);
}

function entry(tile: [number, number], tick: number, b: Base, damage: number): Danger {
  return { tile, tick, attack: b.attack, owner: b.owner, damage, source: b.source };
}

function addArea(
  out: Danger[],
  base: Base,
  tiles: [number, number][],
  tick: number,
  damage: number,
): void {
  for (const tile of tiles) out.push(entry(tile, tick, base, damage));
}

/** Flies `p` (mutated) from `tick` until it stops, recording each tile it sweeps. */
function fly(state: MatchState, p: Projectile, tick: number, base: Base, out: Danger[]): void {
  for (let t = tick; ; t++) {
    const flight = advanceProjectile(state.map, p, (tile) => {
      out.push(entry(tile, t, base, p.damage));
      return false;
    });
    if (flight.end !== null && flight.end !== "bounce") return;
  }
}
