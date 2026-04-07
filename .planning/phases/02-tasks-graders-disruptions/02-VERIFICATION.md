---
phase: 02-tasks-graders-disruptions
verified: 2026-04-07T17:38:52Z
status: passed
score: 17/17 requirements verified
re_verification: false
gaps: []
human_verification:
  - test: "Run a full episode to completion and call a grader on the live env object"
    expected: "Score reflects actual episode play, not just static state manipulation"
    why_human: "Full episode integration is tested by existing tests but end-to-end grader scoring requires a completing episode, which is slow and not exercised in test_env.py directly"
---

# Phase 02: Tasks, Graders, Disruptions — Verification Report

**Phase Goal:** 3 fully-defined tasks with deterministic programmatic graders (scores 0.0–1.0), a layered reward function with partial progress signals, and 3 disruption types that trigger mid-episode.
**Verified:** 2026-04-07T17:38:52Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|---------|
| 1  | `grade_solo_delivery` returns `fulfilled/5`, clamped to [0.0, 1.0] | VERIFIED | Code: `round(min(1.0, fulfilled / 5), 6)`. Tested: 0/5=0.0, 3/5=0.6, 5/5=1.0, 6/5 clamped to 1.0 |
| 2  | `grade_coordinated_delivery` uses `max(0.0, fulfilled/10 - 0.05*collisions)` | VERIFIED | Code and math confirmed. 5/10 - 2*0.05=0.4; massive collision floored at 0.0 |
| 3  | `grade_crisis_management` uses composite 0.5*order + 0.3*survival + 0.2*disruption | VERIFIED | Weights sum to 1.0. Tested with 12 delivered of 25, 5 alive, 2 surge delivered: score=0.62 matches math |
| 4  | All graders are deterministic (no randomness) | VERIFIED | No `random`/`choice` in graders.py source. Same state produces identical score across 5 calls |
| 5  | GRADER_REGISTRY maps all 3 task IDs to callable grader functions | VERIFIED | Keys match TASK_REGISTRY exactly: `['solo_delivery', 'coordinated_delivery', 'crisis_management']` |
| 6  | REW-01: +10.0 per delivery | VERIFIED | `calculate_reward` with 2 deliveries -> breakdown["delivery"]=20.0 |
| 7  | REW-02: +5.0 fast bonus per on-time delivery | VERIFIED | 1 on-time of 2 deliveries -> fast_bonus=5.0 |
| 8  | REW-03: -8.0 per collision pair | VERIFIED | 3 pairs -> collision=-24.0 |
| 9  | REW-04: -1.0 per waiting robot | VERIFIED | 3 waiting -> wasted_step=-3.0 |
| 10 | REW-05: -3.0 per late delivery | VERIFIED | 1 late -> late_penalty=-3.0 |
| 11 | REW-06: +3.0 per rerouting robot | VERIFIED | 2 rerouting -> reroute_bonus=6.0 |
| 12 | REW-07: -10.0 per unfulfilled order at episode end | VERIFIED | 3 unfulfilled at done -> timeout=-30.0 |
| 13 | REW-08: Grader normalizes to [0.0, 1.0] | VERIFIED | All 3 graders clamp/floor within range. Crisis grader reaches 0.0 when all robots dead |
| 14 | DISR-01: `blocked_aisle` fires at configured step, sets cells to blocked, displaces robots | VERIFIED | Step 5: no fire. Step 20: fires, (5,5)/(5,6) become impassable. Robot on (5,5) displaced to (4,5). No re-fire on repeat call |
| 15 | DISR-02: `robot_breakdown` deactivates robot, returns order to pending queue | VERIFIED | Robot 2 deactivated at step 15, carrying_item cleared, order returned to `pending` with assigned_robot_id=None |
| 16 | DISR-03: `surge_orders` injects additional orders mid-episode | VERIFIED | 20 -> 25 orders at step 25, all surge orders have `status="pending"` and `created_at_step=25` |
| 17 | Disruptions fire before observation is built so LLM sees updated state | VERIFIED | In `step()`: `step_count +=` (L34) -> `apply_disruptions` (L40) -> `_build_observation` (L61). Step 20 obs.description contains "DISRUPTION ALERTS" and "blocked" |

