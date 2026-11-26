// Frame data and counters: one page, generated from the rules table so its numbers
// can't drift. Served at /docs/frame-data and checked in as docs/FRAME_DATA.md
// (regenerate with `bun run frame-data`).

import type { Attack, Rules } from "./rules.ts";

export interface FrameRow {
  attack: string;
  damage: string;
  cooldown: number;
  /** observations that show the threat before it lands on a tile at each sample distance; null = out of range */
  warning: (number | null)[];
}

/** Distances the warning column is given for. */
export const WARNING_DISTANCES = [1, 2, 5, 8];

/** Ticks from the attack tick until a tile `d` away is hit. */
function flightTicks(a: Attack, d: number): number | null {
  if (a.range !== undefined && d > a.range) return null;
  if (a.kind === "projectile") return Math.ceil(d / a.speed) - 1;
  if (a.kind === "area") return a.fuse;
  return 0;
}

export function frameData(rules: Rules): FrameRow[] {
  return Object.entries(rules.attacks).map(([name, a]) => ({
    attack: name,
    damage: a.kind === "burst" ? `${a.damage}, push ${a.push}` : `${a.damage}`,
    cooldown: a.cooldown,
    warning: WARNING_DISTANCES.map((d) => flightTicks(a, d)),
  }));
}

/** What each attack threatens and its cheapest answer, by attack name. */
function counters(rules: Rules): Record<string, { threat: string; counter: string }> {
  const at = rules.attacks;
  const side = (r: number) => `${2 * r + 1}×${2 * r + 1}`;
  const fb = at.frostburst?.kind === "area" ? at.frostburst : undefined;
  return {
    ranged: {
      threat: `A line at any angle, ${at.ranged?.kind === "projectile" ? at.ranged.speed : "?"} tiles a tick, that bounces once off a flat wall (a corner stops it), so it reaches angles a straight shot can't. The cheapest poke, on the shortest cooldown. Within ${at.ranged?.kind === "projectile" ? at.ranged.speed : "?"} tiles it lands the tick it is sent.`,
      counter:
        "At range, step off its path while it flies, reading the path after the bounce from `danger`. Up close there's no warning: don't stand still next to a shooter whose shot is off cooldown. Being out of the shooter's line of sight is not enough.",
    },
    frostburst: {
      threat: `A ${side(fb?.radius ?? 1)} area (walls shield tiles behind them) on a fixed tick, cast instantly on a tile you can see. Until it goes off, moving from inside it takes ${fb?.slow ?? "?"} ticks longer per step.`,
      counter:
        "Walk out of `areas[].tiles` before `ticks_left` reaches 1, starting early: each step inside costs extra. Don't plan to cross it. Dash on the last tick if you're boxed in.",
    },
    repulsor: {
      threat: `All eight tiles around the attacker (no aim), landing the tick it is sent: ${at.repulsor?.damage ?? "?"} damage and a shove ${at.repulsor?.kind === "burst" ? at.repulsor.push : "?"} tiles straight away. A wall stops the shove with a slam (${rules.knockback.wall_slam_damage} more damage, stunned ${rules.knockback.wall_slam_stun} ticks); the zone edge keeps hurting.`,
      counter:
        "Don't stand next to an opponent whose repulsor is up, least of all with a wall or the zone edge behind you: a slam stuns you for 3 ticks, long enough for a guaranteed follow-up shot. Its cooldown is long, but spending it leaves their other weapons ready.",
    },
  };
}

export function frameDataMarkdown(rules: Rules): string {
  const rows = frameData(rules);
  const s = rules.stats;
  const mc = s.move_cooldown;
  const dash = rules.dash;
  const table = rows
    .map(
      (r) =>
        `| \`${r.attack}\` | ${r.damage} | ${r.cooldown} | ${r.warning.map((w) => (w === null ? "–" : w)).join(" / ")} |`,
    )
    .join("\n");
  const text = counters(rules);
  const counterRows = rows
    .map((r) => {
      const c = text[r.attack];
      return `| \`${r.attack}\` | ${c?.threat ?? ""} | ${c?.counter ?? ""} |`;
    })
    .join("\n");
  return `# Frame data and counters (rules v${rules.version})

Generated from the rules table, so these numbers match \`hello.rules\`. Times are in ticks. Tick T is the tick you send the attack.

## Frame data

| attack | damage | cooldown | warning at ${WARNING_DISTANCES.join(" / ")} tiles |
| --- | --- | --- | --- |
${table}

- **Every attack fires the tick you send it**, after movement: projectiles launch and fly, frostburst creates its area and starts its fuse, repulsors shove. Nothing is telegraphed before it's in the world, so a target that stepped away that same tick escapes, and one that stood still doesn't.
- **No recovery**: an attacker can step, dash or fire on the very next tick, and can even move in the same tick it fires. There is no punish window after an attack; count its cooldown instead.
- **cooldown**: each attack has its own. The same attack can start again on tick T + cooldown; the others are unaffected, so a fighter can fire a different weapon on the very next tick (one attack per tick). Opponents' cooldowns are hidden, but every attack is an \`attack\` event naming the weapon, so you can count each one from the last time you saw it.
- **warning**: how many observations show the threat (in \`danger\`) before it hits a tile at that distance. 0 means it lands the tick it's sent: no warning, only the knowledge that the shooter could fire. "–" means out of range.

## Counters

Every threat, with its exact tiles and tick, is in \`observation.danger\`. The cheapest answer is usually to be somewhere else on that tick.

| attack | what it threatens | cheapest counter |
| --- | --- | --- |
${counterRows}

## Your defensive tools

| tool | cooldown | notes |
| --- | --- | --- |
| step | ${mc} ticks, in any of 8 directions | Your move must be off cooldown on the impact tick. Movement resolves before attacks, so stepping out on that tick still dodges. |
| dash | ${dash.cooldown} ticks; ${dash.recovery} tick of recovery | Moves ${dash.distance} tiles and makes you invulnerable for that tick. Your landing tile must be safe on the following ticks. It's your only escape once your move is on cooldown, so don't spend it on travel. An opponent's is in \`enemies[].dash_cooldown\`: while it's above 0, they can't dash out of a well-placed frostburst. |
| cover | free | Walls stop shots and shield blast tiles. If a wall blocks the line of sight between you and a shooter, a shot can still bank off another wall to reach you, and a frostburst can be cast on a tile beside you. |

## Reading \`observation.danger\`

Each entry is one tile an opponent attack will hit on one tick: \`{"tile": [x, y], "tick": 213, "attack": "ranged", "owner": 2, "damage": 12, "source": "projectile"}\`.

- An entry whose \`tick\` equals the observation's \`tick\` lands during the tick you are replying to, after movement. Don't end this tick's move on that tile.
- Everything listed is already in the world (\`source\` is \`projectile\` or \`area\`), so it's certain. An attack sent this tick isn't listed until the next observation.
- \`damage\` is base damage, before the attacker's power buff.
- Only what you can see is listed. A shot fired from the fog appears once the projectile enters your sight.
`;
}
