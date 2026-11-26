// Match statistics: what each fighter did over a match, counted from the engine's own
// events as it steps. `replayStats` re-simulates a replay, so any replay yields exactly the
// numbers the server recorded for it.

import { chebyshev, eq } from "./geometry.ts";
import { createMatch } from "./match.ts";
import { checkCompatible, type RecordedTurn, type Replay, type ReplayBot } from "./replay.ts";
import { PICKUP_KINDS } from "./rules.ts";
import type { GameEvent, MatchState } from "./state.ts";
import { step } from "./step.ts";
import { idiv } from "./util.ts";
import { validateTurn, type ValidTurn } from "./validate.ts";

/** Bumped whenever a field changes meaning, so saved stats can be told apart. 2 added refused turns, timing, disconnects and disqualified. */
export const STATS_VERSION = 2;

/** Reply-time histogram buckets: upper bounds in thousandths of the tick limit, then one bucket for anything slower. */
export const REPLY_BUCKETS = [
  10, 25, 50, 100, 200, 300, 400, 500, 600, 700, 800, 850, 900, 950, 1000,
];
/** A reply taking at least this many thousandths of the tick limit is close to timing out. */
export const NEAR_LIMIT = 800;

/**
 * How long a fighter took to reply, as the server timed it: from sending the observation to the
 * reply arriving, network included. A reply that never came counts at the deadline.
 */
export interface ReplyTiming {
  /** timed replies, timeouts included */
  replies: number;
  mean_ms: number;
  /** the median and 95th percentile reply; adding matches up (sumFighterStats), the histogram bucket each falls in, at most */
  p50_ms: number;
  p95_ms: number;
  max_ms: number;
  /** replies that took at least 80% of the tick limit: one slow moment from a timeout */
  near_limit: number;
  /** the per-tick limit and match budget the replies were timed against, and the budget left at the end */
  tick_ms: number;
  budget_ms: number;
  budget_ms_left: number;
  /** replies per bucket of REPLY_BUCKETS, then one for slower, so matches can be added up */
  histogram: number[];
}

export interface WeaponStats {
  /** attacks fired: sent and accepted by the engine */
  uses: number;
  /** hits on an opponent */
  hits: number;
  /** hp those hits removed (the power buff included) */
  damage: number;
}

export interface Occupancy {
  width: number;
  height: number;
  /** Row-major counts, sampled before each resolved tick while alive. */
  counts: number[];
}

export interface FighterStats {
  /** Absent in statistics recorded before occupancy tracking was added. */
  occupancy?: Occupancy;
  id: number;
  name: string;
  version: string;
  /** hp at the end of the match */
  hp: number;
  alive: boolean;
  /** one-tile steps taken */
  moves: number;
  /** accepted steps that didn't happen because another fighter was in the way */
  moves_blocked: number;
  dashes: number;
  /** tiles covered by dashing */
  dash_tiles: number;
  /** by attack name; every attack in the rules is listed */
  weapons: Record<string, WeaponStats>;
  /** shots that bounced off a wall, and the hits (and hp) they scored after bouncing */
  ricochets: { bounces: number; hits: number; damage: number };
  /** pickups taken, by kind; every kind in the rules is listed */
  pickups: Record<string, number>;
  /** hp restored by health pickups */
  healed: number;
  /** hp removed from opponents, and the same by source: attack names, "wall_slam", "collision" */
  damage_dealt: number;
  dealt_by_source: Record<string, number>;
  /** hp lost, and the same by source: attack names, "wall_slam", "collision", "zone" */
  damage_taken: number;
  taken_by_source: Record<string, number>;
  /** opponents this fighter's repulsor slammed into a wall */
  wall_slams: number;
  /** times this fighter was shoved, and stunned */
  knocked_back: number;
  stunned: number;
  /** ticks ended outside the safe zone */
  zone_ticks: number;
  /** parts of turns the engine refused, by reason */
  rejected: Record<string, number>;
  /** turns with at least one refused part, and the same by reason (a turn counts once per reason) */
  refused_turns: number;
  refused_turns_by_reason: Record<string, number>;
  /** ticks the server played as idle for this fighter, by reason (timeout, malformed_json, disconnected…) */
  server_idles: Record<string, number>;
  /** reply times, or null when the replay has none (the simulator doesn't time replies) */
  timing: ReplyTiming | null;
  /** contiguous runs of recorded disconnected idle turns, not socket-close events */
  disconnects: number;
  /** the match ended because this fighter failed too many ticks in a row */
  disqualified: boolean;
}

