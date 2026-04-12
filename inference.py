import os, json
from collections import deque, defaultdict

_REQUIRED = ["API_BASE_URL", "HF_TOKEN"]
_missing = [v for v in _REQUIRED if not os.environ.get(v)]
if _missing:
    raise EnvironmentError(f"Missing required env vars: {', '.join(_missing)}")

API_BASE_URL = os.environ["API_BASE_URL"]
MODEL_NAME   = os.getenv("MODEL_NAME", "gemini-2.5-flash")
HF_TOKEN     = os.environ["HF_TOKEN"]

from openai import OpenAI
from warehouse_env.env import WarehouseEnv
from warehouse_env.models import WarehouseAction, RobotAction
from warehouse_env.graders import GRADER_REGISTRY
from warehouse_env.tasks import TASK_REGISTRY

client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

# Collision avoidance is the #1 priority — spelled out before anything else
PROMPT_TEMPLATE = (
    "You are a warehouse robot controller. Respond ONLY with a JSON array.\n\n"
    ">>> COLLISION AVOIDANCE — TOP PRIORITY <<<\n"
    "- Two robots entering the same cell = permanent score penalty.\n"
    "- Each robot's instruction below lists AVOID cells (other robots). NEVER move there.\n"
    "- If your Suggested action leads into an AVOID cell, choose 'wait' or a perpendicular move.\n"
    "- Never send two robots to the same destination in the same step.\n\n"
    "CURRENT STATE:\n{description}\n\n"
    "ORDERS:\n{order_info}\n\n"
    "PER-ROBOT INSTRUCTIONS:\n{robot_info}\n\n"
    "MOVEMENT RULES:\n"
    "- [■S■] shelf = WALL, robots CANNOT enter. Stand adjacent, then pick.\n"
    "- [XXX] blocked = WALL, robots CANNOT enter.\n"
    "- [_P_] packing station = walkable, robots CAN enter, then drop.\n"
    "- pick: valid when Manhattan distance to shelf ≤ 1\n"
    "- drop: valid when Manhattan distance to packing station ≤ 1\n"
    "- Each active robot MUST appear EXACTLY ONCE in your response.\n\n"
    'Return JSON array only: [{{"robot_id": <int>, "action_type": "<move_up|move_down|move_left|move_right|pick|drop|wait>"}}]\n'
    "No markdown, no explanation.\n\nActions JSON:\n"
)

# ─── Deadlock tracking ───────────────────────────────────────────────────────

# Per-robot position history (last 5 steps) — reset at each task start
_robot_history: dict[int, deque] = defaultdict(lambda: deque(maxlen=5))


def _reset_history() -> None:
    _robot_history.clear()


def _update_history(obs) -> None:
    """Record each active robot's position after a step."""
    for r in obs.robots:
        if r.is_active:
            _robot_history[r.id].append((r.row, r.col))


def _is_stuck(robot_id: int, current_pos: tuple, steps: int = 3) -> bool:
    """True if robot has been at the same cell for `steps` consecutive steps."""
    hist = _robot_history.get(robot_id)
    if not hist or len(hist) < steps:
        return False
    return all(p == current_pos for p in list(hist)[-steps:])


# ─── Grid-aware pathfinding helpers ─────────────────────────────────────────

def _cell_passable(grid: list[list[str]], r: int, c: int, self_label: str = "") -> bool:
    """True if a robot can move into (r,c): in-bounds, not S/X, not another robot."""
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if r < 0 or r >= rows or c < 0 or c >= cols:
        return False
    cell = grid[r][c]
    if cell in ("S", "X"):
        return False
    if cell.startswith("R") and cell != self_label:
        return False  # occupied by a different robot
    return True  # "." or "P" or self's own cell


