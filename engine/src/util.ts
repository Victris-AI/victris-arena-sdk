// Integer helpers. Game logic must never produce fractional numbers; every
// division in the engine goes through idiv so the intent is explicit.

export function idiv(a: number, b: number): number {
  return Math.floor(a / b);
}

/**
 * A deep copy of plain data, which is all match state is. The platform's structured clone would do,
 * but it is a host API: the engine also runs in bare JavaScript engines (the simulator in embedded V8).
 */
export function clone<T>(v: T): T {
  if (Array.isArray(v)) return v.map(clone) as T;
  if (v === null || typeof v !== "object") return v;
  const out: Record<string, unknown> = {};
  for (const k of Object.keys(v)) out[k] = clone((v as Record<string, unknown>)[k]);
  return out as T;
}

/**
 * Deterministic JSON: object keys sorted, no whitespace. The ladder hashes every tick's state
 * with it, so it builds the string directly; its output is what replay hashes are checked against.
 */
export function canonicalJson(v: unknown): string {
  if (typeof v === "number") return Number.isFinite(v) ? String(v) : "null";
  if (v === null || typeof v !== "object") return JSON.stringify(v);
  let s: string;
  if (Array.isArray(v)) {
    s = "[";
    // join() wrote a missing element (undefined) as nothing
    for (let i = 0; i < v.length; i++) s += (i ? "," : "") + (canonicalJson(v[i]) ?? "");
    return s + "]";
  }
  const o = v as Record<string, unknown>;
  const keys = Object.keys(o);
  if (!isSorted(keys)) keys.sort();
  s = "{";
  for (const k of keys) {
    if (o[k] === undefined) continue;
    let q = quotedKeys.get(k);
    if (q === undefined) {
      q = `${JSON.stringify(k)}:`;
      if (quotedKeys.size < 1000) quotedKeys.set(k, q);
    }
    s += (s.length > 1 ? "," : "") + q + canonicalJson(o[k]);
  }
  return s + "}";
}

// State objects reuse a few dozen keys, so their quoted forms are worth keeping (bounded: past
// the limit, new keys are quoted each time).
const quotedKeys = new Map<string, string>();
const isSorted = (keys: string[]) => keys.every((k, i) => i === 0 || keys[i - 1]! < k);

/** cyrb53: fast 53-bit string hash, identical in Node and browsers. Not cryptographic. */
export function hashString(str: string, seed = 0): string {
  let h1 = 0xdeadbeef ^ seed;
  let h2 = 0x41c6ce57 ^ seed;
  for (let i = 0; i < str.length; i++) {
    const ch = str.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(16).padStart(14, "0");
}

export function hashValue(v: unknown): string {
  return hashString(canonicalJson(v));
}