export interface MatchStats {
  stats_version: number;
  map: string;
  seed: number;
  /** ticks resolved */
  ticks: number;
  /** fighter id of the winner, or null for a draw (or an unfinished match) */
  winner: number | null;
  /** how the match ended; null if it didn't */
  reason: string | null;
  fighters: FighterStats[];
}

export function newStats(state: MatchState, bots: ReplayBot[] = []): MatchStats {
  const rules = state.rules;
  const kinds = PICKUP_KINDS.filter((k) => rules.pickups?.[k]);
  return {
    stats_version: STATS_VERSION,
    map: state.map.name,
    seed: state.seed,
    ticks: 0,
    winner: null,
    reason: null,
    fighters: state.fighters.map((f) => {
      const bot = bots.find((b) => b.id === f.id);
      return {
        id: f.id,
        name: bot?.name ?? `fighter ${f.id}`,
        version: bot?.version ?? "",
        occupancy: {
          width: state.map.width,
          height: state.map.height,
          counts: Array(state.map.width * state.map.height).fill(0),
        },
        hp: f.hp,
        alive: f.alive,
        moves: 0,
        moves_blocked: 0,
        dashes: 0,
        dash_tiles: 0,
        weapons: Object.fromEntries(
          Object.keys(rules.attacks).map((a) => [a, { uses: 0, hits: 0, damage: 0 }]),
        ),
        ricochets: { bounces: 0, hits: 0, damage: 0 },
        pickups: Object.fromEntries(kinds.map((k) => [k, 0])),
        healed: 0,
        damage_dealt: 0,
        dealt_by_source: {},
        damage_taken: 0,
        taken_by_source: {},
        wall_slams: 0,
        knocked_back: 0,
        stunned: 0,
        zone_ticks: 0,
        rejected: {},
        refused_turns: 0,
        refused_turns_by_reason: {},
        server_idles: {},
        timing: null,
        disconnects: 0,
        disqualified: false,
      };
    }),
  };
}

const bump = (o: Record<string, number>, k: string, n = 1) => (o[k] = (o[k] ?? 0) + n);

/**
 * Resolves one tick (like `step`) and adds what happened to `stats`. A turn's `reason`
 * (a server-substituted idle, as recorded in replays) is counted in `server_idles`.
 */
