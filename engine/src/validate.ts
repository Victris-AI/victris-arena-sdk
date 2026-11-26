// Phase 1: turn a bot's requested turn into a validated one, plus a rejection for every part
// that was refused. Validation reads only the state at the start of the tick, so what depends on
// where the fighter ends up (an aimed attack's target) is checked later, in phase 5.

import { chebyshev, eq, isDir, type Dir } from "./geometry.ts";
import { canSee } from "./sight.ts";
import type { Attack } from "./rules.ts";
import { isWall, stepBlocked } from "./map.ts";
import type { AttackInput, Fighter, MatchState, TurnInput } from "./state.ts";

/** A validated attack: fires in phase 5, from wherever the fighter stands after movement. */
export interface ValidAttack {
  name: string;
  /** absent for the repulsor, which has no aim */
  target?: [number, number];
}

/** A validated turn. The movement phase is `move`, `dash` or neither; the attack phase follows it. */
export interface ValidTurn {
  move?: Dir;
  dash?: Dir;
  attack?: ValidAttack;
  shout?: string;
}

/** Every reason the engine refuses a part of a turn; reported in `rejected` events. */
export const REJECT_REASONS = [
  "invalid_state", // the fighter can't act now: recovering from a dash, or stunned
  "conflicting_moves", // both `move` and `dash` were given
  "bad_dir", // a direction is not one of N NE E SE S SW W NW
  "missing_target", // an aimed attack without `target`
  "bad_target", // `target` is not [x, y] integers within ±1000, or is the tile you end on
  "unknown_attack", // the attack is not in the rules' attack table
  "not_ready", // on cooldown
  "blocked", // a step into a wall, off the map, or past a wall corner
  "out_of_range", // frostburst target beyond cast range from the tile you end on
  "not_visible", // frostburst target behind cover or outside sight from the tile you end on
  "bad_text", // a shout that is empty, longer than rules.shout.max_length characters, or not allowed by the rules
] as const;

export type RejectReason = (typeof REJECT_REASONS)[number];

/** A part of a turn that was refused. `part` is `move`, `dash`, `attack`, `shout`, or `turn` for the whole turn. */
export interface Rejection {
  part: "move" | "dash" | "attack" | "shout" | "turn";
  reason: RejectReason;
}

/**
 * The turn the engine will play, and what it refused. Parts are judged separately, so a blocked
 * step is listed in `rejected` while the attack that came with it still fires.
 */
export interface Validation {
  turn: ValidTurn;
  rejected: Rejection[];
}

function isTile(v: unknown): v is [number, number] {
  return (
    Array.isArray(v) &&
    v.length === 2 &&
    v.every((n) => typeof n === "number" && Number.isInteger(n) && Math.abs(n) <= 1000)
  );
}

type Part<T> = { ok: true; value: T } | { ok: false; reason: RejectReason };

/**
 * Why `target` can't be aimed at from where `f` stands, or null. A target is any tile but the
 * fighter's own, and a frostburst's must also be within range, not a wall and in sight. The
 * engine asks this in phase 5, from the tile the fighter ended its movement on.
 */
export function targetProblem(
  state: MatchState,
  f: Fighter,
  atk: Attack,
  target: readonly [number, number],
): RejectReason | null {
  if (eq(target, f.pos)) return "bad_target";
  if (atk.kind !== "area") return null;
  if (chebyshev(f.pos, target) > atk.range) return "out_of_range";
  if (isWall(state.map, target)) return "blocked";
  if (!canSee(state, f, target)) return "not_visible";
  return null;
}

function validateMovement(
  state: MatchState,
  f: Fighter,
  kind: "move" | "dash",
  dir: unknown,
): Part<Dir> {
  if (!isDir(dir)) return { ok: false, reason: "bad_dir" };
  if ((f.cooldowns[kind] ?? 0) > 0) return { ok: false, reason: "not_ready" };
  if (kind === "move" && stepBlocked(state.map, f.pos, dir))
    return { ok: false, reason: "blocked" };
  return { ok: true, value: dir };
}

/** What can be judged from the start of the tick: the attack exists, is off cooldown, and its target is a tile. */
function validateAttack(state: MatchState, f: Fighter, input: AttackInput): Part<ValidAttack> {
  const name = input.name;
  const atk =
    typeof name === "string" && Object.hasOwn(state.rules.attacks, name)
      ? state.rules.attacks[name]
      : undefined;
  if (typeof name !== "string" || !atk) return { ok: false, reason: "unknown_attack" };
  if ((f.cooldowns[name] ?? 0) > 0) return { ok: false, reason: "not_ready" };
  // The repulsor hits every tile around the fighter, so any `target` sent with it is ignored.
  if (atk.kind === "burst") return { ok: true, value: { name } };
  if (input.target == null) return { ok: false, reason: "missing_target" };
  if (!isTile(input.target)) return { ok: false, reason: "bad_target" };
  return { ok: true, value: { name, target: [input.target[0], input.target[1]] } };
}

/** A shout is 1 to max_length characters (code points) that aren't all spaces, off its cooldown. */
function validateShout(state: MatchState, f: Fighter, text: unknown): Part<string> {
  const max = state.rules.shout?.max_length ?? 0;
  if (typeof text !== "string" || text.trim() === "" || [...text].length > max)
    return { ok: false, reason: "bad_text" };
  if ((f.cooldowns.shout ?? 0) > 0) return { ok: false, reason: "not_ready" };
  return { ok: true, value: text };
}

export function validateTurn(
  state: MatchState,
  f: Fighter,
  input: TurnInput | undefined | null,
): Validation {
  const turn: ValidTurn = {};
  const rejected: Rejection[] = [];
  if (!input || typeof input !== "object") return { turn, rejected };
  // Talking takes no action, so a fighter can shout while it recovers or is stunned.
  if (input.shout !== undefined && input.shout !== null) {
    const s = validateShout(state, f, input.shout);
    if (s.ok) turn.shout = s.value;
    else rejected.push({ part: "shout", reason: s.reason });
  }
  const hasMove = input.move !== undefined && input.move !== null;
  const hasDash = input.dash !== undefined && input.dash !== null;
  const hasAttack = input.attack !== undefined && input.attack !== null;
  if (!hasMove && !hasDash && !hasAttack) return { turn, rejected };
  if (f.state !== "idle")
    return { turn, rejected: [...rejected, { part: "turn", reason: "invalid_state" }] };

  if (hasMove && hasDash) rejected.push({ part: "turn", reason: "conflicting_moves" });
  else {
    for (const kind of ["move", "dash"] as const) {
      if (input[kind] === undefined || input[kind] === null) continue;
      const m = validateMovement(state, f, kind, input[kind]);
      if (m.ok) turn[kind] = m.value;
      else rejected.push({ part: kind, reason: m.reason });
    }
  }
  if (hasAttack) {
    const a = validateAttack(state, f, input.attack as AttackInput);
    if (a.ok) turn.attack = a.value;
    else rejected.push({ part: "attack", reason: a.reason });
  }
  return { turn, rejected };
}
