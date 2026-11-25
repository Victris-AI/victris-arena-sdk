#!/usr/bin/env node
// Compares two versions of a Victris Arena bot's strategy in the simulator, before you ship one:
// head to head, then each against the bundled opponents on the same seeds, on every map. Prints
// each side's score with a 95% interval, so you can tell a real improvement from luck, and how
// long decide() takes, so you know it fits the ladder's deadline.
//
//   node compare.mjs --candidate ./strategy.ts --baseline ./strategy-v1.ts
//   node compare.mjs --sim ./arena-sim.mjs --candidate ./a.ts --baseline ./b.ts --games 600 --against ts-starter,random
//
// Each strategy module exports decide(observation, match), as the TypeScript starter's
// strategy.ts does: `match` is { id, rules } from the match's hello. Node 22.18 and later load
// .ts files directly when they use only erasable TypeScript (no enums or parameter properties).
// Download the simulator first: curl -O https://victrisarena.com/download/arena-sim.mjs

import { resolve } from "node:path";
import { performance } from "node:perf_hooks";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

const { values: args } = parseArgs({
  options: {
    sim: { type: "string", default: "./arena-sim.mjs" },
    candidate: { type: "string" },
    baseline: { type: "string" },
    games: { type: "string", default: "300" },
    against: { type: "string", default: "ts-starter,random" },
    seed: { type: "string", default: "0" },
  },
});
if (!args.candidate || !args.baseline) {
  console.error("usage: node compare.mjs --candidate <module> --baseline <module> [--games 300]");
  process.exit(2);
}
const load = (path) => import(pathToFileURL(resolve(path)).href);
const sim = await load(args.sim);
const strategies = {
  candidate: (await load(args.candidate)).decide,
  baseline: (await load(args.baseline)).decide,
};
for (const [side, decide] of Object.entries(strategies))
  if (typeof decide !== "function") throw new Error(`${side} module exports no decide()`);

const games = Number(args.games);
const firstSeed = Number(args.seed);
const maps = sim.SHIPPED_MAPS.length;

/** Calls a strategy as the starters do: a bug in it makes that tick idle instead of crashing. */
function player(side) {
  const decide = strategies[side];
  const stats = { calls: 0, ms: 0, maxMs: 0, errors: 0, firstError: null };
  const turn = (observation, match) => {
    const started = performance.now();
    try {
      return decide(observation, match) ?? {};
    } catch (error) {
      stats.errors++;
      stats.firstError ??= error instanceof Error ? error.stack : String(error);
      return {};
    } finally {
      const ms = performance.now() - started;
      stats.calls++;
      stats.ms += ms;
      stats.maxMs = Math.max(stats.maxMs, ms);
    }
  };
  return { side, turn, stats };
}
const matchOf = (hello) => ({ id: hello.match_id, rules: hello.rules });

/** The simulator's opponent object for a strategy, so two of yours can meet. */
function asOpponent(p) {
  return {
    name: p.side,
    version: "local",
    start(hello) {
      const match = matchOf(hello);
      return (observation) => p.turn(observation, match);
    },
  };
}

/** A short fingerprint of a played game's turns, to tell how many games were really different. */
function fingerprint(replay) {
  let h = 2166136261;
  for (const ch of JSON.stringify(replay.ticks)) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return h >>> 0;
}

/**
 * Plays `you` as fighter 1 against `opponent` on one seed. `score` is 1 for a win, 0.5 a draw and
 * 0 a loss; `key` identifies the game, since two bots without randomness replay the same game
 * whenever a seed gives the same map and spawns.
 */
function play(you, opponent, seed, flip = false) {
  const game = new sim.Game({ seed, opponent, name: you.side });
  const match = matchOf(game.hello(1));
  while (!game.over) game.step({ 1: you.turn(game.next(1), match) });
  const result = game.next(1).result;
  const score = result === "win" ? 1 : result === "draw" ? 0.5 : 0;
  return { score: flip ? 1 - score : score, key: `${flip}:${fingerprint(game.replay())}` };
}

/** Wilson score interval for a share of points, at 95%. */
function interval(points, n) {
  const z = 1.96,
    p = points / n,
    centre = (p + (z * z) / (2 * n)) / (1 + (z * z) / n),
    half = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / (1 + (z * z) / n);
  return [Math.max(0, centre - half), Math.min(1, centre + half)];
}
const pct = (x) => `${(100 * x).toFixed(1)}%`;
let repeated = false;
function line(label, games) {
  const scores = games.map((g) => g.score),
    n = scores.length,
    points = scores.reduce((a, b) => a + b, 0),
    [low, high] = interval(points, n),
    wins = scores.filter((s) => s === 1).length,
    draws = scores.filter((s) => s === 0.5).length,
    distinct = new Set(games.map((g) => g.key)).size;
  if (distinct < n / 2) repeated = true;
  return `${label.padEnd(30)} ${pct(points / n).padStart(6)}  [${pct(low)} – ${pct(high)}]  ${wins}W ${draws}D ${n - wins - draws}L  ${distinct} distinct`;
}

const candidate = player("candidate"),
  baseline = player("baseline");
const seeds = Array.from({ length: games }, (_, i) => firstSeed + i);
const started = performance.now();

console.log(
  `Victris Arena simulator ${sim.RELEASE}, ${games} games per line, maps by seed (${maps} maps)\n`,
);

// Head to head: the candidate as fighter 1 against the baseline, then the other way round, on
// the same seeds, so spawns and maps are shared out evenly.
const forward = seeds.map((seed) => play(candidate, asOpponent(baseline), seed));
const reverse = seeds.map((seed) => play(baseline, asOpponent(candidate), seed, true));
const headToHead = [...forward, ...reverse];
console.log(line("candidate vs baseline", headToHead));
for (let m = 0; m < maps; m++) {
  const onMap = headToHead.filter((_, i) => seeds[i % games] % maps === m);
  console.log(line(`  on ${sim.SHIPPED_MAPS[m].name}`, onMap));
}

// Against the bundled opponents, both strategies on the same seeds.
for (const opponent of args.against.split(",").filter(Boolean)) {
  console.log("");
  console.log(
    line(
      `candidate vs ${opponent}`,
      seeds.map((s) => play(candidate, opponent, s)),
    ),
  );
  console.log(
    line(
      `baseline  vs ${opponent}`,
      seeds.map((s) => play(baseline, opponent, s)),
    ),
  );
}

console.log(
  `\ndecide() time (your machine; the ladder allows ${sim.SHIPPED_RULES.limits.tick_ms} ms a tick, network included):`,
);
for (const p of [candidate, baseline]) {
  const { calls, ms, maxMs, errors, firstError } = p.stats;
  console.log(
    `  ${p.side.padEnd(9)} mean ${(ms / calls).toFixed(2)} ms, max ${maxMs.toFixed(1)} ms over ${calls} calls${errors ? `, ${errors} errors (idle ticks)` : ""}`,
  );
  if (firstError)
    console.log(`    first error: ${firstError.split("\n").slice(0, 3).join("\n    ")}`);
}
console.log(`\n${((performance.now() - started) / 1000).toFixed(1)} s`);
if (repeated)
  console.log(
    "\nSome lines replayed the same few games: neither bot uses randomness, so a seed with the same map and spawns gives the same game. Their intervals count repeats as evidence and are too narrow. Judge those lines by their distinct games, add opponents that vary, or give your bot a seeded random tie-break.",
  );
console.log(
  "\nShip the candidate when its head-to-head interval sits above 50% and it doesn't lose ground against the others.",
);
