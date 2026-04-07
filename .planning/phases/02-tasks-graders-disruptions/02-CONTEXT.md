# Phase 2: Tasks, Graders & Disruptions - Context

**Gathered:** 2026-04-07
**Status:** Ready for planning
**Source:** /gsd:discuss-phase

<domain>
## Phase Boundary

Deliver: (1) deterministic programmatic graders for all 3 tasks (TASK-01..05), (2) a layered reward function with 8 components (REW-01..08) in a separate module, and (3) a disruption system that fires mid-episode events (DISR-01..03).

This phase does NOT include inference.py, Dockerfile, or HF deployment — those are Phase 3. The graders must score in [0.0, 1.0] and be deterministic. The reward function must return non-zero intermediate rewards at each step.

</domain>

<decisions>
## Implementation Decisions

### Grader Interface

- **D-01:** Grader reads env state at episode end — signature: `grade(env: WarehouseEnv) -> float`. Called by inference.py after `done=True`. Grader reads `env._episode` internals (fulfilled orders, step count, collision count, etc.) to compute score. No trajectory log needed.
- **D-02:** Each task has its own grader function in `warehouse_env/graders.py`: `grade_solo_delivery`, `grade_coordinated_delivery`, `grade_crisis_management`. A single dispatch `GRADER_REGISTRY: dict[str, Callable] = {task_id: grade_fn}` maps task_id → grader.
- **D-03:** Graders are deterministic — same episode state always returns same score. No randomness.

### Reward Logic Location

- **D-04:** Layered reward lives in `warehouse_env/reward.py`, exported as `calculate_reward(context: RewardContext) -> WarehouseReward`. `step()` in `env.py` calls it. `RewardContext` is a dataclass with all the info reward needs: robot actions, collision set, fulfilled orders this step, late orders, reroutes, step count.
- **D-05:** `WarehouseReward.breakdown` keys: `'delivery'`, `'fast_bonus'`, `'collision'`, `'wasted_step'`, `'late_penalty'`, `'reroute_bonus'`, `'timeout'`. Only non-zero components appear in the breakdown dict.

### Reward Components (REW-01..08)

- **D-06:** REW-01: `+10.0` per order successfully delivered (pick from shelf → drop at packing station matching order).
- **D-07:** REW-02: `+5.0` fast bonus if delivered within `task_config.time_bonus_window` steps from order assignment (already in TaskConfig from Phase 1).
- **D-08:** REW-03: `-8.0` per robot collision (two robots attempt same cell in the same step).
- **D-09:** REW-04: `-1.0` per robot that executes `action_type='wait'`. Wait-only definition — avoids false positives on suboptimal movement.
- **D-10:** REW-05: `-3.0` per order delivered after `time_bonus_window` threshold (late delivery).
- **D-11:** REW-06: `+3.0` per robot that successfully reroutes — detected when robot's previous cell was adjacent to a newly-blocked cell AND robot moved in a direction away from it.
- **D-12:** REW-07: `-10.0` per unfulfilled order when episode ends (`done=True` by max_steps).
- **D-13:** REW-08: Final grader score normalizes cumulative reward to [0.0, 1.0]. The env returns raw step rewards (not normalized) — normalization happens in the grader only.

### Disruption System

- **D-14:** Disruptions fire in `step()` by checking `task_config.disruption_events` against `episode.step_count` (already structured as `[{step, type, params}]` in TaskConfig from Phase 1).
- **D-15:** Disruption handler in `warehouse_env/disruptions.py`, exported as `apply_disruptions(episode: _EpisodeState, task_config: TaskConfig, current_step: int) -> list[str]`. Returns a list of disruption descriptions for the observation's description field. `step()` calls this before computing observations.
- **D-16:** DISR-01 blocked_aisle: sets cells in `params['cells']` to blocked in `grid._blocked`. Robots occupying those cells are moved to adjacent free cells (or stay if no adjacent free cell exists).
- **D-17:** DISR-02 robot_breakdown: sets `robot.is_active = False` for `params['robot_id']`. Broken robot's currently-assigned order returns to the unassigned order queue (set `order.assigned_robot_id = None`). Active robots can pick it up on subsequent steps.
- **D-18:** DISR-03 surge_orders: generates `params['num_orders']` new orders (cycling through shelves/packing stations in TaskConfig pattern) and appends to `episode.orders`.

### Grader Scoring Logic

- **D-19:** `grade_solo_delivery`: `orders_fulfilled / 5`. Pure completion ratio.
- **D-20:** `grade_coordinated_delivery`: `base = orders_fulfilled / 10`. Collision penalty: subtract `0.05 * total_collisions` (capped so score ≥ 0). Return `max(0.0, base - collision_penalty)`.
- **D-21:** `grade_crisis_management`: composite of 3 factors: order completion (weight 0.5), survival time for robots (weight 0.3 — fraction of non-broken robots still active at end), disruption handling (weight 0.2 — whether surge orders were partially fulfilled). All normalized to [0.0, 1.0] before weighting.

### Claude's Discretion

- `RewardContext` exact field names and types — researcher/planner decides what's cleanest
- Whether `reroute_bonus` detection (D-11) uses a simpler heuristic (e.g., robot moved in same step disruption fired) — implementation detail
- `OrderState` fields needed to track `time_bonus_window` (e.g., `assigned_at_step: Optional[int]`) — planner adds what's needed

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 Artifacts (already built)
- `warehouse_env/tasks.py` — TASK_REGISTRY with all 3 TaskConfigs including `disruption_events` and `time_bonus_window`
- `warehouse_env/env.py` — `_EpisodeState`, `WarehouseEnv.step()`, `WarehouseEnv.reset()`, `WarehouseEnv.state()`
- `warehouse_env/models.py` — `WarehouseReward`, `RobotState`, `OrderState`, `WarehouseObservation`
- `warehouse_env/grid.py` — `Grid` with `_blocked` overlay; `set_blocked()`, `is_blocked()` methods

### Project Context
- `.planning/PROJECT.md` — constraints: Pure Python + Pydantic only, programmatic graders only, deadline April 8
- `.planning/REQUIREMENTS.md` — TASK-01..05, REW-01..08, DISR-01..03 requirement IDs for this phase
- `.planning/ROADMAP.md` — Phase 2 success criteria

### Prior Phase Context
- `.planning/phases/01-core-environment/01-CONTEXT.md` — D-01..D-12 decisions locked in Phase 1

</canonical_refs>

<specifics>
## Specific Ideas

- `graders.py` uses `GRADER_REGISTRY: dict[str, Callable[[WarehouseEnv], float]]` for dispatch — matches `TASK_REGISTRY` pattern from Phase 1.
- `disruptions.py` called before observation is built in `step()` so the disruption state is reflected in the observation the LLM sees.
- `OrderState` may need `assigned_at_step: Optional[int]` to detect fast delivery for REW-02 — planner should add this field if not already present.
- Reroute bonus (REW-06) simplest implementation: set a flag `_disrupted_cells_this_step: set[tuple]` in `_EpisodeState`, and if a robot successfully moved adjacent to a disrupted cell this step, award +3.0.

</specifics>

<deferred>
## Deferred Ideas

- Battery/recharge disruption — explicitly cut for deadline (PROJECT.md)
- LLM-based graders — out of scope (PROJECT.md)
- Visualization/rendering — out of scope
- Weighted per-robot grading (tracking individual robot contribution) — post-hackathon enhancement

</deferred>

---

*Phase: 02-tasks-graders-disruptions*
*Context gathered: 2026-04-07 via /gsd:discuss-phase*
