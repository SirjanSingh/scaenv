# Architecture Patterns — WarehouseEnv Multi-Agent OpenEnv

**Domain:** Multi-agent grid warehouse benchmark environment
**Researched:** 2026-04-07
**Overall confidence:** HIGH (established Gym/PettingZoo conventions, pure Python — no exotic deps)

---

## Recommended Architecture

### Decision Summary

| Question | Decision | Rationale |
|----------|----------|-----------|
| Grid representation | Pure Python `dict` of `(row, col) -> CellState` | O(1) lookup, no NumPy, trivially serializable to JSON for `state()` |
| Multi-agent step() | All robots advance simultaneously per call | OpenEnv convention mirrors Gym — one `step()` = one world tick |
| Task structure | Task registry: `dict[str, TaskConfig]` + `TaskConfig` dataclass | Decoupled, testable, no subclassing needed |
| Grader inputs | Receives `EpisodeLog` (immutable record of the run) | Grader is a pure function: `EpisodeLog -> float` |
| Episode state | `EpisodeState` dataclass owned by env, mutated in-place | Single source of truth, easy to snapshot for `state()` |
| File layout | Flat `warehouse/` package + root-level API files | Matches OpenEnv expected structure, minimal indirection |

---

## Data Flow Diagram

```
                         ┌─────────────────────────────────────────────┐
                         │                  FastAPI App                 │
                         │  POST /reset   POST /step   GET /state       │
                         └────────────┬──────────┬─────────────────────┘
                                      │          │
                              reset() │          │ step(actions)
                                      ▼          ▼
                         ┌────────────────────────────────┐
                         │         WarehouseEnv           │
                         │  (owns EpisodeState, Grid)     │
                         └──┬──────────┬────────────┬─────┘
                            │          │            │
              ┌─────────────▼──┐  ┌────▼────┐  ┌───▼──────────┐
              │   GridMap      │  │ Robots  │  │ TaskRegistry  │
              │ dict[(r,c)]    │  │ list of │  │ easy/med/hard │
              │ -> CellState   │  │ Robot   │  │ TaskConfig    │
              └────────────────┘  └─────────┘  └──────────────┘
                            │          │
                            └────┬─────┘
                                 │ produces
                                 ▼
                         ┌───────────────┐
                         │  EpisodeLog   │  (append-only event log)
                         └───────┬───────┘
                                 │ passed to
                                 ▼
                         ┌───────────────┐
                         │    Grader     │  -> float 0.0–1.0
                         └───────────────┘
```

---

## Component Boundaries

| Component | File | Responsibility | Communicates With |
|-----------|------|---------------|-------------------|
| `WarehouseEnv` | `warehouse/env.py` | Owns episode state, routes actions, calls disruptions | GridMap, RobotManager, TaskRegistry, Grader |
| `GridMap` | `warehouse/grid.py` | Spatial state: cell types, blocked cells, adjacency | WarehouseEnv (read/write), RobotManager (collision check) |
| `RobotManager` | `warehouse/robots.py` | Robot structs, movement resolution, collision detection | GridMap |
| `TaskRegistry` | `warehouse/tasks.py` | Maps task_id -> TaskConfig (orders, layout, time limit) | WarehouseEnv (at reset) |
| `DisruptionEngine` | `warehouse/disruptions.py` | Probabilistic disruption fire-and-forget side effects | WarehouseEnv, GridMap, RobotManager |
| `Grader` | `warehouse/grader.py` | Pure function: EpisodeLog -> score float | EpisodeLog only |
| `models.py` | `warehouse/models.py` | All Pydantic models (Observation, Action, Reward, etc.) | All components (import only) |
| `app.py` | root | FastAPI app, `/reset` `/step` `/state` routes | WarehouseEnv singleton |
| `inference.py` | root | LLM agent loop, stdout `[START]/[STEP]/[END]` | app.py (via HTTP), OpenAI client |

---

## 1. Grid State Representation

### Decision: `dict[(int, int), str]` cell map

Use a plain Python dictionary mapping `(row, col)` tuples to cell type strings.

