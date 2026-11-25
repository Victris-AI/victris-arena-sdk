// Random: sends a random turn every tick, including invalid ones. Useful as a
// fuzzer for validation paths and as the weakest possible opponent.
// The decisions are in policy.ts, which the simulator also runs in-process.
import { runBot } from "../lib/run.ts";
import { random } from "./policy.ts";

runBot(random);
