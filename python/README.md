# arena-sim

Victris Arena's simulator for Python: the ladder's own match code (`arena-sim.js`, built from
`packages/sim`) run in embedded V8 through [mini-racer](https://pypi.org/project/mini-racer/),
with Gymnasium and PettingZoo environments. No Node.js needed.

- `Simulator(num_games)`: many games stepped in one call, any mix of Random and starter opponents and self-play.
- `ArenaEnv`, `ArenaVectorEnv`: Gymnasium environments, one match an episode against Random or the starter bot,
  or (vector) against your own policies and scripted bots.
- `ArenaSelfPlayEnv`: batched self-play, both fighters of every match yours.
- `FastVectorEnv`, `FastSelfPlayEnv`: the same matches encoded inside the simulator and read in
  place (no JSON), about 7 times faster a process, and split over worker processes with `workers=N`.
  `scripts=` loads JavaScript that registers your own bots (opponents, teachers) and encoders;
  `ScriptedOpponent`s (bots written in Python) play and teach there too.
- `ScriptEncoder`: an encoder from the simulator in a live Python bot; `check_encoder` checks one
  reads the ladder's JSON as it reads the batch.
- `arena_sim.sb3.ArenaVecEnv`: the batched environments for Stable-Baselines3 and sb3-contrib's
  `MaskablePPO` (the `sb3` extra).
- `python -m arena_sim.examples.train_ppo`: a complete PPO training run (curriculum against
  Random, then the starter bot) to start from.
- `python -m arena_sim.examples.train_ppo_gpu`: the same curriculum in plain PyTorch, built for a GPU
  (the fast environments, byte grids, rollouts on the device, CUDA graphs), training against
  Random, then `ts-starter` (the `torch` extra, or a CUDA build of torch).
- `download_replays`, `replay_trajectories`, `replay_dataset`: ladder games as training data, each
  fighter's observations and turns rebuilt from the replay, or encoded straight into arrays.
- `python -m arena_sim.examples.imitate` and `python -m arena_sim.examples.league`: imitation of the
  ladder's strongest bots, and PPO against a pool of bots and copies of yourself.
- `arena_sim.multiagent.ArenaParallelEnv`: PettingZoo self-play (the `pettingzoo` extra).
- `Raw` passes the ladder's JSON through; `Basic` is a reference encoder to start from.

Players install the wheel the ladder serves (`GET /api` → `simulator.python`); see
`docs/SIMULATOR.md` (`/docs/simulator` on a ladder). `python -m arena_sim check <ladder URL>` says
whether an installed copy is the release that ladder runs. Without contacting anyone, it also
warns (`OutdatedSimulatorWarning`) when a live match's hello (`Basic`, `ScriptEncoder`,
`check_hello`) or downloaded replays were played on other rules.
`python -m arena_sim changelog` prints the release notes since this release, and
`python -m arena_sim source <dir>` the TypeScript it was built from (the wheel carries
`arena-sim.js.map` and `CHANGELOG.md`). The package's version is the game's `RELEASE`, read from
`arena-sim.js` when the wheel is built.

Developing: `bun run build:py` builds the wheel into `dist/`, `bun run test:py` runs the tests
(both need [uv](https://docs.astral.sh/uv/)).