def _suggest_move(
    robot_r: int, robot_c: int,
    target_r: int, target_c: int,
    grid: list[list[str]],
    self_label: str,
    stuck: bool = False,
) -> str:
    """Return the best 1-step action toward (target_r, target_c).

    Avoids walls, blocked cells, and other robots via grid inspection.
    If stuck (same cell 3+ steps), tries perpendicular moves first to escape.
    """
    moves = [
        ("move_up",    robot_r - 1, robot_c),
        ("move_down",  robot_r + 1, robot_c),
        ("move_left",  robot_r,     robot_c - 1),
        ("move_right", robot_r,     robot_c + 1),
    ]
    # Sort by resulting Manhattan distance to target (closest first)
    moves.sort(key=lambda m: abs(m[1] - target_r) + abs(m[2] - target_c))

    if stuck:
        # Try lateral/perpendicular moves first to break the deadlock
        current_dist = abs(robot_r - target_r) + abs(robot_c - target_c)
        lateral = [m for m in moves
                   if abs(m[1] - target_r) + abs(m[2] - target_c) >= current_dist]
        forward = [m for m in moves
                   if abs(m[1] - target_r) + abs(m[2] - target_c) < current_dist]
        moves = lateral + forward

    for action, nr, nc in moves:
        if _cell_passable(grid, nr, nc, self_label):
            return action

    return "wait"  # completely boxed in


def _nearest_passable_adjacent(
    robot_r: int, robot_c: int,
    target_r: int, target_c: int,
    grid: list[list[str]],
    self_label: str,
) -> tuple[int, int]:
    """Adjacent cell to target that is passable and closest to robot."""
    candidates = [
        (target_r - 1, target_c),
        (target_r + 1, target_c),
        (target_r,     target_c - 1),
        (target_r,     target_c + 1),
    ]
    passable = [p for p in candidates if _cell_passable(grid, p[0], p[1], self_label)]
    pool = passable if passable else candidates  # fallback: ignore passability
    return min(pool, key=lambda p: abs(p[0] - robot_r) + abs(p[1] - robot_c))


# ─── Logging ────────────────────────────────────────────────────────────────

def log_print(msg: str) -> None:
    print(msg, flush=True)
    with open("simulation.log", "a", encoding="utf-8") as f:
        f.write(msg + "\n")


# ─── Grid rendering ─────────────────────────────────────────────────────────