**Score: 17/17 truths verified**

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `warehouse_env/graders.py` | 3 grader functions + GRADER_REGISTRY | VERIFIED | 102 lines, all 3 graders implemented, registry wired |
| `warehouse_env/reward.py` | calculate_reward with all 7 step components | VERIFIED | 99 lines, RewardContext + calculate_reward complete |
| `warehouse_env/disruptions.py` | apply_disruptions + 3 handlers | VERIFIED | 149 lines, all 3 handler functions present |
| `warehouse_env/env.py` | list_tasks(), disruptions wired in step(), reward called | VERIFIED | list_tasks() at L238; disruptions at L192-196; reward via _apply_actions |
| `warehouse_env/models.py` | OrderState.assigned_at_step field | VERIFIED | L44: `assigned_at_step: Optional[int] = None` |
| `warehouse_env/tasks.py` | 3 TaskConfig entries in TASK_REGISTRY | VERIFIED | solo(1R,5O,10x10), coordinated(3R,10O,12x12), crisis(5R,20O,15x15) |
| `tests/test_env.py` | Integration tests for step, reset, state | VERIFIED | 36 tests, all pass |
| `tests/test_tasks.py` | Task registry and config tests | VERIFIED | 20 tests, all pass |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `env.step()` | `disruptions.apply_disruptions` | import + call at L193-196 | WIRED | Fires after step_count increment, before _build_observation |
| `env._apply_actions()` | `reward.calculate_reward` | import + RewardContext at L374-420 | WIRED | All 6 context fields populated |
| `env.step()` | `reward.calculate_reward` (timeout) | import + RewardContext at L207-213 | WIRED | is_done=True path applies REW-07 |
| `disruptions._handle_blocked_aisle` | `episode.grid.add_block` | direct call L75 | WIRED | Grid._blocked populated, is_passable returns False |
| `disruptions._handle_robot_breakdown` | `robot.is_active = False` + order requeue | L104-115 | WIRED | Order status reset to "pending", robot fields cleared |
| `disruptions._handle_surge_orders` | `episode.orders.extend` | L147 | WIRED | Orders injected with created_at_step=current_step |
| `GRADER_REGISTRY` | `grade_solo_delivery` etc. | dict literal L98-102 | WIRED | Keys match TASK_REGISTRY exactly |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `graders.py::grade_solo_delivery` | `ep.orders` | `env._episode` passed as `env` arg | Yes — live episode state | FLOWING |
| `graders.py::grade_coordinated_delivery` | `ep.collision_count` | Accumulated in `_apply_actions` L300 | Yes — incremented per collision pair | FLOWING |
| `graders.py::grade_crisis_management` | `surge_orders` (created_at_step > 0) | `_handle_surge_orders` injects with current_step | Yes — real step timestamp | FLOWING |
| `reward.py::calculate_reward` | `RewardContext` fields | Built in `_apply_actions` from episode state | Yes — newly_delivered, late, wait_ids all from live state | FLOWING |
| `disruptions.py::apply_disruptions` | `task_config.disruption_events` | `TASK_REGISTRY[ep.task_id]` in `step()` | Yes — real config data per task | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Result | Status |
|----------|--------|--------|
| `grade_solo_delivery`: 3/5 orders -> 0.6 | Returned 0.6 | PASS |
| `grade_coordinated_delivery`: 5/10 fulfilled, 2 collisions -> 0.4 | Returned 0.4 | PASS |
| `grade_crisis_management`: 12/25 delivered, 5 robots alive, 2/5 surge -> 0.62 | Returned 0.62 | PASS |
| REW-01 through REW-07 exact values | All matched spec (+10, +5, -8, -1, -3, +3, -10) | PASS |
| DISR-01 fires at step 20, not step 5, not twice | Confirmed | PASS |
| DISR-02 returns order to pending and clears robot state | Confirmed | PASS |
| DISR-03 injects exactly 5 surge orders with created_at_step=25 | 25 total orders confirmed | PASS |
| Disruption messages appear in obs.description at step 20 | "DISRUPTION ALERTS" in description | PASS |
| `env.list_tasks()` returns 3-element list in correct order | `['solo_delivery', 'coordinated_delivery', 'crisis_management']` | PASS |
| 110 tests pass with no failures | 110 passed in 17.82s | PASS |

---

## Requirements Coverage