```python
# warehouse/grid.py

CELL_FREE    = "."
CELL_SHELF   = "S"
CELL_PACKING = "P"
CELL_BLOCKED = "X"
CELL_ROBOT   = "R"   # overlay — robots are separate, rendered on top

class GridMap:
    def __init__(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        # base layer: static structure (shelves, packing stations, paths)
        self._base: dict[tuple[int, int], str] = {}
        # dynamic overlay: blocked cells added mid-episode
        self._blocked: set[tuple[int, int]] = set()

    def cell_type(self, r: int, c: int) -> str:
        if (r, c) in self._blocked:
            return CELL_BLOCKED
        return self._base.get((r, c), CELL_FREE)

    def is_passable(self, r: int, c: int) -> bool:
        return self.cell_type(r, c) not in (CELL_SHELF, CELL_BLOCKED)

    def block_cell(self, r: int, c: int) -> None:
        self._blocked.add((r, c))

    def to_grid_strings(self) -> list[list[str]]:
        """Renders base map as 2D list for state() serialization."""
        return [
            [self.cell_type(r, c) for c in range(self.cols)]
            for r in range(self.rows)
        ]
```

**Why dict, not list-of-lists:**
- O(1) lookup by coordinate (same as list-of-lists for small grids, but more explicit)
- Sparse representation — only defined cells need entries
- Trivially JSON-serializable (convert keys to strings for output)
- No NumPy import; works identically on any Python 3.10+

**Why two layers (base + blocked):**
- `_base` is set at reset, never mutated — represents warehouse structure
- `_blocked` is the dynamic disruption layer — cleared between episodes
- This separates static configuration from runtime state, making tests trivially clean (build a `GridMap`, block a cell, assert `is_passable`)

---

## 2. Multi-Agent step() — Simultaneous Advancement

### Decision: All robots move in one step() call

```
step(actions: list[Action]) -> StepResult
```

One `step()` advances the world clock by one tick. All robot actions are resolved simultaneously, then disruptions are evaluated, then rewards are computed.

**Why simultaneous (not turn-based):**
- Matches OpenAI Gym / PettingZoo "parallel env" convention
- The OpenEnv spec appears to follow Gym's synchronous parallel model
- LLM agents submit a batch of actions per step; one action per robot
- Simplifies time accounting — step counter == world time
- Turn-based would mean step N only moves robot 0, step N+1 moves robot 1 — produces confusing partial-world states and asymmetric observation sizes

**Collision resolution (simultaneous movement creates swapping conflicts):**

```
Resolution order within a tick:
1. Collect all (robot_id, action) pairs
2. Compute each robot's intended next cell
3. Detect conflicts:
   a. Two robots claiming same target cell → both stay, both pay -1 wasted step
   b. Two robots swapping cells (A->B and B->A) → both stay, both pay -8 collision
   c. Robot moving into shelf/blocked → stays, pays -1 wasted step
4. Apply non-conflicting moves
5. Trigger disruption checks
6. Compute per-robot rewards
7. Return StepResult
```

This is the standard "simultaneous resolution with priority" pattern from multi-agent gridworld literature (MiniGrid, SMAC). No randomness needed — deterministic conflict resolution.

---

## 3. Task Registry Pattern

### Decision: Dict-based registry with `TaskConfig` dataclass

```python
# warehouse/tasks.py

from dataclasses import dataclass, field

@dataclass
class TaskConfig:
    task_id: str
    name: str
    description: str
    grid_rows: int
    grid_cols: int
    num_robots: int
    shelf_positions: list[tuple[int, int]]
    packing_positions: list[tuple[int, int]]
    initial_orders: list[dict]        # [{item_id, shelf_pos, quantity}]
    max_steps: int
    disruption_probability: float     # per-step chance of disruption event
    time_bonus_window: int            # steps within which delivery earns +5

TASK_REGISTRY: dict[str, TaskConfig] = {
    "easy": TaskConfig(
        task_id="easy",
        name="Single Aisle Delivery",
        description="2 robots, 4 shelves, no disruptions, 8x8 grid",
        grid_rows=8, grid_cols=8,
        num_robots=2,
        shelf_positions=[(1,1),(1,3),(1,5),(1,7)],
        packing_positions=[(7,3),(7,5)],
        initial_orders=[...],
        max_steps=100,
        disruption_probability=0.0,
        time_bonus_window=20,
    ),
    "medium": TaskConfig(
        task_id="medium",
        name="Multi-Aisle with Blocked Path",
        description="4 robots, 12 shelves, 1 aisle block mid-episode, 12x12 grid",
        grid_rows=12, grid_cols=12,
        num_robots=4,
        ...
        disruption_probability=0.05,
        ...
    ),
    "hard": TaskConfig(
        task_id="hard",
        name="Surge + Breakdown",
        description="6 robots, 20 shelves, aisle blocks + robot breakdown + surge orders, 16x16",
        grid_rows=16, grid_cols=16,
        num_robots=6,
        ...
        disruption_probability=0.10,
        ...
    ),
}
```

