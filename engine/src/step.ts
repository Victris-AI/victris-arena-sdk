// Tick resolution follows the spec. `step` mutates the
// state in place; callers that need history clone first (see cloneState).

import { DIR_VEC, add, eq, key, octant, repulsorRing, SUB, type Dir } from "./geometry.ts";
import { blastTiles } from "./sight.ts";
import { UNLIMITED_TRAVEL, advanceProjectile } from "./flight.ts";
import { isWall, stepBlocked } from "./map.ts";
import { checkEnd, inZone, weaponCanAffect, zoneRadiusAt } from "./match.ts";
import type { Fighter, GameEvent, MatchState, PickupPad, Projectile, TurnInput } from "./state.ts";
import type { PickupKind } from "./rules.ts";
import { clone, idiv } from "./util.ts";
import { targetProblem, validateTurn, type ValidTurn } from "./validate.ts";

/** What each fighter asked for this tick, by fighter id. A missing entry is an idle turn. */
export type TurnMap = Record<number, TurnInput | undefined | null>;

interface TickCtx {
  state: MatchState;
  tick: number;
  events: GameEvent[];
  turns: Map<number, ValidTurn>;
}

export function cloneState(state: MatchState): MatchState {
  // rules and map are immutable for a match, so they are shared rather than copied.
  const { rules, map, ...rest } = state;
  return { ...clone(rest), rules, map };
}

export function step(state: MatchState, input: TurnMap): GameEvent[] {
  if (state.result) throw new Error("match is over");
  const ctx: TickCtx = {
    state,
    tick: state.tick,
    events: [],
    turns: new Map(),
  };
  phase1Validate(ctx, input);
  // A pad that restocked under a fighter is theirs whether they stay, step or dash off it.
  takePadsUnderfoot(ctx);
  phase2Dashes(ctx);
  phase3Movement(ctx);
  takePadsUnderfoot(ctx); // phase 4: pickups
  phase5Attacks(ctx);
  phase6Zone(ctx);
  phase7Deaths(ctx);
  phase8Timers(ctx);
  state.events = ctx.events;
  return ctx.events;
}

function alive(state: MatchState): Fighter[] {
  return state.fighters.filter((f) => f.alive);
}

/** How much of a hit landed: `damage` is hp removed. */
interface Dealt {
  damage: number;
}

/**
 * Applies damage and credits the attacker with the hp actually removed. Weapon damage
 * (attacker set) is scaled by the attacker's power buff.
 */
function damage(ctx: TickCtx, target: Fighter, amount: number, attacker: number | null): Dealt {
  if (attacker !== null && !weaponCanAffect(ctx.state, attacker, target)) return { damage: 0 };
  if (attacker !== null) {
    const a = ctx.state.fighters.find((f) => f.id === attacker);
    const power = ctx.state.rules.pickups?.power;
    if (a && power && a.buffs.power !== undefined)
      amount = idiv(amount * power.damage_multiplier[0], power.damage_multiplier[1]);
  }
  const dealt = Math.min(target.hp, amount);
  target.hp -= dealt;
  if (attacker !== null && attacker !== target.id) {
    const a = ctx.state.fighters.find((f) => f.id === attacker);
    if (a) a.damage_dealt += dealt;
  }
  return { damage: dealt };
}

/** damage = max(1, base − armor) */
export function hitDamage(base: number, armor: number): number {
  return Math.max(1, base - armor);
}

// ---------------------------------------------------------------- phase 1

function phase1Validate(ctx: TickCtx, input: TurnMap): void {
  for (const f of alive(ctx.state)) {
    const v = validateTurn(ctx.state, f, input[f.id]);
    ctx.turns.set(f.id, v.turn);
    for (const r of v.rejected)
      ctx.events.push({ kind: "rejected", fighter: f.id, part: r.part, reason: r.reason });
    if (v.turn.shout !== undefined) {
      f.cooldowns.shout = ctx.state.rules.shout!.cooldown;
      ctx.events.push({ kind: "shout", fighter: f.id, text: v.turn.shout });
    }
  }
}

// ---------------------------------------------------------------- phases 2–3

