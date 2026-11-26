// Grid geometry: directions, arcs, distance, lines. Integer math only.

export type Vec = readonly [number, number];
export type Dir = "N" | "NE" | "E" | "SE" | "S" | "SW" | "W" | "NW";

/** Clockwise from north; index arithmetic mod 8 gives neighbours and opposites. */
export const DIRS: readonly Dir[] = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];

export const DIR_VEC: Record<Dir, Vec> = {
  N: [0, -1],
  NE: [1, -1],
  E: [1, 0],
  SE: [1, 1],
  S: [0, 1],
  SW: [-1, 1],
  W: [-1, 0],
  NW: [-1, -1],
};

export function isDir(v: unknown): v is Dir {
  return typeof v === "string" && (DIRS as readonly string[]).includes(v);
}

export function dirIndex(d: Dir): number {
  return DIRS.indexOf(d);
}

export function rotate(d: Dir, steps: number): Dir {
  return DIRS[(((dirIndex(d) + steps) % 8) + 8) % 8]!;
}

export function opposite(d: Dir): Dir {
  return rotate(d, 4);
}

export function add(a: Vec, b: Vec, k = 1): [number, number] {
  return [a[0] + b[0] * k, a[1] + b[1] * k];
}

/** The repulsor's burst: all eight tiles around `origin`. */
export function repulsorRing(origin: Vec): [number, number][] {
  return DIRS.map((d) => add(origin, DIR_VEC[d]));
}

export function eq(a: Vec, b: Vec): boolean {
  return a[0] === b[0] && a[1] === b[1];
}

export function chebyshev(a: Vec, b: Vec): number {
  return Math.max(Math.abs(a[0] - b[0]), Math.abs(a[1] - b[1]));
}

export function key(p: Vec): string {
  return `${p[0]},${p[1]}`;
}

/**
 * Octant of the vector from `from` to `to`: which of the 8 directions it falls in,
 * each a 45° wedge centred on the direction. Uses integer comparisons only:
 * tan(22.5°) ≈ 0.41421356, compared as 2.41421356·|minor| vs |major| scaled by 1e8.
 * Boundaries (exactly 22.5°) never occur on an integer grid.
 */
export function octant(from: Vec, to: Vec): Dir | null {
  const dx = to[0] - from[0];
  const dy = to[1] - from[1];
  if (dx === 0 && dy === 0) return null;
  const ax = Math.abs(dx);
  const ay = Math.abs(dy);
  // |minor|/|major| < tan(22.5°)  ⇔  |minor|·241421356 < |major|·100000000
  const T_NUM = 41421356;
  const T_DEN = 100000000;
  if (ay * T_DEN < ax * T_NUM) return dx > 0 ? "E" : "W";
  if (ax * T_DEN < ay * T_NUM) return dy > 0 ? "S" : "N";
  if (dx > 0) return dy > 0 ? "SE" : "NE";
  return dy > 0 ? "SW" : "NW";
}

/** Bresenham line from a to b inclusive of both ends. */
export function bresenham(a: Vec, b: Vec): [number, number][] {
  const out: [number, number][] = [];
  let [x0, y0] = a;
  const [x1, y1] = b;
  const dx = Math.abs(x1 - x0);
  const dy = -Math.abs(y1 - y0);
  const sx = x0 < x1 ? 1 : -1;
  const sy = y0 < y1 ? 1 : -1;
  let err = dx + dy;
  for (;;) {
    out.push([x0, y0]);
    if (x0 === x1 && y0 === y1) break;
    const e2 = 2 * err;
    if (e2 >= dy) {
      err += dy;
      x0 += sx;
    }
    if (e2 <= dx) {
      err += dx;
      y0 += sy;
    }
  }
  return out;
}

// ---------------------------------------------------------------- projectile rays
//
// Projectiles fly along the true straight line from the centre of the shooter's
// tile through the centre of the target tile. Positions are exact rationals;
// distances along the ray are measured in SUB units (thousandths of a tile) along
// the ray's major axis, so "speed 2" and "range 10" use the same Chebyshev metric
// as movement. Tiles are unit squares centred on integer coordinates, and a ray
// touches a tile only if it passes through the tile's interior: grazing a corner
// or running exactly along an edge does not count.

/** Sub-tile units per tile. */
export const SUB = 1000;

export interface Ray {
  origin: readonly [number, number];
  /** target − origin; never [0, 0] */
  d: readonly [number, number];
  /** max(|dx|, |dy|) */
  major: number;
}