| Requirement | File | Description | Status | Evidence |
|-------------|------|-------------|--------|---------|
| TASK-01 | graders.py L17-26 | solo_delivery grader: fulfilled/5 | SATISFIED | `round(min(1.0, fulfilled / 5), 6)` |
| TASK-02 | graders.py L29-44 | coordinated grader: base - collision penalty | SATISFIED | `max(0.0, base - penalty)` with collision_count |
| TASK-03 | graders.py L47-91 | crisis grader: composite 3-factor | SATISFIED | Weights 0.5/0.3/0.2, surge orders via created_at_step |
| TASK-04 | graders.py | All graders deterministic | SATISFIED | No random imports, pure function over episode state |
| TASK-05 | env.py L238-241 | `list_tasks()` returns task IDs | SATISFIED | Returns `list(TASK_REGISTRY.keys())` |
| REW-01 | reward.py L67-68 | +10 delivery | SATISFIED | `10.0 * len(context.fulfilled_this_step)` |
| REW-02 | reward.py L71-77 | +5 fast bonus | SATISFIED | `5.0 * len(on_time)` |
| REW-03 | reward.py L79-81 | -8 collision | SATISFIED | `-8.0 * context.collision_pairs` |
| REW-04 | reward.py L83-85 | -1 wasted step | SATISFIED | `-1.0 * len(context.wait_robot_ids)` |
| REW-05 | reward.py L87-89 | -3 late penalty | SATISFIED | `-3.0 * len(context.late_this_step)` |
| REW-06 | reward.py L91-93 | +3 reroute bonus | SATISFIED | `3.0 * len(context.reroute_robot_ids)` |
| REW-07 | reward.py L95-97 | -10 timeout | SATISFIED | `-10.0 * len(context.unfulfilled_at_done)` |
| REW-08 | graders.py | Grader normalizes to [0.0, 1.0] | SATISFIED | `min(1.0, ...)` and `max(0.0, ...)` in all 3 graders |
| DISR-01 | disruptions.py L65-93 | blocked_aisle | SATISFIED | `grid.add_block(r,c)` + robot displacement logic |
| DISR-02 | disruptions.py L96-117 | robot_breakdown | SATISFIED | `robot.is_active = False` + order return to pending |
| DISR-03 | disruptions.py L120-148 | surge_orders | SATISFIED | `episode.orders.extend(new_orders)` with created_at_step |

---

## Anti-Patterns Found

| File | Pattern | Severity | Assessment |
|------|---------|----------|-----------|
| `env.py` L193 | `from warehouse_env.disruptions import apply_disruptions` inside step() | Info | Deferred import pattern; harmless, no performance impact in this context |
| `env.py` L374 | `from warehouse_env.reward import RewardContext, calculate_reward` inside _apply_actions() | Info | Same deferred import pattern; avoids circular import risk, acceptable |
| `graders.py` L43 | `getattr(ep, "collision_count", 0)` defensive fallback | Info | Conservative guard; collision_count is defined on _EpisodeState L53, so this is belt-and-suspenders only |

No blockers or warnings found. All anti-patterns are informational only.

---

## Notable Implementation Detail: Crisis Grader Minimum

`grade_crisis_management` returns 0.3 when no orders are delivered but all robots are alive (because `survival_score=1.0` contributes `1.0 * 0.3 = 0.3`). This is **by design** per the composite formula — robot survival is an independent axis. The grader CAN reach 0.0 (verified: all robots deactivated + no deliveries = 0.0) and CAN reach 1.0 (all orders including surge delivered + all robots alive). The mathematical range is [0.0, 1.0] as required.

---

## Human Verification Required

### 1. Full Episode Grader Integration

**Test:** Run a complete episode to `done=True` on `crisis_management`, then call `GRADER_REGISTRY['crisis_management'](env)`.
**Expected:** Score reflects total orders delivered, robot survival, and whether surge orders (injected at step 25) were handled.
**Why human:** Requires running a 200-step episode to completion; too slow for automated spot-checks and not exercised by existing tests.

---

## Summary

Phase 02 goal is **fully achieved**. All 17 requirement checkpoints pass:

- **3 tasks fully defined** in `tasks.py` with correct grid sizes, robot counts, order counts, and disruption event schedules.
- **3 deterministic graders** in `graders.py`, each implementing the exact formula from requirements. GRADER_REGISTRY wired to matching TASK_REGISTRY keys.
- **7 reward components** (REW-01 through REW-07) implemented in `reward.py::calculate_reward` with exact values confirmed. REW-08 (normalization) enforced in all graders.
- **3 disruption types** in `disruptions.py`, each handler correct: `blocked_aisle` blocks cells and displaces robots, `robot_breakdown` deactivates robot and returns order to queue, `surge_orders` injects new pending orders.
- **Disruptions fire BEFORE `_build_observation`** — LLM receives updated state in the same step the disruption occurs.
- **`env.list_tasks()`** returns `['solo_delivery', 'coordinated_delivery', 'crisis_management']`.
- **`OrderState.assigned_at_step`** present as `Optional[int] = None`, set during pick action.
- **110 tests pass** with no failures.

---

_Verified: 2026-04-07T17:38:52Z_
_Verifier: Claude (gsd-verifier)_