interface Mover {
  id: number;
  from: [number, number];
  to: [number, number];
}

/**
 * Resolves simultaneous one-tile moves. Returns the ids that actually move.
 * Rules: two movers into one tile → neither; swaps → neither; moving into a tile
 * whose occupant stays (including a mover that was itself stopped) → stopped.
 * Moving into a tile its occupant is successfully leaving is allowed.
 */
export function resolveSimultaneous(movers: Mover[], occupied: Map<string, number>): Set<number> {
  const ok = new Set(movers.map((m) => m.id));
  const byId = new Map(movers.map((m) => [m.id, m]));
  const contested = new Set<number>();
  const targets = new Map<string, number[]>();
  for (const m of movers) {
    const k = key(m.to);
    targets.set(k, [...(targets.get(k) ?? []), m.id]);
  }
  for (const ids of targets.values()) if (ids.length > 1) ids.forEach((id) => contested.add(id));
  for (const m of movers) {
    const other = occupied.get(key(m.to));
    const om = other !== undefined ? byId.get(other) : undefined;
    if (om && eq(om.to, m.from)) contested.add(m.id);
  }
  contested.forEach((id) => ok.delete(id));
  let changed = true;
  while (changed) {
    changed = false;
    for (const m of movers) {
      if (!ok.has(m.id)) continue;
      const occ = occupied.get(key(m.to));
      if (occ !== undefined && occ !== m.id && !ok.has(occ)) {
        ok.delete(m.id);
        changed = true;
      }
    }
  }
  return ok;
}

function occupancy(state: MatchState): Map<string, number> {
  return new Map(alive(state).map((f) => [key(f.pos), f.id]));
}

function phase2Dashes(ctx: TickCtx): void {
  const { state } = ctx;
  const dashers = alive(state).filter((f) => ctx.turns.get(f.id)!.dash !== undefined);
  if (dashers.length === 0) return;
  const start = new Map(dashers.map((f) => [f.id, [f.pos[0], f.pos[1]] as [number, number]]));
  const active = new Set(dashers.map((f) => f.id));
  for (const f of dashers) {
    f.state = "dashing";
    f.invulnerable = true;
    f.cooldowns.dash = state.rules.dash.cooldown;
  }
  // Step every dasher one tile at a time, all at once. A dash stops at the first
  // wall, map edge or fighter; two dashes meeting stop one tile short of each other.
  // A dash takes every stocked pad it enters. Dashers advance in lockstep, so of two
  // dashes crossing one pad the one that reaches it first takes it; two can't enter one
  // tile on the same step (both stop short), so a pad never has two claimants.
  const claims: { pad: PickupPad; f: Fighter }[] = [];
  for (let i = 0; i < state.rules.dash.distance && active.size > 0; i++) {
    const movers: Mover[] = [];
    for (const f of dashers) {
      if (!active.has(f.id)) continue;
      const dir = ctx.turns.get(f.id)!.dash!;
      if (stepBlocked(state.map, f.pos, dir)) {
        active.delete(f.id);
        continue;
      }
      movers.push({ id: f.id, from: f.pos, to: add(f.pos, DIR_VEC[dir]) });
    }
    const ok = resolveSimultaneous(movers, occupancy(state));
    for (const m of movers) {
      if (!ok.has(m.id)) {
        active.delete(m.id);
        continue;
      }
      const f = state.fighters.find((x) => x.id === m.id)!;
      f.pos = m.to;
      const pad = stockedPad(state, m.to);
      if (pad) {
        // Spoken for now, so a dash reaching it on a later step finds it gone.
        pad.available = false;
        claims.push({ pad, f });
      }
    }
  }
  for (const f of dashers) {
    const from = start.get(f.id)!;
    ctx.events.push({ kind: "dash", fighter: f.id, from, to: [f.pos[0], f.pos[1]] });
  }
  // Nothing before phase 5 reads hp or buffs, so granting after the dash events is the same
  // as granting mid-dash, and keeps each dash's event ahead of what it picked up.
  for (const { pad, f } of claims) takePickup(ctx, pad, f);
}