def render_grid(obs, action_str: str = "", reward: float = 0.0) -> None:
    os.system("cls" if os.name == "nt" else "clear")
    lines = []

    sep = "═" * (obs.max_steps // 5 + 10)
    lines.append(sep)
    lines.append(f"  Task: {obs.task_id}   Step: {obs.step_count}/{obs.max_steps}")
    lines.append(sep)

    carrying = {r.id for r in obs.robots if r.carrying_item}

    for row in obs.grid:
        line_parts = []
        for cell in row:
            if cell == ".":
                line_parts.append("[ . ]")
            elif cell == "S":
                line_parts.append("[■S■]")
            elif cell == "P":
                line_parts.append("[_P_]")
            elif cell == "X":
                line_parts.append("[XXX]")
            else:
                try:
                    rid = int(cell[1:])
                    marker = f"{cell}*" if rid in carrying else f"{cell} "
                    line_parts.append(f"[{marker:^3}]")
                except (ValueError, IndexError):
                    line_parts.append(f"[{cell:^3}]")
        lines.append("".join(line_parts))

    lines.append("─" * len(lines[-1]))

    delivered  = sum(1 for o in obs.order_queue if o["status"] == "delivered")
    in_transit = sum(1 for o in obs.order_queue if o["status"] == "picked")
    pending    = sum(1 for o in obs.order_queue if o["status"] == "pending")
    total      = len(obs.order_queue)
    lines.append(
        f"  Orders: {delivered}/{total} done  |  {in_transit} in-transit  |  {pending} pending"
    )

    robot_parts = []
    for r in obs.robots:
        if not r.is_active:
            robot_parts.append(f"R{r.id}:BROKEN")
        elif r.carrying_item:
            robot_parts.append(f"R{r.id}:CARRY({r.assigned_order_id})*")
        elif r.assigned_order_id:
            robot_parts.append(f"R{r.id}:→{r.assigned_order_id}")
        else:
            robot_parts.append(f"R{r.id}:idle")
    lines.append("  " + "  ".join(robot_parts))

    if action_str:
        lines.append(f"  Action : {action_str}")
    if reward != 0.0:
        sign = "+" if reward > 0 else ""
        lines.append(f"  Reward : {sign}{reward:.2f}")

    out = "\n".join(lines)
    print(out, flush=True)
    with open("simulation.log", "a", encoding="utf-8") as f:
        f.write(out + "\n\n")


# ─── Prompt helpers ──────────────────────────────────────────────────────────

def _build_order_info(obs) -> str:
    lines = []
    for o in obs.order_queue:
        if o["status"] == "delivered":
            continue
        sr, sc = o["shelf_pos"]
        pr, pc = o["packing_pos"]
        who = f" [Robot {o['assigned_robot_id']}]" if o.get("assigned_robot_id") is not None else ""
        lines.append(
            f"  {o['order_id']} ({o['status']}){who}: "
            f"shelf(WALL) at ({sr},{sc}) → packing station at ({pr},{pc})"
        )
    return "\n".join(lines) if lines else "  All orders delivered!"


def _build_robot_info(obs) -> str:
    """Per-robot instructions with:
    - Explicit list of OTHER robots' cells to avoid
    - Grid-aware suggested next action
    - Deadlock warning + escape hint when stuck 3+ steps
    """
    grid = obs.grid

    # Current positions of all active robots
    active_positions: dict[int, tuple[int, int]] = {
        r.id: (r.row, r.col) for r in obs.robots if r.is_active
    }

    # Round-robin: distribute unassigned pending orders to idle robots
    unassigned_orders = [
        o for o in obs.order_queue
        if o["status"] == "pending" and o.get("assigned_robot_id") is None
    ]
    idle_robots = [r for r in obs.robots if r.is_active and not r.assigned_order_id]
    idle_to_order: dict[int, dict] = {}
    for i, robot in enumerate(idle_robots):
        if i < len(unassigned_orders):
            idle_to_order[robot.id] = unassigned_orders[i]

    lines = []
    for r in obs.robots:
        if not r.is_active:
            lines.append(f"  Robot {r.id}: BROKEN DOWN — omit from response")
            continue

        self_label = f"R{r.id}"

        # Build the avoid-cells string: all OTHER active robots' positions
        others = [
            f"({row},{col})[R{rid}]"
            for rid, (row, col) in active_positions.items()
            if rid != r.id
        ]
        avoid_str = ", ".join(others) if others else "none"

        # Deadlock detection
        stuck = _is_stuck(r.id, (r.row, r.col), steps=3)
        stuck_note = " *** STUCK 3+ steps — MUST take a DIFFERENT direction! ***" if stuck else ""

        # Build the task-specific instruction + suggested move
        if r.assigned_order_id:
            order = next(
                (o for o in obs.order_queue if o["order_id"] == r.assigned_order_id), None
            )
            if order:
                if r.carrying_item:
                    pr, pc = order["packing_pos"]
                    if abs(r.row - pr) + abs(r.col - pc) <= 1:
                        suggested = "drop"
                        task_line = (
                            f"CARRYING {r.assigned_order_id} — adjacent to "
                            f"packing station ({pr},{pc}). Suggested: 'drop' NOW."
                        )
                    else:
                        adj_r, adj_c = _nearest_passable_adjacent(
                            r.row, r.col, pr, pc, grid, self_label
                        )
                        suggested = _suggest_move(
                            r.row, r.col, adj_r, adj_c, grid, self_label, stuck
                        )
                        task_line = (
                            f"CARRYING {r.assigned_order_id} → target ({adj_r},{adj_c}) "
                            f"[adjacent to packing station ({pr},{pc})], then drop. "
                            f"Suggested: '{suggested}'"
                        )
                else:
                    sr, sc = order["shelf_pos"]
                    if abs(r.row - sr) + abs(r.col - sc) <= 1:
                        suggested = "pick"
                        task_line = (
                            f"NEXT TO shelf ({sr},{sc}) for {r.assigned_order_id}. "
                            f"Suggested: 'pick' NOW."
                        )
                    else:
                        adj_r, adj_c = _nearest_passable_adjacent(
                            r.row, r.col, sr, sc, grid, self_label
                        )
                        suggested = _suggest_move(
                            r.row, r.col, adj_r, adj_c, grid, self_label, stuck
                        )
                        task_line = (
                            f"target ({adj_r},{adj_c}) [adjacent to shelf WALL ({sr},{sc})] "
                            f"for {r.assigned_order_id}. Do NOT enter ({sr},{sc}). "
                            f"Suggested: '{suggested}'"
                        )
            else:
                task_line = "order not found — action='wait'."
                suggested = "wait"
        else:
            order = idle_to_order.get(r.id)
            if order:
                sr, sc = order["shelf_pos"]
                if abs(r.row - sr) + abs(r.col - sc) <= 1:
                    suggested = "pick"
                    task_line = (
                        f"NEXT TO shelf ({sr},{sc}) for {order['order_id']}. "
                        f"Suggested: 'pick' NOW."
                    )
                else:
                    adj_r, adj_c = _nearest_passable_adjacent(
                        r.row, r.col, sr, sc, grid, self_label
                    )
                    suggested = _suggest_move(
                        r.row, r.col, adj_r, adj_c, grid, self_label, stuck
                    )
                    task_line = (
                        f"IDLE → target ({adj_r},{adj_c}) [adjacent to shelf WALL ({sr},{sc})] "
                        f"for {order['order_id']}. Do NOT enter ({sr},{sc}). "
                        f"Suggested: '{suggested}'"
                    )
            else:
                task_line = "IDLE — all orders handled. Suggested: 'wait'."
                suggested = "wait"

        lines.append(
            f"  Robot {r.id} at ({r.row},{r.col}){stuck_note}\n"
            f"    AVOID (other robots): {avoid_str}\n"
            f"    {task_line}"
        )

    return "\n".join(lines)


# ─── LLM call ────────────────────────────────────────────────────────────────

def get_actions(obs, active_robot_ids: list[int]) -> tuple[WarehouseAction, str | None]:
    """Call LLM once for all active robots. Returns (action, error_or_None)."""
    prompt = PROMPT_TEMPLATE.format(
        description=obs.description,
        order_info=_build_order_info(obs),
        robot_info=_build_robot_info(obs),
    )
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        text = response.choices[0].message.content or ""

        # Extract JSON array
        start = text.find("[")
        end   = text.rfind("]") + 1
        if start != -1 and end > start:
            parsed = json.loads(text[start:end])
        else:
            start_d = text.find("{")
            end_d   = text.rfind("}") + 1
            if start_d != -1 and end_d > start_d:
                parsed = [json.loads(text[start_d:end_d])]
            else:
                print(f"DEBUG LLM: {text[:300]}")
                raise ValueError("No JSON found in response")

        # Deduplicate: keep first action per robot_id, filter to active only
        seen: set[int] = set()
        robot_actions = []
        for a in parsed:
            rid = a.get("robot_id")
            if rid in active_robot_ids and rid not in seen:
                seen.add(rid)
                robot_actions.append(
                    RobotAction(robot_id=rid, action_type=a["action_type"])
                )

        # Any active robot missing from LLM response → wait
        for rid in active_robot_ids:
            if rid not in seen:
                robot_actions.append(RobotAction(robot_id=rid, action_type="wait"))

        return WarehouseAction(robots=robot_actions), None

    except Exception as exc:
        wait_actions = [RobotAction(robot_id=rid, action_type="wait") for rid in active_robot_ids]
        return WarehouseAction(robots=wait_actions), str(exc)


# ─── Task runner ─────────────────────────────────────────────────────────────

def run_task(env: WarehouseEnv, task_id: str) -> None:
    task_config = TASK_REGISTRY[task_id]
    _reset_history()               # fresh deadlock history for each task
    obs = env.reset(task_id=task_id)
    _update_history(obs)           # record initial positions
    all_rewards: list[float] = []

    log_print(f"[START] task={task_id} env=warehouse model={MODEL_NAME}")
    render_grid(obs)

    for step_num in range(1, task_config.max_steps + 1):
        active_ids = [r.id for r in obs.robots if r.is_active]
        action, error_msg = get_actions(obs, active_ids)

        obs = env.step(action)
        _update_history(obs)       # record positions after step
        reward = obs.reward
        done   = obs.done
        all_rewards.append(reward)

        action_str  = ",".join(a.action_type for a in action.robots) if action.robots else "wait"
        error_field = error_msg if error_msg else "null"

        log_print(
            f"[STEP] step={step_num} action={action_str} reward={reward:.4f} "
            f"done={str(done).lower()} error={error_field}"
        )
        render_grid(obs, action_str=action_str, reward=reward)

        if done:
            break

    score   = GRADER_REGISTRY[task_id](env)
    delivered = sum(1 for o in obs.order_queue if o["status"] == "delivered")
    success = delivered > 0
    rewards_str = ",".join(f"{r:.4f}" for r in all_rewards)

    log_print(
        f"[END] success={str(success).lower()} steps={len(all_rewards)} "
        f"score={score:.4f} rewards={rewards_str}"
    )


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    with open("simulation.log", "w", encoding="utf-8") as f:
        f.write("")
    env = WarehouseEnv()
    for task_id in ["solo_delivery", "coordinated_delivery", "crisis_management"]:
        run_task(env, task_id)