export function stepWithStats(
  stats: MatchStats,
  state: MatchState,
  turns: Record<number, RecordedTurn | undefined | null>,
): GameEvent[] {
  const fighter = (id: number) => stats.fighters.find((f) => f.id === id);
  // Movement isn't an event, so judge it from the validated turn and where each fighter stood.
  const before = new Map<number, { pos: [number, number]; hp: number; turn: ValidTurn }>();
  for (const f of state.fighters) {
    if (!f.alive) continue;
    const occupancy = fighter(f.id)?.occupancy;
    if (occupancy) occupancy.counts[f.pos[1] * occupancy.width + f.pos[0]]! += 1;
    const t = turns[f.id];
    if (t?.reason) bump(fighter(f.id)!.server_idles, t.reason);
    before.set(f.id, { pos: [f.pos[0], f.pos[1]], hp: f.hp, turn: validateTurn(state, f, t).turn });
  }
  const events = step(state, turns);
  stats.ticks += 1;

  // hp as of the event being read: a push can heal a fighter after this tick's repulsor hit it.
  const hp = new Map([...before].map(([id, b]) => [id, b.hp]));
  const hurt = (target: number, source: string, n: number, attacker?: number) => {
    const now = hp.get(target);
    if (now !== undefined) hp.set(target, Math.max(0, now - n));
    const t = fighter(target);
    if (t) ((t.damage_taken += n), bump(t.taken_by_source, source, n));
    const a = attacker === undefined || attacker === target ? undefined : fighter(attacker);
    if (a) ((a.damage_dealt += n), bump(a.dealt_by_source, source, n));
  };
  for (const e of events) {
    switch (e.kind) {
      case "attack": {
        const w = fighter(e.fighter)?.weapons[e.attack];
        if (w) w.uses += 1;
        break;
      }
      case "hit": {
        hurt(e.target, e.attack, e.damage, e.attacker);
        const a = fighter(e.attacker);
        if (!a || e.attacker === e.target) break;
        const w = a.weapons[e.attack];
        if (w) ((w.hits += 1), (w.damage += e.damage));
        if (e.ricochet) ((a.ricochets.hits += 1), (a.ricochets.damage += e.damage));
        break;
      }
      case "projectile_bounce": {
        const a = fighter(e.owner);
        if (a) a.ricochets.bounces += 1;
        break;
      }
      case "dash": {
        const f = fighter(e.fighter);
        if (f) ((f.dashes += 1), (f.dash_tiles += chebyshev(e.from, e.to)));
        break;
      }
      case "pickup": {
        const f = fighter(e.fighter);
        if (!f) break;
        bump(f.pickups, e.pickup);
        const was = hp.get(e.fighter);
        const amount = state.rules.pickups?.health?.amount ?? 0;
        if (e.pickup === "health" && was !== undefined) {
          const now = Math.min(state.rules.stats.max_hp, was + amount);
          f.healed += now - was;
          hp.set(e.fighter, now);
        }
        break;
      }
      case "wall_slam": {
        hurt(e.target, "wall_slam", e.damage, e.attacker);
        const a = fighter(e.attacker);
        if (a) a.wall_slams += 1;
        break;
      }
      case "collision":
        for (const id of e.fighters) hurt(id, "collision", e.damage, e.attacker);
        break;
      case "knockback": {
        const f = fighter(e.target);
        if (f) f.knocked_back += 1;
        break;
      }
      case "stunned": {
        const f = fighter(e.fighter);
        if (f) f.stunned += 1;
        break;
      }
      case "zone_damage": {
        hurt(e.fighter, "zone", e.damage);
        const f = fighter(e.fighter);
        if (f) f.zone_ticks += 1;
        break;
      }
      case "rejected": {
        const f = fighter(e.fighter);
        if (f) bump(f.rejected, e.reason);
        break;
      }
    }
  }
  for (const f of stats.fighters) {
    const reasons = new Set(
      events.flatMap((e) => (e.kind === "rejected" && e.fighter === f.id ? [e.reason] : [])),
    );
    if (reasons.size) f.refused_turns += 1;
    for (const r of reasons) bump(f.refused_turns_by_reason, r);
  }

  for (const [id, b] of before) {
    if (!b.turn.move) continue;
    const f = fighter(id)!;
    const now = state.fighters.find((x) => x.id === id)!;
    // A repulsor fires after movement; its knockback starts where the step ended.
    const kb = events.find(
      (e): e is Extract<GameEvent, { kind: "knockback" }> =>
        e.kind === "knockback" && e.target === id,
    );
    if (eq(kb ? kb.from : now.pos, b.pos)) f.moves_blocked += 1;
    else f.moves += 1;
  }
  for (const f of state.fighters) {
    const s = fighter(f.id);
    if (s) ((s.hp = f.hp), (s.alive = f.alive));
  }
  if (state.result) {
    stats.winner = state.result.winner;
    stats.reason = state.result.reason;
  }
  return events;
}

/** Re-simulates a replay and returns its stats. The recorded result wins over the simulated one (forfeits, disqualifications). */
export function replayStats(replay: Replay): MatchStats {
  const { rules, map } = checkCompatible(replay.header);
  const state = createMatch(rules, map, replay.header.seed);
  const stats = newStats(state, replay.header.bots);
  const played: Replay["ticks"] = [];
  for (const t of replay.ticks) {
    if (state.result) break;
    stepWithStats(stats, state, t.turns);
    played.push(t);
  }
  const r = replay.result ?? state.result;
  if (r) {
    stats.winner = r.winner;
    stats.reason = r.reason;
  }
  for (const f of stats.fighters) {
    const turns = played.map((t) => t.turns[String(f.id)]);
    const ms = turns.flatMap((t) => (t?.ms === undefined ? [] : [t.ms]));
    f.timing = ms.length
      ? replyTiming(ms, rules.limits.tick_ms, rules.limits.match_budget_ms)
      : null;
    // A disconnect is a run of ticks idled as "disconnected".
    f.disconnects = turns.filter(
      (t, i) => t?.reason === "disconnected" && turns[i - 1]?.reason !== "disconnected",
    ).length;
    f.disqualified = r?.reason === "disqualified" && r.winner !== f.id;
  }
  return stats;
}