export function moveCooldown(state: MatchState): number {
  return state.rules.stats.move_cooldown;
}

/**
 * Extra move cooldown from slow areas. An opponent's area slows every fighter standing in it
 * from the tick after it is cast until the tick it explodes; the worst one counts.
 * Dash is unaffected.
 */
export function slowPenalty(state: MatchState, f: Fighter, tick: number): number {
  let penalty = 0;
  for (const b of state.areas) {
    if (b.slow <= penalty || tick <= b.launched_tick || tick > b.explodes_tick) continue;
    if (
      !weaponCanAffect(state, b.owner, f) ||
      !blastTiles(state, b.pos, b.radius).some((t) => eq(t, f.pos))
    )
      continue;
    penalty = b.slow;
  }
  return penalty;
}

function phase3Movement(ctx: TickCtx): void {
  const { state } = ctx;
  const movers: Mover[] = [];
  for (const f of alive(state)) {
    const dir = ctx.turns.get(f.id)!.move;
    if (dir === undefined) continue;
    f.cooldowns.move = moveCooldown(state) + slowPenalty(state, f, ctx.tick);
    movers.push({ id: f.id, from: f.pos, to: add(f.pos, DIR_VEC[dir]) });
  }
  if (movers.length === 0) return;
  const ok = resolveSimultaneous(movers, occupancy(state));
  for (const m of movers) {
    if (!ok.has(m.id)) continue;
    const f = state.fighters.find((x) => x.id === m.id)!;
    f.pos = m.to;
  }
}

// ---------------------------------------------------------------- phase 4

/**
 * Anyone standing on a stocked pad takes it: once as the tick begins, for pads that restocked
 * under a fighter, and again after movement (phase 4). Only one fighter fits a tile. Pads a
 * dash enters go in phase 2, and pads a repulsor push crosses in phase 5.
 */
function takePadsUnderfoot(ctx: TickCtx): void {
  const { state } = ctx;
  if (!state.rules.pickups) return;
  for (const pad of state.pickups) {
    if (!pad.available) continue;
    const f = alive(state).find((x) => eq(x.pos, pad.pos));
    if (f) takePickup(ctx, pad, f);
  }
}

/** The stocked pad on `pos`, if pickups are on and there is one. */
function stockedPad(state: MatchState, pos: readonly [number, number]): PickupPad | undefined {
  if (!state.rules.pickups) return undefined;
  return state.pickups.find((p) => p.available && eq(p.pos, pos));
}

/**
 * `f` takes `pad`. A buff taken while repulsors resolve is granted through `later`, once every
 * repulsor has landed: they land in fighter-id order, so granting it at once would let a
 * fighter pushed onto power by a lower id boost its own repulsor that tick, and never the reverse.
 */
function takePickup(ctx: TickCtx, pad: PickupPad, f: Fighter, later?: (() => void)[]): void {
  const { state } = ctx;
  const rules = state.rules.pickups!;
  pad.available = false;
  const kind = pad.kind as PickupKind;
  pad.respawn_tick = ctx.tick + rules[kind]!.respawn;
  ctx.events.push({
    kind: "pickup",
    fighter: f.id,
    pad: pad.id,
    pickup: pad.kind,
    pos: [pad.pos[0], pad.pos[1]],
  });
  if (kind === "health") {
    f.hp = Math.min(state.rules.stats.max_hp, f.hp + rules.health!.amount);
    return;
  }
  const buff = rules[kind]!;
  // Taking a buff you already have refreshes it; it never shortens it.
  const grant = () => {
    f.buffs[kind] = Math.max(f.buffs[kind] ?? -1, ctx.tick + buff.duration - 1);
  };
  if (later) later.push(grant);
  else grant();
}

// ---------------------------------------------------------------- phase 5

/**
 * Attacks fire the tick they are sent, after movement. Repulsors resolve first, from
 * where everyone stands after movement, so a push can shove someone into or out of a
 * shot fired this tick. Then shots launch and areas are cast, and every projectile advances.
 */
