"""Task registry for WarehouseEnv.

TaskConfig is a plain Python dataclass (not Pydantic) for speed.
TASK_REGISTRY maps task_id -> TaskConfig for all 3 tasks.
"""
from dataclasses import dataclass, field


@dataclass
class TaskConfig:
    """Configuration for a single warehouse task."""
    task_id: str
    name: str
    description: str
    grid_rows: int
    grid_cols: int
    num_robots: int
    shelf_positions: list[tuple[int, int]]       # (row, col) of each shelf
    packing_positions: list[tuple[int, int]]     # (row, col) of each packing station
    robot_start_positions: list[tuple[int, int]] # initial (row, col) per robot (index = robot_id)
    initial_orders: list[dict]                   # each dict: {order_id, shelf_pos, packing_pos}
    max_steps: int
    disruption_events: list[dict]                # {step, type, params} — consumed by Phase 2
    time_bonus_window: int                       # steps within which delivery earns fast bonus


# ---------------------------------------------------------------------------
# Task 1: solo_delivery
# TASK-01: 1 robot, 5 orders, 10x10 grid, max_steps=100
# ---------------------------------------------------------------------------

_solo_shelves = [(1, 1), (1, 3), (1, 5), (1, 7), (3, 1)]
_solo_packing = [(8, 2), (8, 7)]
_solo_orders = [
    {"order_id": "o1", "shelf_pos": [1, 1], "packing_pos": [8, 2]},
    {"order_id": "o2", "shelf_pos": [1, 3], "packing_pos": [8, 2]},
    {"order_id": "o3", "shelf_pos": [1, 5], "packing_pos": [8, 7]},
    {"order_id": "o4", "shelf_pos": [1, 7], "packing_pos": [8, 7]},
    {"order_id": "o5", "shelf_pos": [3, 1], "packing_pos": [8, 2]},
]

_solo_delivery = TaskConfig(
    task_id="solo_delivery",
    name="Solo Delivery",
    description=(
        "A single robot must pick items from shelves and deliver them to "
        "packing stations. Simple navigation, 5 orders, 10x10 grid."
    ),
    grid_rows=10,
    grid_cols=10,
    num_robots=1,
    shelf_positions=_solo_shelves,
    packing_positions=_solo_packing,
    robot_start_positions=[(5, 5)],
    initial_orders=_solo_orders,
    max_steps=100,
    disruption_events=[],
    time_bonus_window=20,
)

# ---------------------------------------------------------------------------
# Task 2: coordinated_delivery
# TASK-02: 3 robots, 10 orders, 12x12 grid, blocked aisle at step 20
# ---------------------------------------------------------------------------

_coord_shelves = [
    (1, 1), (1, 3), (1, 5), (1, 7), (1, 9),
    (3, 1), (3, 3), (3, 5), (3, 7), (3, 9),
]
_coord_packing = [(10, 3), (10, 6), (10, 9)]

# Assign each shelf to nearest packing station (by column proximity)
def _nearest_packing(shelf_col: int, packing_cols: list[int]) -> int:
    return min(packing_cols, key=lambda pc: abs(shelf_col - pc))

_coord_packing_cols = [10, 3, 6, 9]  # packing station cols
_coord_orders = []
for _i, (_sr, _sc) in enumerate(_coord_shelves, start=1):
    _nearest_pc = min(_coord_packing, key=lambda p: abs(_sc - p[1]))
    _coord_orders.append({
        "order_id": f"o{_i}",
        "shelf_pos": [_sr, _sc],
        "packing_pos": list(_nearest_pc),
    })

_coordinated_delivery = TaskConfig(
    task_id="coordinated_delivery",
    name="Coordinated Delivery",
    description=(
        "Three robots coordinate to deliver 10 orders on a 12x12 grid. "
        "A blocked aisle appears at step 20, requiring rerouting."
    ),
    grid_rows=12,
    grid_cols=12,
    num_robots=3,
    shelf_positions=_coord_shelves,
    packing_positions=_coord_packing,
    robot_start_positions=[(6, 2), (6, 6), (6, 10)],
    initial_orders=_coord_orders,
    max_steps=150,
    disruption_events=[
        {"step": 20, "type": "blocked_aisle", "params": {"cells": [[5, 5], [5, 6]]}},
    ],
    time_bonus_window=30,
)

# ---------------------------------------------------------------------------
# Task 3: crisis_management
# TASK-03: 5 robots, 20 orders, 15x15 grid
# ---------------------------------------------------------------------------

_crisis_shelves = [
    (1, 1), (1, 3), (1, 5), (1, 7), (1, 9), (1, 11), (1, 13),
    (3, 1), (3, 3), (3, 5), (3, 7), (3, 9), (3, 11), (3, 13),
]
_crisis_packing = [(13, 3), (13, 7), (13, 11)]

# Generate 20 orders cycling through available shelves and packing stations
_crisis_orders = []
for _i in range(20):
    _shelf = _crisis_shelves[_i % len(_crisis_shelves)]
    _packing = _crisis_packing[_i % len(_crisis_packing)]
    _crisis_orders.append({
        "order_id": f"o{_i + 1}",
        "shelf_pos": list(_shelf),
        "packing_pos": list(_packing),
    })

_crisis_management = TaskConfig(
    task_id="crisis_management",
    name="Crisis Management",
    description=(
        "Five robots must handle 20 orders on a 15x15 grid while dealing with "
        "a robot breakdown at step 15 and a surge of new orders at step 25."
    ),
    grid_rows=15,
    grid_cols=15,
    num_robots=5,
    shelf_positions=_crisis_shelves,
    packing_positions=_crisis_packing,
    robot_start_positions=[(7, 2), (7, 5), (7, 8), (7, 11), (7, 13)],
    initial_orders=_crisis_orders,
    max_steps=200,
    disruption_events=[
        {"step": 15, "type": "robot_breakdown", "params": {"robot_id": 2}},
        {"step": 25, "type": "surge_orders", "params": {"num_orders": 5}},
    ],
    time_bonus_window=40,
)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TASK_REGISTRY: dict[str, TaskConfig] = {
    "solo_delivery": _solo_delivery,
    "coordinated_delivery": _coordinated_delivery,
    "crisis_management": _crisis_management,
}
