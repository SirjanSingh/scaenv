"""WarehouseEnv — OpenEnv-compliant multi-robot warehouse environment.

All internal episode state lives in the private _EpisodeState dataclass.
WarehouseEnv inherits from openenv Environment[WarehouseAction, WarehouseObservation, WarehouseState].
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from openenv.core.env_server.interfaces import Environment

from warehouse_env.grid import Grid, CELL_SHELF, CELL_PACKING
from warehouse_env.models import (
    WarehouseAction,
    WarehouseObservation,
    WarehouseState,
    WarehouseReward,
    RobotState,
    OrderState,
    RobotAction,
)
from warehouse_env.tasks import TASK_REGISTRY, TaskConfig

# Valid movement action types
_MOVE_ACTIONS = {"move_up", "move_down", "move_left", "move_right"}
_VALID_ACTIONS = _MOVE_ACTIONS | {"pick", "drop", "wait"}

# Movement deltas: action_type -> (delta_row, delta_col)
_MOVE_DELTAS: dict[str, tuple[int, int]] = {
    "move_up": (-1, 0),
    "move_down": (1, 0),
    "move_left": (0, -1),
    "move_right": (0, 1),
}


# ---------------------------------------------------------------------------
# Private episode state
# ---------------------------------------------------------------------------

@dataclass
class _EpisodeState:
    """All mutable state for one episode."""
    task_id: str
    step_count: int
    max_steps: int
    grid: Grid
    robots: list[RobotState]
    orders: list[OrderState]
    done: bool = False
    cumulative_reward: float = 0.0
    collision_count: int = 0  # accumulated collision pairs across episode (for grader)


# ---------------------------------------------------------------------------
# WarehouseEnv
# ---------------------------------------------------------------------------

class WarehouseEnv(Environment[WarehouseAction, WarehouseObservation, WarehouseState]):
    """Multi-robot warehouse environment implementing the OpenEnv interface.

    One instance handles all three tasks via reset(task_id=...).
    Singleton pattern: create one instance and reuse across HTTP reset/step calls.
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = False

    def __init__(self) -> None:
        super().__init__()
        self._episode: Optional[_EpisodeState] = None

    # ------------------------------------------------------------------
    # OpenEnv interface
    # ------------------------------------------------------------------

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        task_id: str = "solo_delivery",
        **kwargs,
    ) -> WarehouseObservation:
        """Initialize a new episode for the given task_id.

        Args:
            seed: Unused — deterministic tasks.
            episode_id: Optional episode identifier forwarded to state.
            task_id: One of "solo_delivery", "coordinated_delivery", "crisis_management".

        Returns:
            WarehouseObservation with step_count=0 and done=False.

        Raises:
            ValueError: If task_id is not in TASK_REGISTRY.
        """
        if task_id not in TASK_REGISTRY:
            valid = list(TASK_REGISTRY.keys())
            raise ValueError(
                f"Unknown task_id: {task_id!r}. Valid task IDs: {valid}"
            )

        cfg: TaskConfig = TASK_REGISTRY[task_id]

        # Build static grid layout
        g = Grid(cfg.grid_rows, cfg.grid_cols)
        for (r, c) in cfg.shelf_positions:
            g.set_cell(r, c, CELL_SHELF)
        for (r, c) in cfg.packing_positions:
            g.set_cell(r, c, CELL_PACKING)

        # Build initial robot states and place on grid
        robots: list[RobotState] = []
        for i, pos in enumerate(cfg.robot_start_positions):
            robot = RobotState(
                id=i,
                row=pos[0],
                col=pos[1],
                carrying_item=False,
                assigned_order_id=None,
                is_active=True,
            )
            robots.append(robot)
            g.place_robot(pos[0], pos[1], f"R{i}")

        # Build initial order states
        orders: list[OrderState] = []
        for o in cfg.initial_orders:
            orders.append(
                OrderState(
                    order_id=o["order_id"],
                    shelf_pos=tuple(o["shelf_pos"]),
                    packing_pos=tuple(o["packing_pos"]),
                    status="pending",
                    created_at_step=0,
                    assigned_robot_id=None,
                )
            )

        self._episode = _EpisodeState(
            task_id=task_id,
            step_count=0,
            max_steps=cfg.max_steps,
            grid=g,
            robots=robots,
            orders=orders,
            done=False,
            cumulative_reward=0.0,
        )

        return self._build_observation()

    def step(self, action: WarehouseAction, **kwargs) -> WarehouseObservation:
        """Advance the simulation by one tick with the given multi-robot action.

        Args:
            action: WarehouseAction with per-robot actions. Missing robots get 'wait'.

        Returns:
            Updated WarehouseObservation with reward, done, and step_count set.

        Raises:
            RuntimeError: If called before reset() or when episode is already done.
        """
        if self._episode is None or self._episode.done:
            raise RuntimeError(
                "Call reset() before step(). "
                "Also call reset() to start a new episode after done=True."
            )

        ep = self._episode

        # Build per-robot action map; missing robots get 'wait'
        robot_actions: dict[int, RobotAction] = {
            ra.robot_id: ra for ra in action.robots
        }
        for robot in ep.robots:
            if robot.id not in robot_actions:
                robot_actions[robot.id] = RobotAction(
                    robot_id=robot.id, action_type="wait"
                )

        # Apply actions and compute reward
        reward = self._apply_actions(ep, robot_actions)

        # Advance step counter
        ep.step_count += 1
        ep.cumulative_reward += reward.value

        # Check episode termination
        all_delivered = all(o.status == "delivered" for o in ep.orders)
        ep.done = all_delivered or (ep.step_count >= ep.max_steps)

        # Build observation
        obs = self._build_observation()
        obs.reward = reward.value
        obs.done = ep.done
        obs.metadata["reward_breakdown"] = reward.breakdown
        return obs

    @property
    def state(self) -> WarehouseState:
        """Return current full state as WarehouseState (not a plain dict)."""
        if self._episode is None:
            return WarehouseState()
        ep = self._episode
        return WarehouseState(
            episode_id=str(id(ep)),
            step_count=ep.step_count,
            task_id=ep.task_id,
            grid=ep.grid.to_2d_list(),
            robots=[r.to_dict() for r in ep.robots],
            orders=[o.to_dict() for o in ep.orders],
            done=ep.done,
        )

    def list_tasks(self) -> list[str]:
        """Return the ids of all registered tasks. Per TASK-05 phase success criterion."""
        from warehouse_env.tasks import TASK_REGISTRY
        return list(TASK_REGISTRY.keys())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_actions(
        self, ep: _EpisodeState, robot_actions: dict[int, RobotAction]
    ) -> WarehouseReward:
        """Apply all robot actions simultaneously and return computed reward.

        Movement is resolved simultaneously with collision detection:
        - Two robots wanting the same target cell both stay.
        - Two robots swapping cells both stay.
        """
        breakdown: dict[str, float] = {}

        # Normalize action types: invalid -> 'wait'
        normalized: dict[int, str] = {}
        for rid, ra in robot_actions.items():
            atype = ra.action_type if ra.action_type in _VALID_ACTIONS else "wait"
            normalized[rid] = atype

        # --- Step 1: Compute intended positions ---
        current_positions: dict[int, tuple[int, int]] = {
            r.id: (r.row, r.col) for r in ep.robots
        }
        intended: dict[int, tuple[int, int]] = {}
        for robot in ep.robots:
            atype = normalized.get(robot.id, "wait")
            if atype in _MOVE_DELTAS:
                dr, dc = _MOVE_DELTAS[atype]
                nr, nc = robot.row + dr, robot.col + dc
                if ep.grid.is_passable(nr, nc):
                    intended[robot.id] = (nr, nc)
                else:
                    intended[robot.id] = (robot.row, robot.col)
            else:
                intended[robot.id] = (robot.row, robot.col)

        # --- Step 2: Collision detection ---
        # 2a. Multiple robots targeting the same cell → all revert
        from collections import defaultdict
        target_counts: dict[tuple[int, int], list[int]] = defaultdict(list)
        for rid, pos in intended.items():
            target_counts[pos].append(rid)

        collisions: set[int] = set()
        for pos, rids in target_counts.items():
            if len(rids) >= 2:
                for rid in rids:
                    collisions.add(rid)
                # Penalty per collision pair
                n = len(rids)
                pairs = n * (n - 1) // 2
                breakdown["collision"] = breakdown.get("collision", 0.0) + (-8.0 * pairs)
                ep.collision_count += pairs  # accumulate for grader

        # 2b. Swap detection: A wants B's current pos AND B wants A's current pos
        robot_ids = list(intended.keys())
        for i in range(len(robot_ids)):
            for j in range(i + 1, len(robot_ids)):
                a, b = robot_ids[i], robot_ids[j]
                if (
                    intended[a] == current_positions[b]
                    and intended[b] == current_positions[a]
                    and intended[a] != current_positions[a]  # actually moving
                ):
                    collisions.add(a)
                    collisions.add(b)

        # Revert colliding robots to current position
        for rid in collisions:
            intended[rid] = current_positions[rid]

        # --- Step 3: Apply non-conflicting moves ---
        robot_map: dict[int, RobotState] = {r.id: r for r in ep.robots}
        for robot in ep.robots:
            new_pos = intended[robot.id]
            old_pos = (robot.row, robot.col)
            if new_pos != old_pos:
                ep.grid.remove_robot(old_pos[0], old_pos[1], f"R{robot.id}")
                ep.grid.place_robot(new_pos[0], new_pos[1], f"R{robot.id}")
                robot.row = new_pos[0]
                robot.col = new_pos[1]

        # --- Step 4: Process pick/drop actions ---
        order_map: dict[str, OrderState] = {}
        for o in ep.orders:
            order_map[o.order_id] = o

        for robot in ep.robots:
            if not robot.is_active:
                continue
            atype = normalized.get(robot.id, "wait")

            if atype == "pick" and not robot.carrying_item:
                # Find a pending order whose shelf is adjacent (|dr|+|dc| <= 1)
                # with shelf cell adjacent to robot
                for order in ep.orders:
                    if order.status != "pending":
                        continue
                    sr, sc = order.shelf_pos
                    # Adjacent: Manhattan distance <= 1
                    if abs(robot.row - sr) + abs(robot.col - sc) <= 1:
                        robot.carrying_item = True
                        robot.assigned_order_id = order.order_id
                        order.status = "picked"
                        order.assigned_robot_id = robot.id
                        order.assigned_at_step = ep.step_count  # record step for fast-bonus tracking
                        breakdown["pick"] = breakdown.get("pick", 0.0) + 1.0
                        break

            elif atype == "drop" and robot.carrying_item:
                # Find the order this robot is carrying
                for order in ep.orders:
                    if (
                        order.status == "picked"
                        and order.assigned_robot_id == robot.id
                    ):
                        pr, pc = order.packing_pos
                        # Check robot is adjacent to correct packing station
                        if abs(robot.row - pr) + abs(robot.col - pc) <= 1:
                            order.status = "delivered"
                            robot.carrying_item = False
                            robot.assigned_order_id = None
                            breakdown["delivery"] = breakdown.get("delivery", 0.0) + 10.0
                        break

        total = sum(breakdown.values())
        return WarehouseReward(value=total, breakdown=breakdown)

    def _build_observation(self) -> WarehouseObservation:
        """Build a WarehouseObservation from current episode state."""
        if self._episode is None:
            return WarehouseObservation()
        ep = self._episode
        return WarehouseObservation(
            grid=ep.grid.to_2d_list(),
            robots=list(ep.robots),
            order_queue=[o.to_dict() for o in ep.orders],
            step_count=ep.step_count,
            max_steps=ep.max_steps,
            task_id=ep.task_id,
            description=self._build_description(ep),
            done=ep.done,
        )

    def _build_description(self, ep: _EpisodeState) -> str:
        """Build a natural language summary of the current episode state."""
        remaining = sum(1 for o in ep.orders if o.status != "delivered")
        total = len(ep.orders)

        parts = [f"Task: {ep.task_id}. Step {ep.step_count}/{ep.max_steps}."]

        for robot in ep.robots:
            status = "idle"
            if not robot.is_active:
                status = "broken down"
            elif robot.carrying_item and robot.assigned_order_id:
                status = f"carrying item for order {robot.assigned_order_id}"
            parts.append(
                f"Robot {robot.id} at ({robot.row},{robot.col}) {status}."
            )

        parts.append(f"{remaining} of {total} orders remaining.")

        # Mention active blocks (disruptions)
        if ep.grid._blocked:
            parts.append(f"Active disruptions: {len(ep.grid._blocked)} blocked cell(s).")

        return " ".join(parts)