function phase5Attacks(ctx: TickCtx): void {
  const { state } = ctx;
  const rules = state.rules;
  const fired: {
    f: Fighter;
    name: string;
    target: [number, number];
    direction: [number, number];
  }[] = [];
  for (const f of alive(state)) {
    const fire = ctx.turns.get(f.id)!.attack;
    if (!fire) continue;
    const atk = rules.attacks[fire.name]!;
    // The repulsor has no aim; its event reports the fighter's own tile.
    const target: [number, number] = atk.kind === "burst" ? [f.pos[0], f.pos[1]] : fire.target!;
    // Aimed attacks are judged from where the fighter ended its movement.
    const bad = atk.kind === "burst" ? null : targetProblem(state, f, atk, target);
    if (bad) {
      ctx.events.push({ kind: "rejected", fighter: f.id, part: "attack", reason: bad });
      continue;
    }
    // Each weapon has its own cooldown: firing one leaves the others ready.
    f.cooldowns[fire.name] = atk.cooldown;
    ctx.events.push({ kind: "attack", fighter: f.id, attack: fire.name, target });
    fired.push({
      f,
      name: fire.name,
      target,
      direction: [target[0] - f.pos[0], target[1] - f.pos[1]],
    });
  }
  // Every repulsor's ring is fixed before any push moves anyone.
  const repulses = fired
    .filter(({ name }) => rules.attacks[name]!.kind === "burst")
    .map((r) => ({ ...r, hits: repulsorHits(ctx, r.f, r.name) }));
  // Buffs taken mid-push, granted once every repulsor has landed.
  const later: (() => void)[] = [];
  for (const r of repulses) {
    const atk = rules.attacks[r.name]!;
    if (atk.kind !== "burst") continue;
    for (const t of r.hits) {
      projectileHit(ctx, { owner: r.f.id, attack: r.name, damage: atk.damage }, t);
      push(ctx, r.f, t, octant(r.f.pos, t.pos)!, atk.push, later);
    }
  }
  for (const grant of later) grant();
  for (const { f, name, target, direction } of fired) {
    const atk = rules.attacks[name]!;
    if (atk.kind === "area") {
      const area = {
        id: state.next_projectile_id++,
        owner: f.id,
        attack: name,
        pos: [...target] as [number, number],
        origin: [...f.pos] as [number, number],
        launched_tick: ctx.tick,
        explodes_tick: ctx.tick + atk.fuse,
        radius: atk.radius,
        damage: atk.damage,
        slow: atk.slow ?? 0,
      };
      state.areas.push(area);
      ctx.events.push({
        kind: "area_spawn",
        area: area.id,
        owner: area.owner,
        attack: area.attack,
        pos: area.pos,
        explodes_tick: area.explodes_tick,
        radius: area.radius,
      });
      continue;
    }
    if (atk.kind === "burst") continue;
    // The target sets the aim after movement; knockback shifts the launch point,
    // not the direction, even if the shooter is pushed onto the original target.
    const p: Projectile = {
      id: state.next_projectile_id++,
      owner: f.id,
      attack: name,
      origin: [f.pos[0], f.pos[1]],
      target: add(f.pos, direction),
      traveled: 0,
      max_travel: atk.range === undefined ? UNLIMITED_TRAVEL : atk.range * SUB,
      pos: [f.pos[0], f.pos[1]],
      exact_pos: [f.pos[0] * SUB, f.pos[1] * SUB],
      speed: atk.speed,
      damage: atk.damage,
      bounces_left: atk.bounces ?? 0,
    };
    state.projectiles.push(p);
    ctx.events.push({
      kind: "projectile_spawn",
      attack: p.attack,
      projectile: p.id,
      owner: f.id,
      pos: p.origin,
      target: p.target,
    });
  }

  // Each projectile sweeps a straight segment this tick. It hits the first wall or
  // fighter whose tile interior the segment passes through, including the tile it
  // starts the tick in (so a fighter stepping into an arrow's path is hit).
  const survivors: Projectile[] = [];
  for (const p of [...state.projectiles].sort((a, b) => a.id - b.id)) {
    let hit: Fighter | undefined;
    const flight = advanceProjectile(state.map, p, (tile) => {
      hit = state.fighters.find(
        (f) => f.alive && weaponCanAffect(state, p.owner, f) && !f.invulnerable && eq(f.pos, tile),
      );
      return !!hit;
    });
    switch (flight.end) {
      case "bounce":
        survivors.push(p);
        ctx.events.push({
          kind: "projectile_bounce",
          projectile: p.id,
          owner: p.owner,
          pos: p.pos,
          wall: flight.wall,
          target: p.target,
        });
        break;
      case "wall":
        ctx.events.push({
          kind: "projectile_end",
          projectile: p.id,
          pos: flight.wall,
          reason: "wall",
        });
        break;
      case "hit": {
        // A hit after a wall bounce is a ricochet.
        const atk = rules.attacks[p.attack];
        projectileHit(
          ctx,
          p,
          hit!,
          atk?.kind === "projectile" && p.bounces_left < (atk.bounces ?? 0),
        );
        ctx.events.push({
          kind: "projectile_end",
          projectile: p.id,
          pos: flight.tile,
          reason: "hit",
        });
        break;
      }
      case "range":
        ctx.events.push({ kind: "projectile_end", projectile: p.id, pos: p.pos, reason: "range" });
        break;
      case null:
        survivors.push(p);
    }
  }
  state.projectiles = survivors;
  for (const b of state.areas.filter((b) => b.explodes_tick === ctx.tick)) {
    const tiles = blastTiles(state, b.pos, b.radius);
    ctx.events.push({
      kind: "area_explode",
      area: b.id,
      owner: b.owner,
      attack: b.attack,
      pos: b.pos,
      tiles,
    });
    // Blasts affect opponents only, even if the shooter or a teammate is inside the footprint.
    for (const f of alive(state)) {
      if (!weaponCanAffect(state, b.owner, f) || f.invulnerable || !tiles.some((t) => eq(t, f.pos)))
        continue;
      const dealt = damage(ctx, f, hitDamage(b.damage, rules.stats.armor), b.owner);
      ctx.events.push({ kind: "hit", attacker: b.owner, target: f.id, attack: b.attack, ...dealt });
    }
  }
  state.areas = state.areas.filter((b) => b.explodes_tick > ctx.tick);
}

