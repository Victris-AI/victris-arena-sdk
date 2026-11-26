// Replay files: JSON Lines (gzip is applied by the caller, since the engine does no I/O).
// A replay holds everything needed to re-simulate: rules, map, seed, and every action
// the server resolved per tick, including idles from late or missing replies.

import { createMatch } from "./match.ts";
import { loadMap, type GameMap } from "./map.ts";
import { loadRules, rulesHash, type Rules } from "./rules.ts";
import type { MatchResult, MatchState, TurnInput } from "./state.ts";
import { cloneState, step } from "./step.ts";
import { hashValue } from "./util.ts";

export const ENGINE_VERSION = "0.24.0";
export const REPLAY_FORMAT_VERSION = 1;

export interface ReplayBot {
  id: number;
  name: string;
  version: string;
}

export interface ReplayHeader {
  type: "header";
  engine: string;
  /** Present on versioned replays; older files have neither field. */
  release?: string;
  replay_format?: number;
  rules_hash: string;
  map: string;
  seed: number;
  bots: ReplayBot[];
  /** embedded so a replay is self-contained */
  rules: Rules;
  map_data: GameMap;
}

/**
 * A recorded turn; `reason` explains a server-substituted idle (timeout, malformed, disconnected…),
 * and `ms` is how long the reply took as the server timed it (absent where nothing was timed, as in
 * the simulator). Neither changes how the turn plays.
 */
export type RecordedTurn = TurnInput & { reason?: string; ms?: number };

export interface ReplayTick {
  type: "tick";
  tick: number;
  turns: Record<string, RecordedTurn>;
  /** optional full state snapshot after this tick resolved */
  state?: unknown;
  /** optional state hash after this tick resolved, for divergence checks */
  hash?: string;
}

export interface ReplayResult extends MatchResult {
  type: "result";
}

export interface Replay {
  header: ReplayHeader;
  ticks: ReplayTick[];
  result: ReplayResult | null;
}

export function makeHeader(
  rules: Rules,
  map: GameMap,
  seed: number,
  bots: ReplayBot[],
): ReplayHeader {
  return {
    type: "header",
    engine: ENGINE_VERSION,
    rules_hash: rulesHash(rules),
    map: map.name,
    seed,
    bots,
    rules,
    map_data: map,
  };
}

export function encodeReplay(r: Replay): string {
  const lines: unknown[] = [r.header, ...r.ticks];
  if (r.result) lines.push(r.result);
  return lines.map((l) => JSON.stringify(l)).join("\n") + "\n";
}

export function parseReplay(text: string): Replay {
  let header: ReplayHeader | null = null;
  const ticks: ReplayTick[] = [];
  let result: ReplayResult | null = null;
  for (const line of text.split("\n")) {
    if (!line.trim()) continue;
    const obj = JSON.parse(line);
    if (obj.type === "header") header = obj;
    else if (obj.type === "tick") ticks.push(obj);
    else if (obj.type === "result") result = obj;
  }
  if (!header) throw new Error("replay: missing header");
  return { header, ticks, result };
}

/** A stable hash of everything that affects the future of the match. */
export function stateHash(state: MatchState): string {
  const { rules: _r, map: _m, events: _e, ...rest } = state;
  return hashValue(rest);
}

export function checkCompatible(header: ReplayHeader): { rules: Rules; map: GameMap } {
  if (header.replay_format !== undefined && header.replay_format !== REPLAY_FORMAT_VERSION)
    throw new Error(`replay: unsupported format ${header.replay_format}`);
  if (header.engine !== ENGINE_VERSION) {
    throw new Error(`replay: recorded with engine ${header.engine}, this is ${ENGINE_VERSION}`);
  }
  const rules = loadRules(header.rules);
  if (rulesHash(rules) !== header.rules_hash) throw new Error("replay: rules hash mismatch");
  return { rules, map: loadMap(header.map_data) };
}

function toTurnMap(turns: Record<string, RecordedTurn>): Record<number, TurnInput> {
  const out: Record<number, TurnInput> = {};
  for (const [id, a] of Object.entries(turns)) {
    const { reason: _reason, ...rest } = a;
    out[Number(id)] = rest;
  }
  return out;
}

export interface Simulation {
  /** states[i] is the state before tick i resolved; the last entry is the final state */
  states: MatchState[];
  final: MatchState;
}

/**
 * Re-simulates a replay. With `keepStates` every intermediate state is kept (for
 * viewers and --from); `upTo` stops before resolving that tick.
 */
export function simulate(
  replay: Replay,
  opts: { keepStates?: boolean; upTo?: number; verifyHashes?: boolean } = {},
): Simulation {
  const { rules, map } = checkCompatible(replay.header);
  const state = createMatch(rules, map, replay.header.seed);
  const states: MatchState[] = [];
  for (const t of replay.ticks) {
    if (opts.upTo !== undefined && t.tick >= opts.upTo) break;
    if (state.result) break;
    if (t.tick !== state.tick)
      throw new Error(`replay: expected tick ${state.tick}, found ${t.tick}`);
    if (opts.keepStates) states.push(cloneState(state));
    step(state, toTurnMap(t.turns));
    if (opts.verifyHashes && t.hash && stateHash(state) !== t.hash) {
      throw new Error(`replay: state diverged at tick ${t.tick}`);
    }
  }
  if (opts.keepStates) states.push(cloneState(state));
  return { states, final: state };
}

/** Re-simulates and checks the recorded result. Returns the recomputed result. */
export function verifyReplay(replay: Replay): {
  ok: boolean;
  result: MatchResult | null;
  recorded: MatchResult | null;
} {
  const sim = simulate(replay, { verifyHashes: true });
  const recorded = replay.result
    ? {
        winner: replay.result.winner,
        reason: replay.result.reason,
        final_tick: replay.result.final_tick,
      }
    : null;
  // Forfeits and disqualifications are decided by the server, not the simulation.
  if (recorded && (recorded.reason === "forfeit" || recorded.reason === "disqualified")) {
    const validWinner =
      recorded.winner === null
        ? recorded.reason === "forfeit"
        : sim.final.fighters.some((f) => f.id === recorded.winner && f.alive);
    // An external ending interrupts the next unresolved tick of a running match.
    const ok = sim.final.result === null && recorded.final_tick === sim.final.tick && validWinner;
    return { ok, result: ok ? recorded : sim.final.result, recorded };
  }
  const result = sim.final.result;
  const ok =
    !!result &&
    !!recorded &&
    result.winner === recorded.winner &&
    result.reason === recorded.reason &&
    result.final_tick === recorded.final_tick;
  return { ok, result, recorded };
}
