import { hashValue } from "./util.ts";

export type AttackName = string;

export interface ProjectileAttack {
  kind: "projectile";
  damage: number;
  /** Total tiles it can fly, bounce included; absent means no limit (it ends on a wall, a fighter or its second wall). */
  range?: number;
  speed: number;
  cooldown: number;
  /** Wall reflections allowed before the projectile expires (currently at most one). */
  bounces?: number;
}

/** An instant area spell (kind `area`, used by frostburst): cast on a visible tile, it exists at once and damages every opponent in its square when the fuse runs out. */
export interface AreaAttack {
  kind: "area";
  damage: number;
  range: number;
  cooldown: number;
  /** Full ticks between the cast and the explosion. */
  fuse: number;
  radius: number;
  /** Extra move cooldown for opponents standing in the square while the fuse burns; absent means none. */
  slow?: number;
}

/** A point-blank force burst: hits all eight tiles around the fighter and shoves each opponent away. No aim. */
export interface BurstAttack {
  kind: "burst";
  /** damage to each fighter hit */
  damage: number;
  /** always 1: the burst covers the eight adjacent tiles */
  range: number;
  cooldown: number;
  /** tiles each fighter hit is pushed straight away from the attacker; a wall stops it with a slam */
  push: number;
}

export type Attack = ProjectileAttack | AreaAttack | BurstAttack;

/** Pickup kinds a map may place on its pads. Each respawns `respawn` ticks after it is taken. */
export interface PickupRules {
  /** tick on which every pad first holds its pickup */
  first_spawn: number;
  health?: { amount: number; respawn: number };
  /** weapon damage × damage_multiplier[0] / damage_multiplier[1] */
  power?: { duration: number; damage_multiplier: [number, number]; respawn: number };
}

export const PICKUP_KINDS = ["health", "power"] as const;
export type PickupKind = (typeof PICKUP_KINDS)[number];

export interface Rules {
  version: string;
  ticks_per_second: number;
  max_ticks: number;
  stats: {
    max_hp: number;
    /** ticks between steps */
    move_cooldown: number;
    sight_radius: number;
    armor: number;
  };
  attacks: Record<AttackName, Attack>;
  dash: { distance: number; cooldown: number; recovery: number };
  knockback: { wall_slam_damage: number; wall_slam_stun: number; fighter_collision_damage: number };
  zone: {
    start_tick: number;
    interval: number;
    step: number;
    min_radius: number;
    warning_ticks: number;
    damage_base: number;
    damage_step: number;
    damage_step_ticks: number;
  };
  /** absent in rules tables before 0.8, which had no pickups */
  pickups?: PickupRules;
  /** short messages a fighter says to everyone; absent in rules tables before 0.22, which had none */
  shout?: { max_length: number; cooldown: number };
  limits: {
    startup_ms: number;
    tick_ms: number;
    match_budget_ms: number;
    max_consecutive_failures: number;
    reconnect_grace_ms: number;
    max_message_bytes: number;
  };
}

function assertInt(v: unknown, path: string): void {
  if (typeof v !== "number" || !Number.isInteger(v) || v < 0) {
    throw new Error(`rules: ${path} must be a non-negative integer, got ${JSON.stringify(v)}`);
  }
}

/** Every number in the rules table must be a non-negative integer: the engine does no float math. */
function checkInts(v: unknown, path: string): void {
  if (typeof v === "number") assertInt(v, path);
  else if (Array.isArray(v)) v.forEach((x, i) => checkInts(x, `${path}[${i}]`));
  else if (v && typeof v === "object")
    for (const [k, x] of Object.entries(v)) checkInts(x, path ? `${path}.${k}` : k);
}

export function loadRules(raw: unknown): Rules {
  if (!raw || typeof raw !== "object") throw new Error("rules: expected an object");
  const r = raw as Rules;
  if (typeof r.version !== "string") throw new Error("rules: version missing");
  checkInts(r, "");
  for (const [name, a] of Object.entries(r.attacks ?? {})) {
    if (a.kind !== "projectile" && a.kind !== "area" && a.kind !== "burst")
      throw new Error(`rules: attacks.${name}.kind invalid`);
    for (const key of ["damage", "cooldown"] as const) assertInt(a[key], `attacks.${name}.${key}`);
    if (a.kind !== "projectile" || a.range !== undefined)
      assertInt(a.range, `attacks.${name}.range`);
    if (a.kind === "area") {
      assertInt(a.fuse, `attacks.${name}.fuse`);
      assertInt(a.radius, `attacks.${name}.radius`);
      if (a.fuse < 3) throw new Error(`rules: attacks.${name}.fuse must be >= 3`);
      if (a.slow !== undefined) {
        assertInt(a.slow, `attacks.${name}.slow`);
        if (a.slow < 1) throw new Error(`rules: attacks.${name}.slow must be >= 1`);
      }
    } else if (a.kind === "burst") {
      assertInt(a.push, `attacks.${name}.push`);
      if (a.range !== 1 || a.push < 1)
        throw new Error(`rules: attacks.${name} repulsor requires range 1 and push >= 1`);
    } else {
      assertInt(a.speed, `attacks.${name}.speed`);
      if (a.bounces !== undefined && a.bounces !== 1)
        throw new Error(`rules: attacks.${name}.bounces must be 1`);
    }
    if (a.kind === "projectile" && a.speed < 1)
      throw new Error(`rules: attacks.${name}.speed must be >= 1`);
  }
  if (r.pickups) {
    assertInt(r.pickups.first_spawn, "pickups.first_spawn");
    for (const [kind, p] of Object.entries(r.pickups)) {
      if (kind === "first_spawn") continue;
      if (!(PICKUP_KINDS as readonly string[]).includes(kind))
        throw new Error(`rules: pickups.${kind} is not a known pickup kind`);
      const x = p as { respawn: number; duration?: number; damage_multiplier?: [number, number] };
      if (x.respawn < 1) throw new Error(`rules: pickups.${kind}.respawn must be >= 1`);
      if (x.duration !== undefined && x.duration < 1)
        throw new Error(`rules: pickups.${kind}.duration must be >= 1`);
      if (kind === "power" && (x.damage_multiplier?.length !== 2 || x.damage_multiplier[1] < 1))
        throw new Error("rules: pickups.power.damage_multiplier invalid");
    }
  }
  if (r.shout) {
    assertInt(r.shout.max_length, "shout.max_length");
    assertInt(r.shout.cooldown, "shout.cooldown");
    if (r.shout.max_length < 1) throw new Error("rules: shout.max_length must be >= 1");
  }
  return r;
}

export function rulesHash(rules: Rules): string {
  return hashValue(rules);
}