/** Which REPLY_BUCKETS bucket a reply of `ms` falls in. */
function bucketOf(ms: number, tickMs: number): number {
  const permille = idiv(ms * 1000, Math.max(1, tickMs));
  const i = REPLY_BUCKETS.findIndex((edge) => permille <= edge);
  return i === -1 ? REPLY_BUCKETS.length : i;
}

/** The q-th percentile (nearest rank) of sorted values. */
const percentile = (sorted: number[], q: number) =>
  sorted[Math.max(0, idiv(q * sorted.length + 99, 100) - 1)]!;

/** Reply timing from one match's reply times. */
export function replyTiming(ms: number[], tickMs: number, budgetMs: number): ReplyTiming {
  const sorted = [...ms].sort((a, b) => a - b);
  const total = ms.reduce((a, b) => a + b, 0);
  const histogram = new Array<number>(REPLY_BUCKETS.length + 1).fill(0);
  for (const m of ms) histogram[bucketOf(m, tickMs)]! += 1;
  return {
    replies: ms.length,
    mean_ms: idiv(total, ms.length),
    p50_ms: percentile(sorted, 50),
    p95_ms: percentile(sorted, 95),
    max_ms: sorted[sorted.length - 1]!,
    near_limit: ms.filter((m) => m * 1000 >= NEAR_LIMIT * tickMs).length,
    tick_ms: tickMs,
    budget_ms: budgetMs,
    budget_ms_left: Math.max(0, budgetMs - total),
    histogram,
  };
}

/**
 * Several matches' reply timing added up. Percentiles come from the summed histogram, so each is the
 * upper bound of its bucket (never more than the slowest reply); the budget left is the lowest seen.
 */
export function mergeTiming(list: ReplyTiming[]): ReplyTiming | null {
  if (!list.length) return null;
  const last = list[list.length - 1]!;
  const replies = list.reduce((a, t) => a + t.replies, 0);
  const histogram = new Array<number>(REPLY_BUCKETS.length + 1).fill(0);
  for (const t of list) t.histogram.forEach((n, i) => (histogram[i]! += n));
  const max = Math.max(...list.map((t) => t.max_ms));
  const bound = (q: number) => {
    const rank = Math.max(1, idiv(q * replies + 99, 100));
    let seen = 0;
    for (let i = 0; i < histogram.length; i++) {
      seen += histogram[i]!;
      if (seen >= rank)
        return i < REPLY_BUCKETS.length
          ? Math.min(max, idiv(REPLY_BUCKETS[i]! * last.tick_ms, 1000))
          : max;
    }
    return max;
  };
  return {
    replies,
    mean_ms: replies
      ? idiv(
          list.reduce((a, t) => a + t.mean_ms * t.replies, 0),
          replies,
        )
      : 0,
    p50_ms: bound(50),
    p95_ms: bound(95),
    max_ms: max,
    near_limit: list.reduce((a, t) => a + t.near_limit, 0),
    tick_ms: last.tick_ms,
    budget_ms: last.budget_ms,
    budget_ms_left: Math.min(...list.map((t) => t.budget_ms_left)),
    histogram,
  };
}

// ------------------------------------------------------------ text

const pct = (n: number, d: number) => (d ? `${idiv(100 * n, d)}%` : "-");
const list = (o: Record<string, number>) =>
  Object.entries(o)
    .filter(([, v]) => v)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `${k} ${v}`)
    .join(", ") || "-";

