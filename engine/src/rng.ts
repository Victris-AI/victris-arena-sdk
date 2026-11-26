// PCG32 (XSH RR variant). The engine owns one instance per match and draws
// from it in a fixed order, so the same seed always yields the same match.

const MULT = 6364136223846793005n;
const INC = 1442695040888963407n; // must be odd
const MASK64 = (1n << 64n) - 1n;

export interface RngState {
  /** 64-bit state as a decimal string so match state stays JSON-serialisable. */
  s: string;
}

export function rngSeed(seed: number): RngState {
  let state = 0n;
  state = (state * MULT + INC) & MASK64;
  state = (state + BigInt.asUintN(64, BigInt(seed))) & MASK64;
  state = (state * MULT + INC) & MASK64;
  return { s: state.toString() };
}

/** Returns the next unsigned 32-bit value and advances the state in place. */
export function rngNext(rng: RngState): number {
  const old = BigInt(rng.s);
  rng.s = ((old * MULT + INC) & MASK64).toString();
  const xorshifted = Number((((old >> 18n) ^ old) >> 27n) & 0xffffffffn);
  const rot = Number(old >> 59n);
  return ((xorshifted >>> rot) | (xorshifted << ((32 - rot) & 31))) >>> 0;
}

/** Uniform integer in [0, n) without modulo bias. */
export function rngInt(rng: RngState, n: number): number {
  const limit = 0x100000000 - (0x100000000 % n);
  for (;;) {
    const v = rngNext(rng);
    if (v < limit) return v % n;
  }
}
