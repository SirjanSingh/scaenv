import os, json

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

PROMPT_TEMPLATE = (
    "You are controlling warehouse robots in a grid warehouse.\n"
    "Grid: rows increase downward, cols increase rightward.\n\n"
    "CURRENT STATE:\n{description}\n\n"
    "PENDING ORDERS:\n{order_info}\n\n"
    "ROBOT INSTRUCTIONS (follow exactly):\n{robot_info}\n\n"
    "RULES:\n"
    "- [■S■] cells are WALLS — robots CANNOT enter them. Stand NEXT TO the shelf, then pick.\n"
    "- [_P_] cells are walkable — robots CAN enter or stand adjacent, then drop.\n"
    "- pick works when Manhattan distance to shelf ≤ 1\n"
    "- drop works when Manhattan distance to packing station ≤ 1\n"
    "- Each robot MUST appear EXACTLY ONCE in your response.\n"
    "- Do NOT send two robots to the same cell — they will collide.\n\n"
    'Return a JSON array, one entry per active robot: [{{"robot_id": <int>, "action_type": "<move_up|move_down|move_left|move_right|pick|drop|wait>"}}]\n'
    "Return ONLY the JSON array, no markdown.\n\n"
    "Actions JSON:\n"
)

# ─── Logging ────────────────────────────────────────────────────────────────

