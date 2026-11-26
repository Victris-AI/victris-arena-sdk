import { eq } from "./geometry.ts";
import { blastTiles, canSee } from "./sight.ts";
import { dangerTiles, type Danger } from "./danger.ts";
import { nextShrink, weaponCanAffect } from "./match.ts";
import { moveOptions, type DashOption, type MoveOption } from "./options.ts";
import type { Fighter, FighterStateName, GameEvent, MatchState } from "./state.ts";

export interface SelfView {
  id: number;
  pos: [number, number];
  hp: number;
  max_hp: number;
  state: FighterStateName;
  state_ticks_left: number;
  slow_ticks_left: number;
  /** active pickup buffs: kind → ticks left, counting the tick you reply to */
  buffs: Record<string, number>;
  cooldowns: Record<string, number>;
  /** filled in by the server; the engine has no clock */
  budget_ms_left?: number;
}

export interface EnemyView {
  id: number;
  pos: [number, number];
  hp: number;
  /** ticks until it can dash again; 0 = ready */
  dash_cooldown: number;
  state: FighterStateName;
  state_ticks_left: number;
  slow_ticks_left: number;
  buffs: Record<string, number>;
}

export interface PickupView {
  id: number;
  pos: [number, number];
  kind: string;
  /** 0 = on the pad now; otherwise ticks until it reappears */
  ready_in: number;
}

export interface ProjectileView {
  id: number;
  /** tile the projectile is in */
  pos: [number, number];
  /** exact position in thousandths of a tile (tile centres are multiples of 1000) */
  exact_pos: [number, number];
  /** it flies along the straight line from the centre of `origin` through the centre of `target` */
  origin: [number, number];
  target: [number, number];
  speed: number;
  owner: number;
  damage: number;
  attack: string;
  bounces_left: number;
}

export interface Observation {
  type: "observation";
  tick: number;
  self: SelfView;
  enemies: EnemyView[];
  projectiles: ProjectileView[];
  pickups: PickupView[];
  /** steps you could start this tick (empty if your move is on cooldown or you can't act) */
  moves: MoveOption[];
  /** dashes you could start this tick, each with the tile it lands on and how far it goes */
  dashes: DashOption[];
  areas: {
    id: number;
    owner: number;
    attack: string;
    pos: [number, number];
    damage: number;
    radius: number;
    slow: number;
    ticks_left: number;
    tiles: [number, number][];
  }[];
  zone: {
    center: [number, number];
    radius: number;
    next_radius: number | null;
    shrinks_in: number | null;
  };
  /** tiles each visible opponent attack will hit, and when; see Danger */
  danger: Danger[];
  events: GameEvent[];
}

function ticksLeft(state: MatchState, f: Fighter): number {
  if (f.state === "recovering" || f.state === "stunned") {
    return Math.max(0, f.state_end - state.tick + 1);
  }
  return 0;
}

/** Ticks until the slow area that is slowing `f` this tick explodes, or 0 when nothing is. */
function slowTicksLeft(state: MatchState, f: Fighter): number {
  let left = 0;
  for (const b of state.areas) {
    if (b.slow === 0 || state.tick <= b.launched_tick || state.tick > b.explodes_tick) continue;
    if (
      weaponCanAffect(state, b.owner, f) &&
      blastTiles(state, b.pos, b.radius).some((t) => eq(t, f.pos))
    )
      left = Math.max(left, b.explodes_tick - state.tick + 1);
  }
  return left;
}

function buffView(state: MatchState, f: Fighter): Record<string, number> {
  return Object.fromEntries(
    Object.entries(f.buffs).map(([k, until]) => [k, until - state.tick + 1]),
  );
}

