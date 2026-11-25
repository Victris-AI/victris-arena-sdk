"""How an environment turns messages into what a network reads, and its actions back into turns.

An encoder is the part of a bot that learning replaces. `encode` turns an observation (the JSON
the ladder sends) into the network's input, and `decode` turns the network's action into a turn.
`Raw` passes messages through untouched. `Basic` is a small, complete starting point, meant to
be replaced: everything it leaves out is still in the observation.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from gymnasium import spaces

from ._check import check_hello

DIRS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


class MessageSpace(spaces.Space):
    """A JSON message as a dict: an observation the ladder sends, or a turn a bot sends."""

    def __init__(self, seed: int | None = None):
        super().__init__(None, None, seed)

    def contains(self, x: Any) -> bool:
        return isinstance(x, dict)

    def sample(self, *args: Any, **kwargs: Any) -> dict:
        return {}  # an idle turn

    def __repr__(self) -> str:
        return "MessageSpace()"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, MessageSpace)


class Encoder:
    observation_space: spaces.Space
    action_space: spaces.Space

    def encode(self, obs: dict, hello: dict) -> Any:
        raise NotImplementedError

    def decode(self, action: Any, obs: dict, hello: dict) -> dict:
        raise NotImplementedError

    def action_mask(self, obs: dict, hello: dict) -> np.ndarray | None:
        """Which actions the engine would accept now, for masked policies; None if not known."""
        return None


class Raw(Encoder):
    """Observations are the ladder's JSON and actions are turns, exactly as a bot sends them."""

    def __init__(self) -> None:
        self.observation_space = MessageSpace()
        self.action_space = MessageSpace()

    def encode(self, obs: dict, hello: dict) -> dict:
        return obs

    def decode(self, action: dict, obs: dict, hello: dict) -> dict:
        return action