def log_print(msg: str) -> None:
    print(msg, flush=True)
    with open("simulation.log", "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# ─── Grid rendering ─────────────────────────────────────────────────────────

def render_grid(obs, action_str: str = "", reward: float = 0.0) -> None:
    os.system("cls" if os.name == "nt" else "clear")
    lines = []

    W = max(10, obs.max_steps // 10)  # rough width guess
    sep = "═" * (obs.max_steps // 5 + 10)

    lines.append(sep)
    lines.append(f"  Task: {obs.task_id}   Step: {obs.step_count}/{obs.max_steps}")
    lines.append(sep)

    # Build carrying-robot set for visual indicator
    carrying = {r.id for r in obs.robots if r.carrying_item}

    for row in obs.grid:
        line_parts = []
        for cell in row:
            if cell == ".":
                line_parts.append("[ . ]")
            elif cell == "S":
                line_parts.append("[■S■]")   # shelf wall
            elif cell == "P":
                line_parts.append("[_P_]")   # packing station
            elif cell == "X":
                line_parts.append("[XXX]")   # blocked
            else:
                # Robot label e.g. "R0", "R1"
                try:
                    rid = int(cell[1:])
                    marker = f"{cell}*" if rid in carrying else f"{cell} "
                    line_parts.append(f"[{marker:^3}]")
                except (ValueError, IndexError):
                    line_parts.append(f"[{cell:^3}]")
        lines.append("".join(line_parts))

    lines.append("─" * len(lines[-1]))

    # Order summary
    delivered = sum(1 for o in obs.order_queue if o["status"] == "delivered")
    in_transit = sum(1 for o in obs.order_queue if o["status"] == "picked")
    pending = sum(1 for o in obs.order_queue if o["status"] == "pending")
    total = len(obs.order_queue)
    lines.append(
        f"  Orders: {delivered}/{total} done  |  {in_transit} in-transit  |  {pending} pending"
    )

    # Per-robot status
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

def _adjacent_cells(r: int, c: int) -> list[tuple[int, int]]:
    return [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]


def _nearest_adjacent(robot_r: int, robot_c: int, target_r: int, target_c: int) -> tuple[int, int]:
    candidates = _adjacent_cells(target_r, target_c)
    return min(candidates, key=lambda p: abs(p[0] - robot_r) + abs(p[1] - robot_c))


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
    """
    Distribute unassigned orders to idle robots so they don't all rush the same shelf.
    Each idle robot gets a DIFFERENT order.
    """
    # Collect unassigned pending orders in order
    unassigned_orders = [
        o for o in obs.order_queue
        if o["status"] == "pending" and o.get("assigned_robot_id") is None
    ]
    # Idle active robots
    idle_robots = [r for r in obs.robots if r.is_active and not r.assigned_order_id]

    # Round-robin: robot i → order i (different order per robot)
    idle_to_order: dict[int, dict] = {}
    for i, robot in enumerate(idle_robots):
        if i < len(unassigned_orders):
            idle_to_order[robot.id] = unassigned_orders[i]

    lines = []
    for r in obs.robots:
        if not r.is_active:
            lines.append(f"  Robot {r.id}: BROKEN DOWN — omit from response")
            continue

        if r.assigned_order_id:
            # Robot has a picked order (carrying or moving to shelf)
            order = next(
                (o for o in obs.order_queue if o["order_id"] == r.assigned_order_id), None
            )
            if order:
                if r.carrying_item:
                    pr, pc = order["packing_pos"]
                    dist = abs(r.row - pr) + abs(r.col - pc)
                    if dist <= 1:
                        lines.append(
                            f"  Robot {r.id} at ({r.row},{r.col}): CARRYING {r.assigned_order_id} — "
                            f"already next to packing station ({pr},{pc}). Action='drop' NOW."
                        )
                    else:
                        adj_r, adj_c = _nearest_adjacent(r.row, r.col, pr, pc)
                        lines.append(
                            f"  Robot {r.id} at ({r.row},{r.col}): CARRYING {r.assigned_order_id} → "
                            f"move toward ({adj_r},{adj_c}) [next to packing station ({pr},{pc})], then drop."
                        )
                else:
                    # Was assigned but hasn't picked yet (shouldn't happen after pick, but handle it)
                    sr, sc = order["shelf_pos"]
                    dist = abs(r.row - sr) + abs(r.col - sc)
                    if dist <= 1:
                        lines.append(
                            f"  Robot {r.id} at ({r.row},{r.col}): NEXT TO shelf ({sr},{sc}) — "
                            f"action='pick' NOW for {r.assigned_order_id}."
                        )
                    else:
                        adj_r, adj_c = _nearest_adjacent(r.row, r.col, sr, sc)
                        lines.append(
                            f"  Robot {r.id} at ({r.row},{r.col}): go to ({adj_r},{adj_c}) "
                            f"[next to shelf WALL at ({sr},{sc})] then pick {r.assigned_order_id}. "
                            f"Do NOT enter ({sr},{sc})."
                        )
        else:
            # Idle — use pre-distributed order
            order = idle_to_order.get(r.id)
            if order:
                sr, sc = order["shelf_pos"]
                dist = abs(r.row - sr) + abs(r.col - sc)
                if dist <= 1:
                    lines.append(
                        f"  Robot {r.id} at ({r.row},{r.col}): NEXT TO shelf ({sr},{sc}) — "
                        f"action='pick' NOW for {order['order_id']}."
                    )
                else:
                    adj_r, adj_c = _nearest_adjacent(r.row, r.col, sr, sc)
                    lines.append(
                        f"  Robot {r.id} at ({r.row},{r.col}): IDLE → go to ({adj_r},{adj_c}) "
                        f"[next to shelf WALL at ({sr},{sc})] for {order['order_id']}. "
                        f"Do NOT enter ({sr},{sc})."
                    )
            else:
                lines.append(
                    f"  Robot {r.id} at ({r.row},{r.col}): IDLE — all orders handled, action='wait'."
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
            # Fallback: model returned single object
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
    obs = env.reset(task_id=task_id)
    all_rewards: list[float] = []

    log_print(f"[START] task={task_id} env=warehouse model={MODEL_NAME}")
    render_grid(obs)

    for step_num in range(1, task_config.max_steps + 1):
        active_ids = [r.id for r in obs.robots if r.is_active]
        action, error_msg = get_actions(obs, active_ids)

        obs = env.step(action)
        reward = obs.reward
        done   = obs.done
        all_rewards.append(reward)

        action_str  = ",".join(a.action_type for a in action.robots) if action.robots else "wait"
        error_field = error_msg if error_msg else "null"

        log_print(
            f"[STEP] step={step_num} action={action_str} reward={reward:.2f} "
            f"done={str(done).lower()} error={error_field}"
        )
        render_grid(obs, action_str=action_str, reward=reward)

        if done:
            break

    score   = GRADER_REGISTRY[task_id](env)
    success = score > 0.0
    rewards_str = ",".join(f"{r:.2f}" for r in all_rewards)

    log_print(
        f"[END] success={str(success).lower()} steps={len(all_rewards)} "
        f"score={score:.2f} rewards={rewards_str}"
    )

# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    with open("simulation.log", "w", encoding="utf-8") as f:
        f.write("")
    env = WarehouseEnv()
    for task_id in ["solo_delivery", "coordinated_delivery", "crisis_management"]:
        run_task(env, task_id)