export function makeRay(origin: Vec, target: Vec): Ray {
  const d: [number, number] = [target[0] - origin[0], target[1] - origin[1]];
  return { origin: [origin[0], origin[1]], d, major: Math.max(Math.abs(d[0]), Math.abs(d[1])) };
}

/** a / b rounded half away from zero, b > 0. */
function roundDiv(a: number, b: number): number {
  const q = Math.trunc(a / b);
  const r = a - q * b;
  return 2 * Math.abs(r) >= b ? q + Math.sign(a) : q;
}

/** Point on the ray after travelling `s` SUB units, in SUB units (rounded; for display and observations). */
export function rayPoint(r: Ray, s: number): [number, number] {
  return [
    r.origin[0] * SUB + roundDiv(r.d[0] * s, r.major),
    r.origin[1] * SUB + roundDiv(r.d[1] * s, r.major),
  ];
}

/** Tile containing a SUB-unit point; points on a boundary belong to the higher tile. */
export function subToTile(p: Vec): [number, number] {
  return [Math.floor((p[0] + SUB / 2) / SUB), Math.floor((p[1] + SUB / 2) / SUB)];
}

/** Rational n/d with d > 0. `null` stands for an unbounded side. */
type Q = { n: number; d: number };
const qlt = (a: Q, b: Q) => a.n * b.d < b.n * a.d;
const qmax = (a: Q, b: Q) => (qlt(a, b) ? b : a);
const qmin = (a: Q, b: Q) => (qlt(a, b) ? a : b);

/**
 * Open interval of travel s (SUB units) during which the ray is strictly inside
 * the slab of tile coordinate `c` on one axis. `null` = never inside.
 */
function slab(
  o: number,
  dAxis: number,
  major: number,
  c: number,
): { lo: Q | null; hi: Q | null } | null {
  // inside ⇔ (2(c−o) − 1)·SUB·major < 2·dAxis·s < (2(c−o) + 1)·SUB·major
  const L = (2 * (c - o) - 1) * SUB * major;
  const U = (2 * (c - o) + 1) * SUB * major;
  const k = 2 * dAxis;
  if (k === 0) return L < 0 && 0 < U ? { lo: null, hi: null } : null;
  return k > 0
    ? { lo: { n: L, d: k }, hi: { n: U, d: k } }
    : { lo: { n: -U, d: -k }, hi: { n: -L, d: -k } };
}

export interface RayTile {
  tile: [number, number];
  /** travel (SUB units) at which the ray enters the tile, clamped to the segment start */
  entry: Q;
}

/** Tiles whose interior the ray passes through while travelling from `sa` to `sb`, in order of entry. */
export function rayTiles(r: Ray, sa: number, sb: number): RayTile[] {
  const a = rayPoint(r, sa);
  const b = rayPoint(r, sb);
  const t0 = subToTile([Math.min(a[0], b[0]), Math.min(a[1], b[1])]);
  const t1 = subToTile([Math.max(a[0], b[0]), Math.max(a[1], b[1])]);
  const start: Q = { n: sa, d: 1 };
  const end: Q = { n: sb, d: 1 };
  const out: RayTile[] = [];
  for (let x = t0[0] - 1; x <= t1[0] + 1; x++) {
    const sx = slab(r.origin[0], r.d[0], r.major, x);
    if (!sx) continue;
    for (let y = t0[1] - 1; y <= t1[1] + 1; y++) {
      const sy = slab(r.origin[1], r.d[1], r.major, y);
      if (!sy) continue;
      // open (lo, hi) ∩ closed [sa, sb] is non-empty ⇔ lo < sb, sa < hi, lo < hi
      const lo: Q | null = sx.lo && sy.lo ? qmax(sx.lo, sy.lo) : (sx.lo ?? sy.lo);
      const hi: Q | null = sx.hi && sy.hi ? qmin(sx.hi, sy.hi) : (sx.hi ?? sy.hi);
      if (lo && !qlt(lo, end)) continue;
      if (hi && !qlt(start, hi)) continue;
      if (lo && hi && !qlt(lo, hi)) continue;
      const entry = lo && qlt(start, lo) ? lo : start;
      out.push({ tile: [x, y], entry });
    }
  }
  return out.sort((p, q) =>
    qlt(p.entry, q.entry)
      ? -1
      : qlt(q.entry, p.entry)
        ? 1
        : p.tile[1] - q.tile[1] || p.tile[0] - q.tile[0],
  );
}