class Basic(Encoder):
    """A grid of the map plus a few numbers in; one of 17 movements times 4 attacks out.

    `grid` has one channel per entry of `CHANNELS`, `size` tiles square (smaller maps are padded).
    `vec` holds the numbers in `FEATURES`, each scaled to about 0..1. An action is
    `movement * 4 + attack`: movement 0 stands still, 1-8 step and 9-16 dash toward `DIRS`;
    attack 0 is none, then the standard shot and frostburst at the enemy (none when it isn't in
    sight) and the repulsor.
    """

    CHANNELS = ("wall", "self", "enemy", "my_shots", "enemy_shots", "danger", "areas", "outside_zone", "pickups")
    FEATURES = (
        "hp", "enemy_seen", "enemy_hp", "cd_move", "cd_dash", "cd_ranged", "cd_frostburst", "cd_repulsor",
        "idle", "state_ticks", "slowed", "power", "enemy_dash_cd", "enemy_idle", "enemy_slowed", "enemy_power",
        "time", "zone_radius", "shrinks_in",
    )
    ATTACKS = (None, "ranged", "frostburst", "repulsor")

    def __init__(self, size: int = 21):
        self.size = size
        self.observation_space = spaces.Dict({
            "grid": spaces.Box(0.0, 1.0, (len(self.CHANNELS), size, size), np.float32),
            "vec": spaces.Box(0.0, 1.0, (len(self.FEATURES),), np.float32),
        })
        self.action_space = spaces.Discrete(17 * len(self.ATTACKS))
        self._walls: dict[str, np.ndarray] = {}
        self._match: object = None
        ys, xs = np.mgrid[0:size, 0:size]
        self._xs, self._ys = xs, ys

    def _wall_grid(self, hello: dict) -> np.ndarray:
        grid = self._walls.get(hello["map_name"])
        if grid is None:
            tiles = hello["map"]
            if len(tiles) > self.size or len(tiles[0]) > self.size:
                raise ValueError(f"map {hello['map_name']} is larger than the encoder's {self.size} tiles")
            grid = np.ones((self.size, self.size), np.float32)  # padding is wall
            for y, row in enumerate(tiles):
                grid[y, : len(row)] = [1.0 if c == "#" else 0.0 for c in row]
            self._walls[hello["map_name"]] = grid
        return grid

    def encode(self, obs: dict, hello: dict) -> dict[str, np.ndarray]:
        if hello.get("match_id") != self._match:  # a match starts: is it on this simulator's rules?
            self._match = hello.get("match_id")
            check_hello(hello)
        grid = np.zeros(self.observation_space["grid"].shape, np.float32)
        c = {name: i for i, name in enumerate(self.CHANNELS)}
        me = obs["self"]

        def put(channel: str, pos: list[int], value: float = 1.0) -> None:
            # Projectiles and blasts can reach past the map's edge; those tiles aren't on the grid.
            x, y = pos
            if 0 <= x < self.size and 0 <= y < self.size:
                grid[c[channel], y, x] = max(grid[c[channel], y, x], value)

        grid[c["wall"]] = self._wall_grid(hello)
        put("self", me["pos"])
        for e in obs["enemies"]:
            put("enemy", e["pos"])
        for p in obs["projectiles"]:
            put("my_shots" if p["owner"] == me["id"] else "enemy_shots", p["pos"])
        for d in obs["danger"]:
            put("danger", d["tile"], 1.0 / (1 + d["tick"] - obs["tick"]))
        for a in obs["areas"]:
            for tile in a["tiles"]:
                put("areas", tile, 1.0 if a["owner"] != me["id"] else 0.5)
        z = obs["zone"]
        dist = np.maximum(np.abs(self._xs - z["center"][0]), np.abs(self._ys - z["center"][1]))
        outside = (dist > z["radius"]).astype(np.float32)
        if z["next_radius"] is not None:  # outside after the coming shrink
            outside = np.maximum(outside, 0.5 * (dist > z["next_radius"]))
        grid[c["outside_zone"]] = outside
        for p in obs["pickups"]:
            if p["ready_in"] == 0:
                put("pickups", p["pos"])

        rules = hello["rules"]
        enemy = obs["enemies"][0] if obs["enemies"] else None
        cd = me["cooldowns"]
        clip = lambda v: min(max(float(v), 0.0), 1.0)  # noqa: E731
        vec = [
            me["hp"] / me["max_hp"],
            1.0 if enemy else 0.0,
            enemy["hp"] / me["max_hp"] if enemy else 0.0,
            *(clip(cd.get(k, 0) / 20) for k in ("move", "dash", "ranged", "frostburst", "repulsor")),
            1.0 if me["state"] == "idle" else 0.0,
            clip(me["state_ticks_left"] / 10),
            clip(me["slow_ticks_left"] / 10),
            1.0 if "power" in me["buffs"] else 0.0,
            clip(enemy["dash_cooldown"] / 20) if enemy else 0.0,
            1.0 if enemy and enemy["state"] == "idle" else 0.0,
            clip(enemy["slow_ticks_left"] / 10) if enemy else 0.0,
            1.0 if enemy and "power" in enemy["buffs"] else 0.0,
            obs["tick"] / rules["max_ticks"],
            clip(z["radius"] / self.size),
            1.0 if z["shrinks_in"] is None else clip(z["shrinks_in"] / 50),
        ]
        return {"grid": grid, "vec": np.asarray(vec, np.float32)}

    def decode(self, action: Any, obs: dict, hello: dict) -> dict:
        movement, attack = divmod(int(action), len(self.ATTACKS))
        turn: dict[str, Any] = {}
        if 1 <= movement <= 8:
            turn["move"] = DIRS[movement - 1]
        elif movement >= 9:
            turn["dash"] = DIRS[movement - 9]
        name = self.ATTACKS[attack]
        if name == "repulsor":
            turn["attack"] = {"name": name}
        elif name and obs["enemies"]:
            turn["attack"] = {"name": name, "target": obs["enemies"][0]["pos"]}
        return turn

    def action_mask(self, obs: dict, hello: dict) -> np.ndarray:
        """Exact for movement, cooldowns and the frostburst's range, which counts from the tile the
        movement ends on. A frostburst also needs line of sight from that tile, which this mask
        doesn't check: without it the engine drops the attack and the movement still happens."""
        me = obs["self"]
        moves = {m["dir"]: m["tile"] for m in obs["moves"]}
        dashes = {d["dir"]: d["tile"] for d in obs["dashes"]}
        ends = [me["pos"], *(moves.get(d) for d in DIRS), *(dashes.get(d) for d in DIRS)]
        ready = lambda name: me["state"] == "idle" and me["cooldowns"].get(name, 0) == 0  # noqa: E731
        enemy = obs["enemies"][0]["pos"] if obs["enemies"] else None
        reach = hello["rules"]["attacks"]["frostburst"]["range"]
        mask = np.zeros((17, len(self.ATTACKS)), np.int8)
        for m, end in enumerate(ends):
            if end is None:
                continue
            in_reach = enemy is not None and max(abs(end[0] - enemy[0]), abs(end[1] - enemy[1])) <= reach
            mask[m] = [True, ready("ranged") and enemy is not None, ready("frostburst") and in_reach, ready("repulsor")]
        return mask.reshape(-1)


def win_loss(obs: dict | None, msg: dict) -> float:
    """The default reward: 1 for a win, -1 for a loss, 0 for a draw and for every tick before the end."""
    if msg.get("type") != "end":
        return 0.0
    return {"win": 1.0, "loss": -1.0}.get(msg["result"], 0.0)


def damage_trade(obs: dict, msg: dict) -> float:
    """`win_loss` at the end, and every tick before it the damage you dealt minus the damage you
    took, as a fraction of your max hp: a denser signal to start learning from."""
    if msg.get("type") == "end":
        return win_loss(obs, msg)
    me = obs["self"]
    dealt = sum(e["damage"] for e in msg["events"] if e["kind"] in ("hit", "wall_slam") and e["attacker"] == me["id"])
    taken = max(0, me["hp"] - msg["self"]["hp"])  # a heal isn't a reward
    return (dealt - taken) / me["max_hp"]
