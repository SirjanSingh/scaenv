---
plan: 02-02
phase: 02-tasks-graders-disruptions
status: complete
completed: 2026-04-07
---

# Summary: Reward Function + Disruption System (02-02)

## Files Created / Modified

### NEW: `warehouse_env/reward.py`
- Exports: `RewardContext` (dataclass), `calculate_reward`
- `RewardContext` fields: fulfilled_this_step, late_this_step, wait_robot_ids, collision_pairs, reroute_robot_ids, unfulfilled_at_done, is_done, task_time_bonus_window
- `calculate_reward` handles 7 REW components:
  - REW-01 `delivery`: +10.0 per order delivered this step
  - REW-02 `fast_bonus`: +5.0 per on-time delivery (not in late_this_step)
  - REW-03 `collision`: -8.0 per collision pair
  - REW-04 `wasted_step`: -1.0 per waiting robot
  - REW-05 `late_penalty`: -3.0 per late delivery
  - REW-06 `reroute_bonus`: +3.0 per rerouting robot
  - REW-07 `timeout`: -10.0 per unfulfilled order at done
- Only non-zero components appear in breakdown dict

### NEW: `warehouse_env/disruptions.py`
- Exports: `apply_disruptions(episode, task_config, current_step) -> list[str]`
- DISR-01 `blocked_aisle`: adds cells to grid._blocked; displaces robots to adjacent free cell
- DISR-02 `robot_breakdown`: sets robot.is_active=False; returns held order to pending
- DISR-03 `surge_orders`: injects new OrderState objects with created_at_step=current_step
- Uses `episode.fired_disruptions` (set) to prevent re-firing

### MODIFIED: `warehouse_env/env.py`
- `_EpisodeState`: added `fired_disruptions: set = field(default_factory=set)` and `last_disruption_msgs: list = field(default_factory=list)`
- `step()`: calls `apply_disruptions(ep, cfg, ep.step_count)` BEFORE termination check
- `step()`: adds timeout REW-07 penalty block when `ep.done=True` and unfulfilled orders exist
- `_apply_actions()`: snapshots `_prev_delivered` at start; replaces inline `return WarehouseReward(value=total, breakdown=breakdown)` with full `calculate_reward(RewardContext(...))` call
- `_build_description()`: appends "DISRUPTION ALERTS:" section when `last_disruption_msgs` is non-empty

## Integration Test Results

All tests passed:
1. ✓ `wasted_step: -1.0` in reward breakdown for wait action
2. ✓ Blocked aisle fires at step 20 in coordinated_delivery (`(5,5)` and `(5,6)` blocked)
3. ✓ Robot breakdown fires at step 15 in crisis_management (robot 2 deactivated)
4. ✓ GRADER_REGISTRY keys match TASK_REGISTRY keys
5. ✓ Grader scores in [0.0, 1.0]
6. ✓ obs.description contains disruption text when disruption fires
7. ✓ Surge orders inject 5 new orders at step 25 (total 25)
8. ✓ Graders are deterministic

## Deviations from Plan

None. All tasks implemented exactly as specified.
