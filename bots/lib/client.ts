// Public policy types, seeded match context and reply framing. No combat strategy lives here.

export type Dir = "N" | "NE" | "E" | "SE" | "S" | "SW" | "W" | "NW";
export type Pos = [number, number];
export const DIRS: Dir[] = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
export const VEC: Record<Dir, Pos> = {
  N: [0, -1],
  NE: [1, -1],
  E: [1, 0],
  SE: [1, 1],
  S: [0, 1],
  SW: [-1, 1],
  W: [-1, 0],
  NW: [-1, -1],
};

/** The parts of `hello.rules` these bots read. Every field: /docs/rules. */
export interface Rules {
  stats: { max_hp: number; move_cooldown: number };
  attacks: {
    ranged: { speed: number };
    frostburst: { range: number; slow?: number };
    repulsor: { push: number };
  };
  knockback: { wall_slam_stun: number };
  pickups?: { health?: { amount: number } };
}

/** The parts of `hello` these bots read. */
export interface Hello {
  match_id: string;
  bot_id: number;
  seed_public: number;
  /** rows of `.` (floor) and `#` (wall) */
  map: string[];
  rules: Rules;
}

export interface Enemy {
  id: number;
  pos: Pos;
  hp: number;
  /** ticks until it can dash again; 0 = ready */
  dash_cooldown: number;
  state: string;
  state_ticks_left: number;
  slow_ticks_left: number;
}

/** The parts of an observation these bots read. Every field: /docs/schema/observation.json. */
export interface Observation {
  tick: number;
  self: {
    id: number;
    pos: Pos;
    hp: number;
    max_hp: number;
    state: string;
    cooldowns: Record<string, number>;
  };
  /** visible opponents only */
  enemies: Enemy[];
  /** steps the engine would accept now, with the tile each reaches */
  moves: { dir: Dir; tile: Pos }[];
  /** dashes the engine would accept now, with the landing tile */
  dashes: { dir: Dir; tile: Pos; distance: number }[];
  /** every tile each visible opponent shot or area will hit, and on which tick */
  danger: { tile: Pos; tick: number }[];
  pickups: { pos: Pos; kind: string; ready_in: number }[];
  areas: { owner: number; ticks_left: number; tiles: Pos[] }[];
  zone: { center: Pos; radius: number; next_radius: number | null; shrinks_in: number | null };
  events: { kind: string; [field: string]: unknown }[];
}

/** The attack half of a turn. The repulsor has no aim, so it needs no target. */
export interface Attack {
  name: string;
  target?: Pos;
}

/** What a bot does in one tick: a movement (a step or a dash, or neither), then an optional attack. */
export interface Turn {
  move?: Dir;
  dash?: Dir;
  attack?: Attack;
  /** said to everyone, at most hello.rules.shout.max_length characters */
  shout?: string;
}

export interface Ctx {
  hello: Hello;
  map: string[];
  /** what a policy notes across the ticks of one match: the enemy's last sighting and step, a temperament */
  memory: Record<string, any>;
  /** seeded per match (from hello.seed_public and this bot's id), so games vary but stay reproducible */
  rand: () => number;
}

/** mulberry32: tiny seeded PRNG returning floats in [0, 1). */
export function seededRandom(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** A bot's decisions: its version label and its turn for each observation. */
export interface Policy {
  version: string;
  decide: (obs: Observation, ctx: Ctx) => Turn;
}

/** The per-match context a policy keeps, from the match's `hello` (the parsed message, as it arrived). */
export function newCtx(message: unknown): Ctx {
  const hello = message as Hello;
  return {
    hello,
    map: hello.map,
    memory: {},
    rand: seededRandom(hello.seed_public * 7919 + hello.bot_id),
  };
}

/**
 * The frame that answers an observation (the parsed message, as it arrived). A crash in `decide`
 * is logged and the tick is idle, so one bug never costs the match.
 */
export function reply(policy: Policy, message: unknown, ctx: Ctx): string {
  const obs = message as Observation;
  let turn: Turn;
  try {
    turn = policy.decide(obs, ctx);
  } catch (e) {
    console.error(e);
    turn = {};
  }
  return JSON.stringify({ tick: obs.tick, ...turn });
}
