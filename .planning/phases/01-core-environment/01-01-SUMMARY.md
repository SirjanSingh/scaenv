---
phase: 01-core-environment
plan: "01"
subsystem: warehouse_env
tags: [pydantic, models, grid, tasks, tdd, openenv]
dependency_graph:
  requires: []
  provides:
    - warehouse_env.models (RobotAction, WarehouseAction, RobotState, OrderState, WarehouseObservation, WarehouseState, WarehouseReward)
    - warehouse_env.grid (Grid, CELL_FREE, CELL_SHELF, CELL_PACKING, CELL_BLOCKED)
    - warehouse_env.tasks (TaskConfig, TASK_REGISTRY)
  affects:
    - warehouse_env/__init__.py (package root with try/except for env.py)
tech_stack:
  added: [pydantic, openenv-core]
  patterns:
    - Pydantic model inheritance from openenv base types (Action, Observation, State)
    - Dict-based grid with separate _blocked disruption overlay
    - Python dataclass TaskConfig (not Pydantic — for speed)
    - Try/except in __init__.py for WarehouseEnv (env.py added in 01-02)
key_files:
  created:
    - warehouse_env/__init__.py
    - warehouse_env/models.py
    - warehouse_env/grid.py
    - warehouse_env/tasks.py
    - tests/__init__.py
    - tests/test_models.py
    - tests/test_grid.py
    - tests/test_tasks.py
  modified: []
decisions:
  - "WarehouseAction wraps list[RobotAction] to bridge OpenEnv single-action contract with multi-robot parallel step (per research mismatch note)"
  - "OrderState uses tuple[int,int] for shelf_pos and packing_pos — Pydantic serializes these as JSON arrays"
  - "tasks.py uses loop to assign coordinated_delivery orders to nearest packing station by column distance"
  - "crisis_management generates 20 orders by cycling over 14 shelves and 3 packing stations"
metrics:
  duration: "7m 17s"
  completed: "2026-04-07"
  tasks: 2
  files: 8
---

# Phase 01 Plan 01: Pydantic Models and Grid Engine Summary

Typed data layer for WarehouseEnv — all Pydantic models inheriting from openenv base types, a dict-based grid engine with two-layer architecture, and a TaskConfig registry with 3 pre-configured tasks.

## Tasks Completed

| Task | Description | Commit | Tests |
|------|-------------|--------|-------|
| 1 | Pydantic models (actions, observations, state, reward) | 45e1f8d | 27 pass |
| 2 | Grid engine and task registry | 3749b79 | 47 pass |

**Total: 74 tests, 0 failures**

## Files Created

### warehouse_env/models.py
Exports: `RobotAction`, `WarehouseAction`, `RobotState`, `OrderState`, `WarehouseObservation`, `WarehouseState`, `WarehouseReward`

Key class signatures for Plan 01-02:

```python
class RobotAction(Action):
    robot_id: int
    action_type: str  # not validated here; normalization in env.py

class WarehouseAction(Action):
    robots: list[RobotAction] = Field(default_factory=list)

class RobotState(BaseModel):
    id: int; row: int; col: int
    carrying_item: bool
    assigned_order_id: Optional[str] = None
    is_active: bool = True
    def to_dict(self) -> dict

class OrderState(BaseModel):
    order_id: str
    shelf_pos: tuple[int, int]
    packing_pos: tuple[int, int]
    status: str = "pending"
    created_at_step: int = 0
    assigned_robot_id: Optional[int] = None
    def to_dict(self) -> dict

class WarehouseObservation(Observation):
    grid: list[list[str]]
    robots: list[RobotState]
    order_queue: list[dict]
    step_count: int
    max_steps: int
    task_id: str
    description: str
    # inherited: done, reward, metadata

class WarehouseState(State):
    task_id: str; grid: list[list[str]]
    robots: list[dict]; orders: list[dict]; done: bool
    # inherited: episode_id, step_count

class WarehouseReward(BaseModel):
    value: float
    breakdown: dict[str, float]  # keys: delivery, fast_bonus, collision, ...
```

### warehouse_env/grid.py
Exports: `Grid`, `CELL_FREE="."`, `CELL_SHELF="S"`, `CELL_PACKING="P"`, `CELL_BLOCKED="X"`

Grid stores `_base: dict[tuple,str]` (static layout), `_blocked: set` (disruptions), `_robots: dict[tuple,str]` (robot overlay). `get_cell()` ignores robots; `to_2d_list()` overlays robots on top.

### warehouse_env/tasks.py
Exports: `TaskConfig` (dataclass), `TASK_REGISTRY: dict[str, TaskConfig]`

| Task ID | Grid | Robots | Orders | max_steps | Disruptions |
|---------|------|--------|--------|-----------|-------------|
| solo_delivery | 10x10 | 1 | 5 | 100 | none |
| coordinated_delivery | 12x12 | 3 | 10 | 150 | blocked_aisle at step 20 |
| crisis_management | 15x15 | 5 | 20 | 200 | robot_breakdown at 15, surge_orders at 25 |

### warehouse_env/__init__.py
Package root. Imports all models directly. Wraps `from warehouse_env.env import WarehouseEnv` in `try/except ImportError` so package is importable before Plan 01-02 creates env.py.

## Interface Contract for Plan 01-02

Plan 01-02 (`WarehouseEnv` environment class) must:
1. `from warehouse_env.models import WarehouseAction, WarehouseObservation, WarehouseState, WarehouseReward, RobotAction, RobotState, OrderState`
2. `from warehouse_env.grid import Grid`
3. `from warehouse_env.tasks import TASK_REGISTRY, TaskConfig`
4. Implement `class WarehouseEnv(Environment[WarehouseAction, WarehouseObservation, WarehouseState])`
5. In `step(action: WarehouseAction)`: iterate `action.robots`, treat missing robots as `wait`, apply simultaneous move resolution

## Test Results

```
tests/test_models.py  — 27 passed
tests/test_grid.py    — 20 passed
tests/test_tasks.py   — 27 passed
Total: 74 passed in ~18s
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all data is wired. `WarehouseEnv = None` in `__init__.py` is an intentional placeholder documented in the plan (env.py created in Plan 01-02).

## Self-Check: PASSED

Files verified:
- warehouse_env/models.py: FOUND
- warehouse_env/grid.py: FOUND
- warehouse_env/tasks.py: FOUND
- warehouse_env/__init__.py: FOUND
- tests/test_models.py: FOUND
- tests/test_grid.py: FOUND
- tests/test_tasks.py: FOUND

Commits verified:
- 45e1f8d (feat: implement Pydantic models): FOUND
- 3749b79 (feat: implement Grid engine): FOUND