/** The stats as table rows: a label, then one cell per fighter. The first row names the fighters. */
export function statsRows(stats: MatchStats): [string, ...string[]][] {
  const fs = stats.fighters;
  const rows: [string, ...string[]][] = [];
  const row = (label: string, cell: (f: FighterStats) => string | number) =>
    rows.push([label, ...fs.map((f) => String(cell(f)))]);
  row("", (f) => `${f.name}${f.version ? ` @${f.version}` : ""}`);
  row("result", (f) =>
    stats.winner === null ? (stats.reason ? "draw" : "-") : stats.winner === f.id ? "WIN" : "loss",
  );
  row("hp left", (f) => (f.alive ? f.hp : `${f.hp} (dead)`));
  row("damage dealt", (f) => f.damage_dealt);
  row("damage taken", (f) => f.damage_taken);
  row("moves", (f) => `${f.moves}${f.moves_blocked ? ` (+${f.moves_blocked} blocked)` : ""}`);
  row("dashes", (f) => `${f.dashes} (${f.dash_tiles} tiles)`);
  for (const name of Object.keys(fs[0]?.weapons ?? {})) {
    row(name, (f) => {
      const w = f.weapons[name]!;
      return w.uses ? `${w.hits}/${w.uses} hit (${pct(w.hits, w.uses)}) · ${w.damage} dmg` : "-";
    });
  }
  row("ricochets", (f) =>
    f.ricochets.bounces
      ? `${f.ricochets.hits}/${f.ricochets.bounces} hit · ${f.ricochets.damage} dmg`
      : "-",
  );
  row("wall slams", (f) => f.wall_slams);
  row("pickups", (f) => list(f.pickups) + (f.healed ? ` (+${f.healed} hp)` : ""));
  row("taken from", (f) => list(f.taken_by_source));
  row("shoved / stunned", (f) => `${f.knocked_back} / ${f.stunned}`);
  row("ticks outside zone", (f) => f.zone_ticks);
  row("rejected", (f) => list(f.rejected));
  row("server idles", (f) => list(f.server_idles));
  row("reply time", (f) =>
    f.timing
      ? `median ${f.timing.p50_ms} · p95 ${f.timing.p95_ms} · max ${f.timing.max_ms} ms`
      : "-",
  );
  row("near the limit", (f) =>
    f.timing
      ? `${f.timing.near_limit} of ${f.timing.replies} (≥ ${idiv(NEAR_LIMIT * f.timing.tick_ms, 1000)} ms)`
      : "-",
  );
  row("budget left", (f) =>
    f.timing
      ? `${idiv(f.timing.budget_ms_left, 1000)} of ${idiv(f.timing.budget_ms, 1000)} s`
      : "-",
  );
  row("disconnects", (f) => f.disconnects);
  row("disqualified", (f) => (f.disqualified ? "yes" : "no"));
  return rows;
}

/** One line about the match: map, seed, length and how it ended. */
export function statsHeadline(stats: MatchStats): string {
  return `${stats.map} · seed ${stats.seed} · ${stats.ticks} ticks${stats.reason ? ` · ${stats.reason.replace(/_/g, " ")}` : ""}`;
}

/** The stats as a plain-text table, one column per fighter. */
export function formatStats(stats: MatchStats): string {
  const rows = statsRows(stats);
  const widths = rows[0]!.map((_, i) => Math.max(...rows.map((r) => r[i]!.length)));
  return [
    statsHeadline(stats),
    ...rows.map((r) =>
      r
        .map((c, i) => c.padEnd(widths[i]!))
        .join("   ")
        .trimEnd(),
    ),
  ].join("\n");
}

/** Adds up several fighters' stats (one bot over many matches, say). Counts sum, timing merges; hp and alive come from the last. */
export function sumFighterStats(list: FighterStats[]): FighterStats | undefined {
  const add = (a: any, b: any): any => {
    if (typeof b === "number") return (typeof a === "number" ? a : 0) + b;
    if (Array.isArray(b)) return b.map((v, i) => add(a?.[i], v));
    if (b && typeof b === "object") {
      const out = { ...a };
      for (const [k, v] of Object.entries(b)) out[k] = add(out[k], v);
      return out;
    }
    return b;
  };
  if (!list.length) return undefined;
  const last = list[list.length - 1]!;
  const {
    timing: _t,
    disqualified: _d,
    ...counts
  } = list.reduce((acc, f) => add(acc, f), {} as FighterStats);
  const timing = mergeTiming(list.flatMap((f) => (f.timing ? [f.timing] : [])));
  return {
    ...counts,
    timing,
    disqualified: list.some((f) => f.disqualified),
    id: last.id,
    name: last.name,
    version: last.version,
    occupancy: list.every(
      (f) =>
        f.occupancy &&
        f.occupancy.width === last.occupancy?.width &&
        f.occupancy.height === last.occupancy?.height,
    )
      ? {
          ...last.occupancy!,
          counts: last.occupancy!.counts.map((_, i) =>
            list.reduce((n, f) => n + f.occupancy!.counts[i]!, 0),
          ),
        }
      : undefined,
    hp: last.hp,
    alive: last.alive,
  };
}
