"""Victris Arena starter bot (Python). Same strategy as bots/ts-starter: every turn has two phases,
movement then attack. Movement dodges what the observation says will hit us, keeps inside the
shrinking zone, grabs nearby pickups, closes in, and searches when the enemy is out of sight; the
attack then fires from wherever the movement ends. Every number comes from hello["rules"], so the
bot keeps working when the ladder retunes them. A turn is a dict with optional "move" (a
direction), "dash" (a direction) and "attack" ({"name": ..., "target": [x, y]}).

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    ARENA_TOKEN=<your token> .venv/bin/python bot.py

(A virtualenv, because many systems refuse a global pip install. The arena CLI's
check-bot, check-protocol and run use a bot directory's .venv automatically.)

Environment: ARENA_URL (default wss://victrisarena.com/bot: a local ladder, or the
ladder this copy was downloaded from), ARENA_TOKEN,
ARENA_VERSION (default v1; every game is rated for it) and ARENA_MATCHES (stop after
this many matches; default: keep playing). It reconnects by itself if the ladder restarts or the
network drops.

Every observation field: /docs/schema/observation.json. Every rule: /docs/rules.
"""
import asyncio
import inspect
import json
import os
import traceback

import websockets

# How close the bot likes to fight: a choice of strategy, not a rule of the game.
FIGHTING_RANGE = 5
# Ticks spent heading for each corner of the patrol while searching, and how far it is from the centre.
PATROL_TICKS = 30
PATROL_RADIUS = 2