/** Opponents on the eight tiles around the repulsor's owner (walls excluded). */
function repulsorHits(ctx: TickCtx, f: Fighter, attack: string): Fighter[] {
  const tiles = repulsorRing(f.pos).filter((t) => !isWall(ctx.state.map, t));
  ctx.events.push({ kind: "repulse", owner: f.id, attack, pos: [f.pos[0], f.pos[1]], tiles });
  return ctx.state.fighters.filter(
    (t) =>
      t.alive &&
      !t.invulnerable &&
      weaponCanAffect(ctx.state, f.id, t) &&
      tiles.some((p) => eq(p, t.pos)),
  );
}

/**
 * Shoves `t` up to `tiles` steps in `dir`, one at a time, taking each stocked pad it lands on.
 * A wall (or a corner it can't cut past) stops it with a slam: damage and a stun. Another
 * fighter stops it with a collision that hurts both.
 */
function push(
  ctx: TickCtx,
  attacker: Fighter,
  t: Fighter,
  dir: Dir,
  tiles: number,
  later: (() => void)[],
): void {
  const { state } = ctx;
  const kb = state.rules.knockback;
  const from: [number, number] = [t.pos[0], t.pos[1]];
  for (let i = 0; i < tiles && t.alive; i++) {
    if (stepBlocked(state.map, t.pos, dir)) {
      const dealt = damage(ctx, t, kb.wall_slam_damage, attacker.id);
      ctx.events.push({
        kind: "wall_slam",
        attacker: attacker.id,
        target: t.id,
        damage: dealt.damage,
      });
      const until = ctx.tick + kb.wall_slam_stun;
      t.state_end = t.state === "idle" ? until : Math.max(t.state_end, until);
      t.state = "stunned";
      ctx.events.push({ kind: "stunned", fighter: t.id, ticks: kb.wall_slam_stun });
      break;
    }
    const next = add(t.pos, DIR_VEC[dir]);
    const other = state.fighters.find((o) => o.alive && o.id !== t.id && eq(o.pos, next));
    if (other) {
      const dmg = kb.fighter_collision_damage;
      damage(ctx, t, dmg, attacker.id);
      damage(ctx, other, dmg, attacker.id);
      ctx.events.push({
        kind: "collision",
        attacker: attacker.id,
        fighters: [t.id, other.id],
        damage: dmg,
      });
      break;
    }
    t.pos = next;
    // The victim takes each stocked pad it is pushed onto, at once, so a heal counts against a
    // slam at the end of the push. Damage that already brought it to 0 hp has killed it, though.
    const pad = stockedPad(state, t.pos);
    if (pad && t.hp > 0) takePickup(ctx, pad, t, later);
  }
  if (!eq(from, t.pos))
    ctx.events.push({
      kind: "knockback",
      attacker: attacker.id,
      target: t.id,
      from,
      to: [t.pos[0], t.pos[1]],
    });
}

