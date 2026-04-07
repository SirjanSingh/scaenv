---
plan: 02-01
phase: 02-tasks-graders-disruptions
status: complete
completed: 2026-04-07
---

# Summary: Task Definitions + Graders (02-01)

## Files Created / Modified

### NEW: `warehouse_env/graders.py`
- Exports: `GRADER_REGISTRY`, `grade_solo_delivery`, `grade_coordinated_delivery`, `grade_crisis_management`
- `GRADER_REGISTRY`: dict with 3 keys matching TASK_REGISTRY keys
- `grade_solo_delivery(env)`: returns `fulfilled / 5`, clamped to [0.0, 1.0]
- `grade_coordinated_delivery(env)`: returns `max(0.0, fulfilled/10 - 0.05*collision_count)`
- `grade_crisis_management(env)`: weighted composite — `order_score*0.5 + survival_score*0.3 + disruption_score*0.2`
- All graders return `0.0` (no crash) when `env._episode is None`

### MODIFIED: `warehouse_env/models.py`
- `OrderState`: added `assigned_at_step: Optional[int] = None` after `assigned_robot_id`
- Field serializes correctly via `model_dump()` / `to_dict()`

### MODIFIED: `warehouse_env/env.py`
- `_EpisodeState`: added `collision_count: int = 0` field (for grader use)
- `_apply_actions`: increments `ep.collision_count += pairs` in collision detection loop
- `_apply_actions` pick branch: sets `order.assigned_at_step = ep.step_count` after `order.status = "picked"`
- `WarehouseEnv.list_tasks()`: new method returning `list(TASK_REGISTRY.keys())`

## Verification Results

All tests passed:
- `OrderState().assigned_at_step` is `None` (default)
- `OrderState(assigned_at_step=5).to_dict()['assigned_at_step']` equals `5`
- `GRADER_REGISTRY` has exactly 3 keys
- `grade_solo_delivery` returns 1.0 for 5/5 delivered, 0.6 for 3/5
- `grade_coordinated_delivery` returns 1.0 for 10/10, 0.0 with 100 collision pairs
- All graders return 0.0 when `env._episode is None`
- `env.list_tasks()` returns `['solo_delivery', 'coordinated_delivery', 'crisis_management']`

## Deviations from Plan

None. All tasks implemented exactly as specified.
