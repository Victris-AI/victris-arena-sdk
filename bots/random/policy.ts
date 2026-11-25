// Random: sends a random turn every tick, including invalid ones. Useful as a
// fuzzer for validation paths and as the weakest possible opponent.
import { DIRS, type Policy, type Turn } from "../lib/client.ts";

export const random: Policy = {
  version: "random-9",
  decide(obs, ctx): Turn {
    const pick = <T>(xs: T[]): T => xs[Math.floor(ctx.rand() * xs.length)]!;
    const dir = pick(DIRS);
    const [x, y] = obs.self.pos;
    const target: [number, number] = [
      x + Math.floor(ctx.rand() * 11) - 5,
      y + Math.floor(ctx.rand() * 11) - 5,
    ];
    const attack = { name: pick(["ranged", "frostburst", "repulsor"]), target };
    return pick<Turn>([
      {},
      { move: dir },
      { dash: dir },
      { attack },
      { move: dir, attack },
      { dash: dir, attack },
    ]);
  },
};
