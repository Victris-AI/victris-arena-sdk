# victris-arena-sim

The simulator for [Victris Arena](https://victrisarena.com), the live, ranked 1v1 arena where you
and your AI agent build battle bots. It is the ladder's own match code in one JavaScript module:
the engine, the protocol's message checks and the match rules, with the shipped rules, maps, the
starter bot and Random built in. One CPU core plays about 100 to 150 games a second, so you can
train and test a bot offline before it plays a rated match.

```bash
npm install victris-arena-sim
```

```js
import { Game, RELEASE } from "victris-arena-sim";
```

It has no dependencies and uses no Node APIs, so it runs in Node 18+ and in browsers.
`victris-arena-sim/script` is the same code as a plain script that sets a global `ArenaSim`, for
engines that don't load modules.

This is release 0.95.0. Each release of the ladder plays on the simulator of the same
version, so keep it current: a policy trained on another release may see other rules.

- [Simulator guide](https://victrisarena.com/guide/simulator): playing games, your own bots and encoders, replays
  as training data.
- [Agent guide](https://victrisarena.com/guide/agents): from zero to a bot on the ladder.
- [Victris Arena SDK](https://github.com/Victris-AI/victris-arena-sdk): the starter bots, the Python
  package (`pip install victris-arena-sim`), Agent Skills and the MCP plugin.

Released under the MIT License by Victris AI.
