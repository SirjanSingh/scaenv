"""Disruption system for WarehouseEnv.

Called from env.py step() BEFORE building the observation, so the LLM sees
disruption state immediately.

apply_disruptions fires all events where event['step'] == current_step.
Returns a list of human-readable description strings for obs.description.

Fired events are recorded in ep.fired_disruptions (declared as a dataclass
field on _EpisodeState — see env.py) to prevent re-firing on subsequent steps.

DISR-01 blocked_aisle:   adds cells to grid._blocked; displaces robots on those cells
DISR-02 robot_breakdown: sets robot.is_active=False; returns robot's order to pending
DISR-03 surge_orders:    injects new orders into ep.orders
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from warehouse_env.models import OrderState

if TYPE_CHECKING:
    from warehouse_env.env import _EpisodeState
    from warehouse_env.tasks import TaskConfig


def apply_disruptions(
    episode: "_EpisodeState",
    task_config: "TaskConfig",
    current_step: int,
) -> list[str]:
    """Fire any disruption events scheduled for current_step.

    Returns list of description strings. Empty list if nothing fired.
    Uses episode.fired_disruptions (set field on _EpisodeState) to track
    fired event indices and prevent re-firing.
    """
    descriptions: list[str] = []

    for idx, event in enumerate(task_config.disruption_events):
        if idx in episode.fired_disruptions:
            continue
        if event["step"] != current_step:
            continue

        episode.fired_disruptions.add(idx)
        etype = event["type"]
        params = event.get("params", {})

        if etype == "blocked_aisle":
            desc = _handle_blocked_aisle(episode, params)
            descriptions.append(desc)

        elif etype == "robot_breakdown":
            desc = _handle_robot_breakdown(episode, params)
            descriptions.append(desc)

        elif etype == "surge_orders":
            desc = _handle_surge_orders(episode, params, task_config, current_step)
            descriptions.append(desc)

    return descriptions


def _handle_blocked_aisle(
    episode: "_EpisodeState", params: dict
) -> str:
    """DISR-01: Block cells; displace robots on those cells to adjacent free cell."""
    cells: list[list[int]] = params.get("cells", [])
    blocked_coords: list[tuple[int, int]] = []

    for cell in cells:
        r, c = cell[0], cell[1]
        episode.grid.add_block(r, c)
        blocked_coords.append((r, c))

    # Displace robots standing on newly-blocked cells
    for robot in episode.robots:
        if not robot.is_active:
            continue
        if (robot.row, robot.col) in episode.grid._blocked:
            # Find first adjacent free cell
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = robot.row + dr, robot.col + dc
                if episode.grid.is_passable(nr, nc) and (nr, nc) not in episode.grid._robots:
                    episode.grid.remove_robot(robot.row, robot.col, f"R{robot.id}")
                    episode.grid.place_robot(nr, nc, f"R{robot.id}")
                    robot.row = nr
                    robot.col = nc
                    break
            # If no adjacent free cell, robot stays (blocked in place is fine)

    return f"Blocked aisle disruption: cells {blocked_coords} are now impassable."


def _handle_robot_breakdown(
    episode: "_EpisodeState", params: dict
) -> str:
    """DISR-02: Deactivate robot; return its pending order to unassigned queue."""
    robot_id: int = params.get("robot_id", 0)

    for robot in episode.robots:
        if robot.id == robot_id:
            robot.is_active = False
            # Return robot's currently-assigned order back to pending
            if robot.assigned_order_id is not None:
                for order in episode.orders:
                    if order.order_id == robot.assigned_order_id and order.status == "picked":
                        order.status = "pending"
                        order.assigned_robot_id = None
                        order.assigned_at_step = None
                        break
                robot.carrying_item = False
                robot.assigned_order_id = None
            break

    return f"Robot breakdown: robot {robot_id} is now inactive."


def _handle_surge_orders(
    episode: "_EpisodeState",
    params: dict,
    task_config: "TaskConfig",
    current_step: int,
) -> str:
    """DISR-03: Inject new orders cycling through task shelves/packing stations."""
    num_orders: int = params.get("num_orders", 5)
    shelves = task_config.shelf_positions
    packings = task_config.packing_positions

    # Generate orders with unique IDs: surge_<step>_<i>
    new_orders: list[OrderState] = []
    for i in range(num_orders):
        shelf = shelves[i % len(shelves)]
        packing = packings[i % len(packings)]
        order_id = f"surge_{current_step}_{i}"
        new_orders.append(OrderState(
            order_id=order_id,
            shelf_pos=shelf,
            packing_pos=packing,
            status="pending",
            created_at_step=current_step,
            assigned_robot_id=None,
            assigned_at_step=None,
        ))

    episode.orders.extend(new_orders)
    return f"Surge orders disruption: {num_orders} new orders injected at step {current_step}."