**Why registry (not subclasses):**
- No inheritance overhead — three plain data objects
- `WarehouseEnv.__init__(task_id)` does: `self.config = TASK_REGISTRY[task_id]`
- Testable: tests can construct a `TaskConfig` with minimal fields and inject it
- Adding a new task = add one dict entry, zero code changes elsewhere
- Pydantic-friendly: `TaskConfig` can be validated with `model_validate`

---

## 4. Grader Structure

### Decision: Pure function receiving `EpisodeLog`

The grader is not a class with state. It is a pure function: `grade(log: EpisodeLog, config: TaskConfig) -> float`.

```python
# warehouse/grader.py

from warehouse.models import EpisodeLog, TaskConfig

def grade(log: EpisodeLog, config: TaskConfig) -> float:
    """
    Returns score in [0.0, 1.0].
    Deterministic given same log + config.
    """
    if not log.events:
        return 0.0

    deliveries_made = sum(1 for e in log.events if e.event_type == "delivery")
    total_orders    = len(config.initial_orders)

    if total_orders == 0:
        return 0.0

    # Partial progress: fraction of orders delivered
    completion_ratio = deliveries_made / total_orders

    # Efficiency bonus: reward fewer steps used
    step_efficiency = max(0.0, 1.0 - (log.total_steps / config.max_steps))

    # Collision penalty: each collision shaves score
    collisions = sum(1 for e in log.events if e.event_type == "collision")
    collision_penalty = min(0.3, collisions * 0.02)

    # Weighted score
    score = (
        0.60 * completion_ratio +
        0.25 * step_efficiency +
        0.15 * (1.0 - collision_penalty / 0.3 if collision_penalty > 0 else 1.0)
    )

    return round(max(0.0, min(1.0, score)), 4)
```

**Why pure function, not a method on env:**
- Grader can be tested without running a full episode — pass a synthetic `EpisodeLog`
- Grader is deterministic by construction (no randomness, no env state)
- Judges can audit the grader independently of the environment
- `EpisodeLog` is an append-only record of events (deliveries, collisions, disruptions) accumulated during the episode — the grader reads it after episode ends (at `done=True`)

**`EpisodeLog` structure:**

```python
@dataclass
class EpisodeEvent:
    step: int
    event_type: str      # "delivery" | "collision" | "disruption" | "timeout"
    robot_id: str | None
    data: dict           # event-specific payload

@dataclass
class EpisodeLog:
    task_id: str
    total_steps: int
    events: list[EpisodeEvent]
    final_robot_states: list[dict]
    completed: bool      # True if all orders delivered before timeout
```

**Grader inputs per task tier:**
- Easy: completion_ratio only — did you deliver everything? (high weight)
- Medium: completion_ratio + step_efficiency (disruption adds path cost)
- Hard: all three terms + reroute bonus events logged by DisruptionEngine

---

## 5. Episode State Management

### Decision: Single `EpisodeState` dataclass, owned by env, mutated in-place

