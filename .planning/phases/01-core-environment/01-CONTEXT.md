# Phase 1: Core Environment - Context

**Gathered:** 2026-04-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a Python library — `WarehouseEnv` — that fully implements the OpenEnv spec: typed Pydantic models (`Observation`, `Action`, `Reward`), `step()`/`reset()`/`state()` endpoints, `openenv.yaml`, and `openenv validate` passes. This phase does NOT include tasks, graders, disruptions, or inference.py — those are Phase 2 and 3. The environment must support a configurable grid warehouse with S/R/P/X/. cells and multi-robot agents that can move, pick, and drop.

</domain>

<decisions>
## Implementation Decisions

### Multi-Agent Step API

- **D-01:** `step()` advances **all robots simultaneously** in a single call: `step(actions: list[Action]) -> tuple[Observation, Reward, bool, dict]`. This is the PettingZoo parallel convention — one call per timestep, all robots act together.
- **D-02:** If a robot is not included in the `actions` list, it automatically executes a **wait action** for that step. No error raised for missing robot actions — safe default.
- **D-03:** `actions` is a `list[Action]` (not a dict). Standard JSON-serializable format, easy for LLM to produce.

### Observation Structure

- **D-04:** Grid is exposed as `grid: list[list[str]]` — a 2D array of cell strings. Each cell is one of: `'.'` (free), `'S'` (shelf), `'P'` (packing station), `'X'` (blocked), `'R0'`/`'R1'`/etc. (robot by id).
- **D-05:** Each robot's state is a `RobotState` sub-model: `RobotState(id: int, row: int, col: int, carrying_item: bool, assigned_order_id: Optional[str], is_active: bool)`. Exposed as `robots: list[RobotState]` in the Observation.
- **D-06:** Observation includes a **`description: str`** field — auto-generated natural language summary of the current state (e.g., `"Robot 0 at (2,3) carrying item, assigned to order #2 → packing station P1. Robot 1 idle at (4,1). 3 orders remaining. Step 12/50."`). This dramatically helps the LLM agent pick sensible actions.
- **D-07:** Observation also includes: `order_queue: list[OrderState]`, `step_count: int`, `max_steps: int`, `task_id: str`.

### Task Selection

- **D-08:** Task is selected via `reset()` parameter: `env.reset(task_id='solo_delivery')`. One `WarehouseEnv` class handles all tasks — task configuration loaded from a registry at reset time.
- **D-09:** Default task when `reset()` called with no `task_id`: **`solo_delivery`** (easiest task). Safe for quick testing.
- **D-10:** Task IDs: `'solo_delivery'`, `'coordinated_delivery'`, `'crisis_management'`. Env raises `ValueError` for unknown task IDs.

### Action Model

- **D-11:** `Action(robot_id: int, action_type: str)` — string-based action type, LLM-friendly. Valid values: `'move_up'`, `'move_down'`, `'move_left'`, `'move_right'`, `'pick'`, `'drop'`, `'wait'`. Invalid `action_type` strings are treated as `'wait'` (graceful degradation for LLM output errors).
- **D-12:** `Reward(value: float, breakdown: dict[str, float])` — `value` is the total step reward, `breakdown` shows individual components (e.g., `{'delivery': 10.0, 'collision': -8.0}`).

### Claude's Discretion

- Internal grid data structure (dict[(row,col)->str] vs list[list[str]]) — implementation detail, architecture research recommends dict with separate `_blocked` overlay
- openenv.yaml schema details — research whatever fields `openenv validate` actually requires
- Whether `OrderState` sub-model includes priority, creation_step, deadline fields — Claude decides based on what Phase 2 graders will need

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Context
- `.planning/PROJECT.md` — vision, constraints, key decisions (Pure Python + Pydantic only)
- `.planning/REQUIREMENTS.md` — ENV-01..08, GRID-01..05 requirement IDs for this phase
- `.planning/ROADMAP.md` — Phase 1 success criteria and plan breakdown

### Research Available
- `.planning/research/ARCHITECTURE.md` — Grid representation (dict pattern), step() convention, task registry, episode state management, recommended file layout
- `.planning/research/PITFALLS.md` — openenv.yaml validation requirements, HF Spaces port binding rules, stdout format for inference.py

### OpenEnv Spec (to discover during research/implementation)
- Install `openenv-core` and inspect: exact Pydantic base classes required (if any), `openenv.yaml` required fields, `openenv validate` CLI behavior
- No external spec files exist locally yet — researcher must discover from the package

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no existing code

### Established Patterns
- None yet — this phase establishes the patterns for all subsequent phases

### Integration Points
- `warehouse_env.py` (or `warehouse/` package) will be imported by `inference.py` (Phase 3)
- `WarehouseEnv` will be imported by the FastAPI server (Phase 3)
- Task configs defined here will be consumed by graders in Phase 2

</code_context>

<specifics>
## Specific Ideas

- Architecture research recommends: grid as `dict[(row,col) -> str]` internally with a separate `_blocked` set overlay for disruptions — keeps `reset()` cheap and tests clean. Expose as `list[list[str]]` in the Observation.
- Architecture research recommends: `EpisodeState` as a single dataclass, `reset()` constructs a fresh one from `TaskConfig`, `state()` serializes it.
- The `description` field in Observation should mention: each robot's position, carrying status, assigned order, and any active disruptions.

</specifics>

<deferred>
## Deferred Ideas

- Rendering/visualization — explicitly out of scope (PROJECT.md)
- Battery/recharge disruption — cut for deadline (PROJECT.md)
- LLM-based graders — out of scope (PROJECT.md)
- Multi-agent communication — out of scope (PROJECT.md)

</deferred>

---

*Phase: 01-core-environment*
*Context gathered: 2026-04-07 via discuss-phase*