/** Events a fighter is told about: its own, those involving a fighter it can see, and global ones (shouts are heard everywhere). */
function visibleEvents(state: MatchState, viewer: Fighter): GameEvent[] {
  const sees = (id: number) => {
    if (id === viewer.id) return true;
    const f = state.fighters.find((x) => x.id === id);
    return !!f && canSee(state, viewer, f.pos);
  };
  return state.events.filter((e) => {
    switch (e.kind) {
      case "rejected":
        return e.fighter === viewer.id;
      case "zone_shrink":
      case "shout":
        return true;
      case "pickup_spawn":
        return canSee(state, viewer, e.pos);
      case "hit":
      case "knockback":
      case "wall_slam":
        return sees(e.attacker) || sees(e.target);
      case "collision":
        return e.fighters.some(sees);
      case "area_spawn":
      case "area_explode":
      case "projectile_spawn":
      case "projectile_bounce":
      case "repulse":
        return e.owner === viewer.id || canSee(state, viewer, e.pos);
      case "projectile_end":
        return (
          canSee(state, viewer, e.pos) ||
          state.events.some(
            (s) =>
              s.kind === "projectile_spawn" &&
              s.projectile === e.projectile &&
              s.owner === viewer.id,
          )
        );
      default:
        return sees(e.fighter);
    }
  });
}

/** The world as fighter `id` sees it, after the previous tick resolved. */
export function observe(state: MatchState, id: number): Observation {
  const me = state.fighters.find((f) => f.id === id);
  if (!me) throw new Error(`no fighter ${id}`);
  const rules = state.rules;
  const seenFighters = state.fighters.filter(
    (f) => f.id !== id && f.alive && canSee(state, me, f.pos),
  );
  const seenProjectiles = state.projectiles.filter(
    (p) => p.owner === id || canSee(state, me, p.pos),
  );
  const seenAreas = state.areas.filter((b) => b.owner === id || canSee(state, me, b.pos));
  const enemies: EnemyView[] = seenFighters.map((f) => ({
    id: f.id,
    pos: [f.pos[0], f.pos[1]],
    hp: f.hp,
    dash_cooldown: f.cooldowns.dash ?? 0,
    state: f.state,
    state_ticks_left: ticksLeft(state, f),
    slow_ticks_left: slowTicksLeft(state, f),
    buffs: buffView(state, f),
  }));
  const projectiles: ProjectileView[] = seenProjectiles.map((p) => ({
    id: p.id,
    pos: [p.pos[0], p.pos[1]],
    exact_pos: [p.exact_pos[0], p.exact_pos[1]],
    origin: [p.origin[0], p.origin[1]],
    target: [p.target[0], p.target[1]],
    speed: p.speed,
    owner: p.owner,
    damage: p.damage,
    attack: p.attack,
    bounces_left: p.bounces_left,
  }));
  // The next shrink is only announced within the warning window.
  const ns = nextShrink(rules, state.map, state.tick - 1);
  const announced = ns && ns.tick - state.tick < rules.zone.warning_ticks ? ns : null;
  return {
    type: "observation",
    tick: state.tick,
    self: {
      id: me.id,
      pos: [me.pos[0], me.pos[1]],
      hp: me.hp,
      max_hp: rules.stats.max_hp,
      state: me.state,
      state_ticks_left: ticksLeft(state, me),
      slow_ticks_left: slowTicksLeft(state, me),
      buffs: buffView(state, me),
      cooldowns: { ...me.cooldowns },
    },
    enemies,
    projectiles,
    ...moveOptions(state, me),
    pickups: state.pickups
      .filter((p) => canSee(state, me, p.pos))
      .map((p) => ({
        id: p.id,
        pos: [p.pos[0], p.pos[1]],
        kind: p.kind,
        ready_in: p.available ? 0 : p.respawn_tick - state.tick,
      })),
    areas: seenAreas.map((b) => ({
      id: b.id,
      owner: b.owner,
      attack: b.attack,
      pos: [...b.pos],
      damage: b.damage,
      radius: b.radius,
      slow: b.slow,
      ticks_left: b.explodes_tick - state.tick + 1,
      tiles: blastTiles(state, b.pos, b.radius),
    })),
    zone: {
      center: [state.zone.center[0], state.zone.center[1]],
      radius: state.zone.radius,
      next_radius: announced ? announced.radius : null,
      shrinks_in: announced ? announced.tick - state.tick : null,
    },
    danger: dangerTiles(state, me, { projectiles: seenProjectiles, areas: seenAreas }),
    events: visibleEvents(state, me),
  };
}
