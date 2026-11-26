import { DIR_VEC, add, type Dir, type Vec } from "./geometry.ts";

export type Tile = "." | "#";
export const TILE_CODES: readonly Tile[] = [".", "#"];

export interface GameMap {
  name: string;
  width: number;
  height: number;
  /** one string per row: `.` floor, `#` wall */
  tiles: string[];
  spawns: [number, number][];
  /** pickup pads; each holds one pickup of its kind, which respawns after it is taken */
  pickups: { pos: [number, number]; kind: string }[];
}

export function loadMap(raw: unknown): GameMap {
  const m = raw as { name?: unknown; tiles?: unknown; spawns?: unknown; pickups?: unknown };
  if (typeof m?.name !== "string") throw new Error("map: name missing");
  if (!Array.isArray(m.tiles) || m.tiles.length === 0) throw new Error("map: tiles missing");
  const tiles = m.tiles as string[];
  const height = tiles.length;
  const width = tiles[0]!.length;
  if (width < 11 || width > 41 || height < 11 || height > 41) {
    throw new Error(`map: size ${width}x${height} outside 11..41`);
  }
  for (const [y, row] of tiles.entries()) {
    if (typeof row !== "string" || row.length !== width)
      throw new Error(`map: row ${y} has wrong length`);
    for (const c of row)
      if (!(TILE_CODES as readonly string[]).includes(c))
        throw new Error(`map: bad tile '${c}' in row ${y}`);
  }
  if (!Array.isArray(m.spawns) || m.spawns.length < 2)
    throw new Error("map: needs at least 2 spawns");
  const spawns = (m.spawns as [number, number][]).map((s) => [s[0], s[1]] as [number, number]);
  if (m.pickups !== undefined && !Array.isArray(m.pickups))
    throw new Error("map: pickups must be a list");
  const pickups = ((m.pickups ?? []) as { pos: [number, number]; kind: string }[]).map((p) => ({
    pos: [p.pos[0], p.pos[1]] as [number, number],
    kind: p.kind,
  }));
  const map: GameMap = { name: m.name, width, height, tiles, spawns, pickups };
  for (const s of spawns) {
    if (!inBounds(map, s) || tileAt(map, s) !== ".")
      throw new Error(`map: spawn ${s} must be an in-bounds floor tile`);
  }
  const seen = new Set<string>(spawns.map((s) => `${s[0]},${s[1]}`));
  for (const p of pickups) {
    if (typeof p.kind !== "string") throw new Error("map: pickup kind missing");
    if (!inBounds(map, p.pos) || tileAt(map, p.pos) !== ".")
      throw new Error(`map: pickup ${p.pos} must be an in-bounds floor tile`);
    const k = `${p.pos[0]},${p.pos[1]}`;
    if (seen.has(k)) throw new Error(`map: pickup ${p.pos} overlaps a spawn or another pickup`);
    seen.add(k);
  }
  return map;
}

export function inBounds(map: GameMap, p: Vec): boolean {
  return p[0] >= 0 && p[1] >= 0 && p[0] < map.width && p[1] < map.height;
}

/** Out-of-bounds reads as wall, which makes edges behave like walls everywhere. */
export function tileAt(map: GameMap, p: Vec): Tile {
  if (!inBounds(map, p)) return "#";
  return map.tiles[p[1]]![p[0]] as Tile;
}

export function isWall(map: GameMap, p: Vec): boolean {
  return tileAt(map, p) === "#";
}

/** A diagonal step is blocked if either orthogonal tile it cuts past is a wall. */
export function cutsCorner(map: GameMap, from: Vec, dir: Dir): boolean {
  const [dx, dy] = DIR_VEC[dir];
  if (dx === 0 || dy === 0) return false;
  return isWall(map, [from[0] + dx, from[1]]) || isWall(map, [from[0], from[1] + dy]);
}

/** Can a fighter at `from` not step in `dir`: into a wall or off the map, or diagonally past a wall corner? */
export function stepBlocked(map: GameMap, from: Vec, dir: Dir): boolean {
  return isWall(map, add(from, DIR_VEC[dir])) || cutsCorner(map, from, dir);
}

/** Point symmetry (180° rotation) or mirror symmetry on either axis, spawns and pickups included. */
export function isSymmetric(map: GameMap): boolean {
  const { width: w, height: h } = map;
  const check = (f: (x: number, y: number) => [number, number]) => {
    for (let y = 0; y < h; y++)
      for (let x = 0; x < w; x++) if (tileAt(map, [x, y]) !== tileAt(map, f(x, y))) return false;
    const [a, b] = map.spawns;
    const fa = f(a![0], a![1]);
    if (fa[0] !== b![0] || fa[1] !== b![1]) return false;
    return map.pickups.every((p) => {
      const q = f(p.pos[0], p.pos[1]);
      return map.pickups.some((o) => o.kind === p.kind && o.pos[0] === q[0] && o.pos[1] === q[1]);
    });
  };
  return (
    check((x, y) => [w - 1 - x, h - 1 - y]) ||
    check((x, y) => [w - 1 - x, y]) ||
    check((x, y) => [x, h - 1 - y])
  );
}

export function mapCenter(map: GameMap): [number, number] {
  return [(map.width - 1) >> 1, (map.height - 1) >> 1];
}

/** The map's pickup pads with the ids the match uses (1-based, in map order), as sent in hello. */
export function pickupPads(map: GameMap): { id: number; pos: [number, number]; kind: string }[] {
  return map.pickups.map((p, i) => ({ id: i + 1, pos: [p.pos[0], p.pos[1]], kind: p.kind }));
}