def dist(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def step_toward(obs, goal):
    """The step toward goal that ends closest to it. obs["moves"] lists every step the engine
    would accept right now (no walls, no corner cutting, nobody in the way, move off cooldown),
    so there is no legality code to write. Greedy, not a path search."""
    best = None
    for m in obs["moves"]:
        # Chebyshev distance first; straight-line distance breaks ties so we head directly at the goal.
        score = dist(m["tile"], goal) * 1000 + (m["tile"][0] - goal[0]) ** 2 + (m["tile"][1] - goal[1]) ** 2
        if best is None or score < best[0]:
            best = (score, m["dir"])
    return best[1] if best else None


def hit_in(obs, p, first, last):
    """Is tile p hit by an opponent attack between `first` and `last` ticks from now
    (0 = the tick we're replying to)? observation["danger"] lists every tile each visible
    projectile and area will hit, and on which tick, so there's no geometry to do."""
    return any(
        list(d["tile"]) == list(p) and first <= d["tick"] - obs["tick"] <= last
        for d in obs["danger"]
    )


def in_safe_zone(obs, p):
    """Inside the zone, and inside the next one too once a shrink is announced: outside it hurts every tick."""
    zone = obs["zone"]
    radius = zone["radius"] if zone["shrinks_in"] is None else zone["next_radius"]
    return dist(p, zone["center"]) <= radius


def dodge(obs):
    """Get off a tile that's about to be hit: step somewhere safe, or dash (invulnerable on its tick)."""
    # Prefer a tile that stays safe for a few ticks, then one that is merely safe this tick.
    for last in (2, 0):
        for m in obs["moves"]:
            if not hit_in(obs, m["tile"], 0, last) and in_safe_zone(obs, m["tile"]):
                return {"move": m["dir"]}
    # obs["dashes"] has each dash's landing tile (shorter than usual when a wall stops it).
    # A dash is invulnerable only on its own tick: land somewhere that stays safe, and in the zone.
    for d in obs["dashes"]:
        if not hit_in(obs, d["tile"], 1, 2) and in_safe_zone(obs, d["tile"]):
            return {"dash": d["dir"]}
    return None


def search_goal(obs):
    """Where to go while the enemy is out of sight: around the zone's centre, the ground every fight
    ends on, one corner of a small square at a time. Waiting in one spot is how two bots spend a
    match either side of a pillar; chasing where the enemy was walks into its range."""
    r = min(PATROL_RADIUS, max(1, obs["zone"]["radius"] // 2))
    cx, cy = obs["zone"]["center"]
    corners = [[cx - r, cy - r], [cx + r, cy - r], [cx + r, cy + r], [cx - r, cy + r]]
    return corners[(obs["tick"] // PATROL_TICKS) % len(corners)]


def movement(obs, match):
    """Movement phase: dodge, stay in the zone, grab a nearby pickup, then close in on the enemy or look for it."""
    me = obs["self"]
    # Something in flight (a shot or a frostburst area) will hit our tile within 2 ticks.
    if hit_in(obs, me["pos"], 0, 2):
        react = dodge(obs)
        if react:
            return react
    # The zone comes before the enemy: standing outside it costs hp every tick.
    if not in_safe_zone(obs, me["pos"]):
        d = step_toward(obs, obs["zone"]["center"])
        return {"move": d} if d else {}
    enemy = obs["enemies"][0] if obs["enemies"] else None
    # Pickups are taken just by stepping onto them. Grab a stocked one that's close and inside the
    # zone, unless the enemy is nearer to it, and skip health we'd mostly waste.
    heal = match["rules"].get("pickups", {}).get("health", {}).get("amount", 0)
    pickups = [
        p for p in obs["pickups"]
        if p["ready_in"] == 0 and in_safe_zone(obs, p["pos"])
        and not (p["kind"] == "health" and me["hp"] > me["max_hp"] - heal / 2)
        and (enemy is None or dist(enemy["pos"], p["pos"]) > dist(me["pos"], p["pos"]))
    ]
    pickups.sort(key=lambda p: dist(me["pos"], p["pos"]))
    if pickups and dist(me["pos"], pickups[0]["pos"]) <= (2 if enemy else 6):
        d = step_toward(obs, pickups[0]["pos"])
        if d:
            return {"move": d}
    if enemy is None:
        d = step_toward(obs, search_goal(obs))
        return {"move": d} if d else {}
    if dist(me["pos"], enemy["pos"]) > FIGHTING_RANGE:
        d = step_toward(obs, enemy["pos"])
        if d:
            return {"move": d}
    return {}


def end_tile(obs, turn):
    """Where the movement ends: the step's or dash's landing tile, or where we already stand."""
    options = obs["moves"] if "move" in turn else obs["dashes"] if "dash" in turn else []
    wanted = turn.get("move") or turn.get("dash")
    return next((o["tile"] for o in options if o["dir"] == wanted), obs["self"]["pos"])


def attack(obs, match, origin):
    """Attack phase: fires from origin, the tile the movement ends on. Each weapon has its own cooldown."""
    enemy = obs["enemies"][0] if obs["enemies"] else None
    if enemy is None:
        return None
    ready = lambda name: obs["self"]["cooldowns"][name] == 0
    distance = dist(origin, enemy["pos"])
    # The repulsor hits every tile around you and needs no target; the other attacks aim at one.
    if distance == 1 and ready("repulsor"):
        return {"name": "repulsor"}
    # Frostburst explodes after a fuse, so it only catches an enemy that can't dash out: cast it while
    # the enemy's dash is on cooldown. It needs its target in range and in sight from where we end up;
    # we only know sight from where we stand (enemies lists who we can see now), so cast it standing still.
    still = list(origin) == list(obs["self"]["pos"])
    frost_range = match["rules"]["attacks"]["frostburst"]["range"]
    if still and enemy["dash_cooldown"] > 0 and distance <= frost_range and ready("frostburst") and not enemy["slow_ticks_left"]:
        return {"name": "frostburst", "target": enemy["pos"]}
    if ready("ranged"):
        return {"name": "ranged", "target": enemy["pos"]}
    return None


def decide(obs, match):
    # Stunned or recovering from a dash: nothing to decide meanwhile.
    if obs["self"]["state"] != "idle":
        return {}
    turn = movement(obs, match)
    fire = attack(obs, match, end_tile(obs, turn))
    if fire:
        turn["attack"] = fire
    return turn


def reply(obs, match):
    """The reply to an observation. A bug in decide costs one idle tick, not the match."""
    turn = {}
    try:
        if match:
            turn = decide(obs, match)
    except Exception:
        print(f"decide failed on tick {obs['tick']}:", flush=True)
        traceback.print_exc()
    return json.dumps({"tick": obs["tick"], **turn})


# Errors that reconnecting can't fix: the bot stops.
FATAL = {"missing_authorization", "invalid_token", "suspended", "banned", "retired", "account_banned", "account_required", "human_only", "replaced", "unknown_ladder", "ladder_closed", "enrollment_required", "wrong_ladder", "membership_revoked", "ladder_unavailable"}


async def play(url, headers, queue, state):
    """One connection: queue, then answer the ladder until it closes. Returns True when the bot is done."""
    # Probe the transport even while queued; JSON messages can legitimately be silent.
    keepalive = {"open_timeout": 10, "ping_interval": 20, "ping_timeout": 20, "close_timeout": 5}
    # The header keyword changed in websockets 14; older versions fail only when awaited.
    header_key = "additional_headers" if "additional_headers" in inspect.signature(websockets.connect).parameters else "extra_headers"
    conn = websockets.connect(url, **{header_key: headers}, **keepalive)
    async with conn as ws:
        await ws.send(queue)
        async for raw in ws:
            msg = json.loads(raw)
            kind = msg.get("type")
            if kind != "error":
                state["delay"] = 1  # a working connection resets the backoff
            if kind == "server_draining":
                print(f"server restarting: matchmaking paused; drain deadline {msg['drain_deadline']}. Keep playing until close, then reconnect.", flush=True)
            elif kind == "hello":
                # The same match_id resumes a match; keep any state we retained.
                if state["match"] is None or state["match"]["id"] != msg["match_id"]:
                    state["match"] = {"id": msg["match_id"], "rules": msg["rules"]}
                await ws.send(json.dumps({"type": "ready"}))
            elif kind == "observation":
                await ws.send(reply(msg, state["match"]))
            elif kind == "end":
                print(f"{msg['result']} ({msg['reason']}) watch: {msg.get('watch_url', '')}", flush=True)
                state["match"] = None
                state["played"] += 1
                if state["played"] >= state["max_matches"]:  # ARENA_MATCHES reached
                    return True
                await ws.send(queue)
            elif kind == "error":
                print(f"{msg['code']}: {msg['message']}", flush=True)
                if msg["code"] in FATAL:
                    return True
    return False


async def main():
    url = os.environ.get("ARENA_URL", "wss://victrisarena.com/bot")
    token = os.environ.get("ARENA_TOKEN", "dev")
    headers = {"Authorization": f"Bearer {token}"}
    version = os.environ.get("ARENA_VERSION", "v1")
    # Every game is rated for this version; create the next numbered version each time the bot changes.
    q = {"type": "queue", "version": version}
    if os.environ.get("ARENA_LADDER"):
        q["ladder_id"] = os.environ["ARENA_LADDER"]
    state = {"played": 0, "max_matches": int(os.environ.get("ARENA_MATCHES", "0")) or float("inf"), "delay": 1, "match": None}
    # The connection survives ladder restarts and network drops: reconnect with backoff (1 s,
    # doubling to 30 s) and queue again. Mid-match, the ladder sends hello then the current
    # observation (and answers the queue with a harmless already_queued). Keep state for the same match_id.
    while True:
        try:
            if await play(url, headers, json.dumps(q), state):
                return
        except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as e:
            print(f"connection lost: {e}", flush=True)
        print(f"reconnecting in {state['delay']} s", flush=True)
        await asyncio.sleep(state["delay"])
        state["delay"] = min(state["delay"] * 2, 30)


if __name__ == "__main__":
    asyncio.run(main())