```python
# warehouse/env.py (fragment)

@dataclass
class RobotState:
    robot_id: str
    position: tuple[int, int]
    carrying: str | None          # item_id being carried, or None
    broken_down: bool = False
    steps_broken: int = 0

@dataclass
class Order:
    order_id: str
    item_id: str
    shelf_pos: tuple[int, int]
    packing_pos: tuple[int, int]
    status: str                   # "pending" | "picked" | "delivered"
    created_at_step: int

@dataclass
class EpisodeState:
    task_id: str
    step_count: int
    robots: list[RobotState]
    order_queue: list[Order]
    grid: GridMap
    log: EpisodeLog
    done: bool
    rng_seed: int                  # stored so disruptions are reproducible
```

**Why a single `EpisodeState` struct:**
- `reset()` creates a fresh `EpisodeState` from `TaskConfig` — one line of initialization
- `state()` endpoint serializes `EpisodeState` to dict — no hidden state elsewhere
- `step()` mutates `EpisodeState` in-place, appends to `log`
- Tests can freeze a state snapshot (via `copy.deepcopy`) and assert transitions
- No global variables — env holds exactly one `EpisodeState` at a time

**Order lifecycle:**
```
Order created (pending) -> Robot picks item (picked) -> Robot delivers to packing (delivered)
                                                   -> Timeout (still pending/picked -> counted as failed)
```

**Disruption event types and their state mutations:**

| Disruption | Trigger | State Change |
|------------|---------|--------------|
| Blocked aisle | Step N (random in [20, max-20]) | `grid.block_cell(r, c)` for random passable cell |
| Robot breakdown | Step N (random, once per episode) | `robot.broken_down = True`, robot skips all moves for 5 steps |
| Surge orders | Step N (random, hard task only) | Append 2-3 new `Order` objects to `order_queue` |

All disruption events are logged to `EpisodeLog` with step number — grader can see them.

---

## 6. Project File Structure

```
scaenv/                              <- repo root
├── app.py                           <- FastAPI app, /reset /step /state routes
├── inference.py                     <- LLM agent loop, [START]/[STEP]/[END] stdout
├── openenv.yaml                     <- OpenEnv spec metadata file
├── Dockerfile                       <- builds image, exposes port 7860
├── requirements.txt                 <- fastapi, uvicorn, pydantic, openai (only!)
├── README.md                        <- env description, action/obs spaces, task descriptions
│
├── warehouse/                       <- core environment package
│   ├── __init__.py                  <- exports WarehouseEnv
│   ├── env.py                       <- WarehouseEnv class (reset/step/state)
│   ├── grid.py                      <- GridMap, cell constants
│   ├── robots.py                    <- RobotState, RobotManager, movement resolution
│   ├── tasks.py                     <- TaskConfig dataclass, TASK_REGISTRY dict
│   ├── disruptions.py               <- DisruptionEngine, triggers blocked/breakdown/surge
│   ├── grader.py                    <- grade(log, config) -> float
│   └── models.py                    <- all Pydantic models (Observation, Action, Reward, StepResult)
│
└── tests/                           <- pytest tests (not shipped in Docker, used for dev)
    ├── test_grid.py                  <- GridMap unit tests
    ├── test_robots.py                <- collision resolution tests
    ├── test_grader.py                <- grader with synthetic EpisodeLog
    ├── test_tasks.py                 <- TASK_REGISTRY smoke tests
    └── test_env.py                   <- full episode integration tests
```

**File ownership rationale:**

- `app.py` at root — OpenEnv validators may expect the entrypoint at root; FastAPI app is thin (import env, wire routes)
- `inference.py` at root — hackathon spec requires it at root
- `warehouse/` package — everything testable lives here; `app.py` is just the HTTP shell
- `models.py` imported by everything — placing it in `warehouse/` avoids circular imports (app.py imports models from warehouse.models, not from itself)
- `tests/` excluded from Docker via `.dockerignore` — keeps image lean

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Storing Robot Positions in the Grid

**What:** Writing `"R"` into the grid dict when a robot moves there.
**Why bad:** Grid becomes the source of truth for robot state. Robot-grid sync bugs are silent (robot dict says position A, grid says robot is at B). Makes collision detection a grid-scan instead of a robot-list scan.
**Instead:** Grid stores only static structure. Robots maintain their own `position` field. Rendering overlays robot positions on top of grid at serialization time only.

### Anti-Pattern 2: One step() Per Robot (Turn-Based)

