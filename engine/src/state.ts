import type { GameMap } from "./map.ts";
import type { RngState } from "./rng.ts";
import type { Rules } from "./rules.ts";

export type FighterStateName = "idle" | "recovering" | "dashing" | "stunned" | "dead";

export interface Fighter {
  id: number;
  /** Fighters on the same team are immune to each other's weapons. */
  team: number;
  pos: [number, number];
  hp: number;
  state: FighterStateName;
  /** last tick (inclusive) the current timed state occupies; unused for idle */
  state_end: number;
  cooldowns: Record<string, number>;
  /** consecutive ticks ended outside the zone */
  ticks_outside: number;
  invulnerable: boolean;
  alive: boolean;
  damage_dealt: number;
  /** active buffs from pickups: kind → last tick (inclusive) it applies */
  buffs: Record<string, number>;
}

export interface PickupPad {
  id: number;
  pos: [number, number];
  kind: string;
  /** whether the pickup is on the pad now */
  available: boolean;
  /** while taken: the tick on whose observation it reappears */
  respawn_tick: number;
}

export interface Projectile {
  id: number;
  owner: number;
  attack: string;
  /** shooter's tile when it fired; the ray starts at its centre */
  origin: [number, number];
  /** aimed tile; the ray passes through its centre and continues to max range */
  target: [number, number];
  /** distance travelled so far, in SUB units along the ray's major axis */
  traveled: number;
  /** max distance, in SUB units (range × SUB, or UNLIMITED_TRAVEL for a shot with no range) */
  max_travel: number;
  /** tile the projectile is in now (for display and observations) */
  pos: [number, number];
  /** exact position now, in SUB units (thousandths of a tile) */
  exact_pos: [number, number];
  /** tiles per tick along the major axis */
  speed: number;
  damage: number;
  bounces_left: number;
}

export interface Area {
  id: number;
  owner: number;
  attack: string;
  pos: [number, number];
  origin: [number, number];
  launched_tick: number;
  explodes_tick: number;
  radius: number;
  damage: number;
  /** move cooldown penalty for opponents standing in the square until it explodes; 0 for none */
  slow: number;
}

export interface Zone {
  center: [number, number];
  radius: number;
}

export type GameEvent =
  | { kind: "rejected"; fighter: number; part: string; reason: string; detail?: string }
  /** `ricochet` marks a shot that hit after bouncing off a wall */
  | {
      kind: "hit";
      attacker: number;
      target: number;
      attack: string;
      damage: number;
      ricochet?: true;
    }
  | { kind: "attack"; fighter: number; attack: string; target: [number, number] }
  | { kind: "dash"; fighter: number; from: [number, number]; to: [number, number] }
  | {
      kind: "area_spawn";
      area: number;
      owner: number;
      attack: string;
      pos: [number, number];
      explodes_tick: number;
      radius: number;
    }
  | {
      kind: "area_explode";
      area: number;
      owner: number;
      attack: string;
      pos: [number, number];
      tiles: [number, number][];
    }
  | {
      kind: "projectile_spawn";
      attack: string;
      projectile: number;
      owner: number;
      pos: [number, number];
      target: [number, number];
    }
  | {
      kind: "projectile_end";
      projectile: number;
      pos: [number, number];
      reason: "wall" | "range" | "hit";
    }
  | {
      kind: "projectile_bounce";
      projectile: number;
      owner: number;
      pos: [number, number];
      wall: [number, number];
      target: [number, number];
    }
  | {
      kind: "repulse";
      owner: number;
      attack: string;
      pos: [number, number];
      tiles: [number, number][];
    }
  | {
      kind: "knockback";
      attacker: number;
      target: number;
      from: [number, number];
      to: [number, number];
    }
  | { kind: "wall_slam"; attacker: number; target: number; damage: number }
  | { kind: "collision"; attacker: number; fighters: [number, number]; damage: number }
  | { kind: "stunned"; fighter: number; ticks: number }
  | { kind: "zone_damage"; fighter: number; damage: number }
  | { kind: "death"; fighter: number }
  | { kind: "zone_shrink"; radius: number }
  | { kind: "pickup"; fighter: number; pad: number; pickup: string; pos: [number, number] }
  | { kind: "pickup_spawn"; pad: number; pickup: string; pos: [number, number] }
  | { kind: "buff_end"; fighter: number; buff: string }
  /** heard by everyone, wherever they are */
  | { kind: "shout"; fighter: number; text: string };

export interface MatchResult {
  /** fighter id of the winner, or null for a draw */
  winner: number | null;
  reason:
    | "last_standing"
    | "all_dead"
    | "timeout_hp"
    | "timeout_damage"
    | "timeout_draw"
    | "forfeit"
    | "disqualified";
  final_tick: number;
}

export interface MatchState {
  rules: Rules;
  map: GameMap;
  seed: number;
  rng: RngState;
  /** the tick about to be resolved; observations are sent for this tick */
  tick: number;
  fighters: Fighter[];
  projectiles: Projectile[];
  areas: Area[];
  pickups: PickupPad[];
  next_projectile_id: number;
  zone: Zone;
  /** events produced by the most recently resolved tick */
  events: GameEvent[];
  result: MatchResult | null;
}

/** The attack half of a turn: what to fire and at which tile (the repulsor has no aim and ignores it). */
export interface AttackInput {
  name?: string;
  target?: [number, number];
}

/**
 * What a bot asks for in one tick: a movement phase (`move` a direction, `dash` a direction, or
 * neither), then an optional attack that fires from where the fighter ends up, and an optional
 * shout. Everything is optional, an empty turn is idle, and the engine validates every part.
 */
export interface TurnInput {
  move?: string;
  dash?: string;
  attack?: AttackInput;
  /** said to everyone; the server cleans it (profanity masked) before the engine sees it */
  shout?: string;
}