function projectileHit(
  ctx: TickCtx,
  p: Pick<Projectile, "owner" | "attack" | "damage">,
  t: Fighter,
  ricochet = false,
): void {
  const dealt = damage(ctx, t, hitDamage(p.damage, ctx.state.rules.stats.armor), p.owner);
  ctx.events.push({
    kind: "hit",
    attacker: p.owner,
    target: t.id,
    attack: p.attack,
    ...dealt,
    ...(ricochet ? { ricochet: true as const } : {}),
  });
}

// ---------------------------------------------------------------- phase 6

function phase6Zone(ctx: TickCtx): void {
  const { state } = ctx;
  const rules = state.rules;
  for (const f of alive(state)) {
    if (!inZone(state, f.pos)) {
      const z = rules.zone;
      const amount = z.damage_base + z.damage_step * idiv(f.ticks_outside, z.damage_step_ticks);
      f.ticks_outside += 1;
      const d = damage(ctx, f, amount, null).damage;
      ctx.events.push({ kind: "zone_damage", fighter: f.id, damage: d });
    } else f.ticks_outside = 0;
  }
  const r = zoneRadiusAt(rules, state.map, ctx.tick);
  if (r !== state.zone.radius) {
    state.zone.radius = r;
    ctx.events.push({ kind: "zone_shrink", radius: r });
  }
}

// ---------------------------------------------------------------- phase 7

function phase7Deaths(ctx: TickCtx): void {
  for (const f of alive(ctx.state)) {
    if (f.hp <= 0) {
      f.alive = false;
      f.state = "dead";
      f.invulnerable = false;
      ctx.events.push({ kind: "death", fighter: f.id });
    }
  }
}

// ---------------------------------------------------------------- phase 8

function phase8Timers(ctx: TickCtx): void {
  const { state } = ctx;
  const rules = state.rules;
  for (const f of alive(state)) {
    for (const k of Object.keys(f.cooldowns)) f.cooldowns[k] = Math.max(0, f.cooldowns[k]! - 1);
    if ((f.state === "recovering" || f.state === "stunned") && f.state_end <= ctx.tick)
      f.state = "idle";
    if (f.state === "dashing") {
      if (rules.dash.recovery > 0) {
        f.state = "recovering";
        f.state_end = ctx.tick + rules.dash.recovery;
      } else f.state = "idle";
    }
    f.invulnerable = false;
    for (const [buff, until] of Object.entries(f.buffs)) {
      if (until > ctx.tick) continue;
      delete f.buffs[buff];
      ctx.events.push({ kind: "buff_end", fighter: f.id, buff });
    }
  }
  // A pad restocks at the end of the tick before its respawn tick, so the observation
  // for that tick shows it and a fighter standing on it takes it during that tick.
  for (const pad of state.pickups) {
    if (pad.available || pad.respawn_tick > ctx.tick + 1) continue;
    pad.available = true;
    ctx.events.push({
      kind: "pickup_spawn",
      pad: pad.id,
      pickup: pad.kind,
      pos: [pad.pos[0], pad.pos[1]],
    });
  }
  state.result = checkEnd(state, ctx.tick);
  state.tick += 1;
}