**What:** `step(robot_id, action)` — advance one robot at a time.
**Why bad:** Observation size changes each call (which robot's turn?). LLM agent must track whose turn it is. Mismatches OpenEnv/Gym parallel model. Episode length measurement becomes ambiguous.
**Instead:** `step(actions: list[Action])` where `len(actions) == num_robots`. Missing actions default to `STAY`.

### Anti-Pattern 3: Grader Reading from Live Env State

**What:** `grader.grade(env)` — grader inspects the running environment.
**Why bad:** Grader can only run at episode end. Can't be unit-tested without a full episode. Env mutation could affect scoring mid-call.
**Instead:** Grader reads `EpisodeLog` — an immutable snapshot built up during the episode and frozen at done=True.

### Anti-Pattern 4: TaskConfig as Subclass

**What:** `class EasyTask(BaseTask)`, `class HardTask(BaseTask)`.
**Why bad:** Inheritance for configuration is over-engineering. Any task-specific logic bleeds into the class, making tests harder and diffs larger.
**Instead:** `TASK_REGISTRY["easy"]` returns a plain `TaskConfig` dataclass. All task-specific behavior is in the data, not in code branches.

### Anti-Pattern 5: Global Env State (module-level singleton)

**What:** `env = WarehouseEnv()` at module level in `app.py`.
**Why bad:** Tests can't instantiate a fresh env per test; state leaks between test runs.
**Instead:** Use FastAPI's `lifespan` or a dependency-injected `get_env()` function that returns the app-level instance. Tests construct `WarehouseEnv` directly.

---

## Pydantic Models — Key Shapes

```python
# warehouse/models.py (reference shapes)

class ActionType(str, Enum):
    MOVE_UP    = "move_up"
    MOVE_DOWN  = "move_down"
    MOVE_LEFT  = "move_left"
    MOVE_RIGHT = "move_right"
    PICK       = "pick"
    DELIVER    = "deliver"
    STAY       = "stay"

class RobotAction(BaseModel):
    robot_id: str
    action: ActionType

class StepRequest(BaseModel):
    actions: list[RobotAction]

class RobotObservation(BaseModel):
    robot_id: str
    position: tuple[int, int]
    carrying: str | None
    broken_down: bool

class Observation(BaseModel):
    step: int
    grid: list[list[str]]          # rendered grid with robots overlaid
    robots: list[RobotObservation]
    orders: list[dict]             # serialized Order list
    disruptions: list[str]         # active disruption descriptions

class RewardBreakdown(BaseModel):
    delivery: float = 0.0
    fast_bonus: float = 0.0
    collision: float = 0.0
    wasted_step: float = 0.0
    late_penalty: float = 0.0
    reroute_bonus: float = 0.0
    timeout: float = 0.0

class StepResult(BaseModel):
    observation: Observation
    rewards: dict[str, RewardBreakdown]   # robot_id -> breakdown
    done: bool
    info: dict                             # task_id, score if done
```

---

## Scalability Considerations

This is a hackathon benchmark, not production. But design choices that keep it clean under judge scrutiny:

| Concern | At demo scale (2-6 robots, ≤16x16) | What would break at scale |
|---------|-------------------------------------|--------------------------|
| Grid lookup | O(1) dict — fine | Dict overhead vs NumPy array at 1000x1000 |
| Collision detection | O(n^2) robot pairs — fine for n<=6 | Would need spatial index at n>50 |
| Disruption timing | Random.seed per episode — reproducible | Fine |
| Episode log | Append-only list — fine | Memory at 100k+ steps |

All concerns are irrelevant at hackathon scale. Document the limits so judges see you thought about it.

---

## Sources

- OpenAI Gym API spec (synchronous step convention): https://gymnasium.farama.org/api/env/
- PettingZoo parallel env API (simultaneous multi-agent step): https://pettingzoo.farama.org/api/parallel/
- MiniGrid environment structure (grid dict pattern, overlay rendering): https://github.com/Farama-Foundation/MiniGrid
- Python dataclass-based state management: standard library, Python 3.10+
- Confidence: HIGH for all patterns above — well-established conventions with multiple reference implementations
