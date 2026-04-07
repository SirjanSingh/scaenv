# Phase 1: Core Environment - Research

**Researched:** 2026-04-07
**Domain:** OpenEnv spec compliance, Python Pydantic environment, warehouse grid simulation
**Confidence:** HIGH (openenv-core 0.2.3 installed and inspected directly; all claims verified from source)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `step()` advances all robots simultaneously: `step(actions: list[Action]) -> tuple[Observation, Reward, bool, dict]` (PettingZoo parallel convention)
- **D-02:** If a robot is not in the `actions` list it automatically executes a wait action. No error raised.
- **D-03:** `actions` is a `list[Action]` (not a dict). Standard JSON-serializable format.
- **D-04:** Grid exposed as `grid: list[list[str]]` — cells: `'.'`, `'S'`, `'P'`, `'X'`, `'R0'`/`'R1'`/etc.
- **D-05:** `RobotState(id: int, row: int, col: int, carrying_item: bool, assigned_order_id: Optional[str], is_active: bool)`
- **D-06:** Observation includes `description: str` — auto-generated natural language summary
- **D-07:** Observation includes `order_queue: list[OrderState]`, `step_count: int`, `max_steps: int`, `task_id: str`
- **D-08:** Task selected via `reset(task_id='solo_delivery')`. One `WarehouseEnv` class handles all tasks.
- **D-09:** Default task: `'solo_delivery'`. Raises `ValueError` for unknown task IDs.
- **D-10:** Task IDs: `'solo_delivery'`, `'coordinated_delivery'`, `'crisis_management'`
- **D-11:** `Action(robot_id: int, action_type: str)` — string actions. Invalid types treated as `'wait'`.
- **D-12:** `Reward(value: float, breakdown: dict[str, float])`
- Pure Python + Pydantic only (no NumPy, no heavy deps)

### Claude's Discretion

- Internal grid data structure (dict[(row,col)->str] vs list[list[str]]) — architecture research recommends dict with separate `_blocked` overlay
- `openenv.yaml` schema details — research whatever fields `openenv validate` actually requires
- Whether `OrderState` sub-model includes priority, creation_step, deadline fields — Claude decides based on what Phase 2 graders will need

### Deferred Ideas (OUT OF SCOPE)

- Rendering/visualization
- Battery/recharge disruption
- LLM-based graders
- Multi-agent communication
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ENV-01 | `WarehouseEnv` implements `step(action)` → `(observation, reward, done, info)` | OpenEnv `Environment` ABC: `step(action, **kwargs) -> ObsT`. Env must inherit from `Environment` base class. |
| ENV-02 | `WarehouseEnv` implements `reset()` → initial `Observation` | OpenEnv `reset(seed, episode_id, **kwargs) -> ObsT`. task_id passed as extra kwarg via ResetRequest extra=allow. |
| ENV-03 | `WarehouseEnv` implements `state()` → current full state dict | OpenEnv uses `@property state -> StateT`. Must return a `State` subclass (not a plain dict). |
| ENV-04 | `Observation` is a typed Pydantic model | Must subclass `openenv.core.env_server.types.Observation`. Adds `done`, `reward`, `metadata` fields automatically. |
| ENV-05 | `Action` is a typed Pydantic model | Must subclass `openenv.core.env_server.types.Action`. Adds `metadata` field automatically. |
| ENV-06 | `Reward` is a typed Pydantic model | NOT an OpenEnv base class. Define as plain Pydantic `BaseModel`. Returned in `metadata` dict of Observation. |
| ENV-07 | `openenv.yaml` present with required fields | Minimal: `spec_version`, `name`, `type`, `runtime`, `app`, `port`. `openenv validate` checks file presence only. |
| ENV-08 | `openenv validate` passes without errors | Requires: `openenv.yaml`, `pyproject.toml` with correct scripts section, `server/app.py` with `main()` function, `uv.lock` |
| GRID-01 | Grid supports S/R/P/X/. cell types | Internal dict; R-cells overlaid at serialization. Verified pattern from architecture research. |
| GRID-02 | 6 action types: move_up/down/left/right, pick, drop | Enum + dispatch table in `WarehouseEnv.step()`. |
| GRID-03 | Collision detection — two robots cannot share a cell | Simultaneous resolution: collect intents, detect conflicts, apply non-conflicting moves. |
| GRID-04 | Order queue: shelf→packing station flow | `Order` dataclass; robots pick from shelf (must be adjacent), drop at packing station (must be adjacent). |
| GRID-05 | Episode ends when all orders fulfilled OR max_steps reached | `done` field on Observation set True; `EpisodeLog` records completion status. |
</phase_requirements>

---

## Summary

OpenEnv 0.2.3 uses a specific directory structure that differs substantially from a bare FastAPI project. The validator (`openenv validate`) requires: `openenv.yaml` at the env root, `pyproject.toml` with a `[project.scripts]` `server` entry point referencing a `main()` function, `server/app.py` containing that `main()`, and a `uv.lock` file. The `openenv.yaml` itself is only checked for existence — its fields are not schema-validated by the local validator. Runtime validation (via `openenv validate --url`) tests five additional HTTP endpoints: `/openapi.json`, `/health`, `/metadata`, `/schema`, and `/mcp`.

The core design insight: OpenEnv provides base classes (`Environment`, `Action`, `Observation`, `State`) that `WarehouseEnv` must inherit from. The framework's `create_app()` factory wires all HTTP routes automatically. Our custom `WarehouseEnvironment` needs to implement only three methods: `reset()`, `step()`, and `state` property. The `action` parameter to `step()` is deserialized automatically from the HTTP request body before reaching our code.

The critical mismatch with the user's API decisions (D-01 to D-12): OpenEnv's `step(action)` takes a single `Action` object, not a `list[Action]`. To support multi-robot simultaneous actions, we define our `WarehouseAction` with a `robots: list[RobotAction]` field (a list of per-robot actions in one action object). This satisfies both the user's parallel-step intention and the OpenEnv single-action-per-step contract.

**Primary recommendation:** Use `openenv init warehouse_env` to scaffold the exact required structure, then replace the echo environment with the warehouse implementation. Wire with `create_app(WarehouseEnvironment, WarehouseAction, WarehouseObservation)` — all routes are provided by the framework.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| openenv-core | 0.2.3 (latest) | Base classes + HTTP server framework | Required by spec; provides `Environment`, `Action`, `Observation`, `State`, `create_app()` |
| pydantic | 2.12.5 | Model validation and serialization | Transitive dep of openenv-core; required for all models |
| fastapi | 0.135.1 | HTTP server (provided via openenv-core) | Wired by `create_app()`; do not instantiate directly |
| uvicorn | 0.41.0 | ASGI server | Required by openenv template; invoked in `main()` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| uv | 0.11.1 | Dependency lock file generation | Required: `openenv validate` checks for `uv.lock` |
| pytest | latest | Unit testing | Development only; excluded from Docker |

**Installation:**
```bash
pip install "openenv-core[core]>=0.2.3"
# Or for the project structure:
uv init warehouse_env && uv add "openenv-core[core]>=0.2.3"
```

**Version verification (confirmed 2026-04-07):**
- openenv-core: 0.2.3
- pydantic: 2.12.5
- fastapi: 0.135.1
- uvicorn: 0.41.0
- uv: 0.11.1 (must be on PATH for `openenv validate` to generate/find uv.lock)

---

## Architecture Patterns

### Required Project Structure

`openenv validate` enforces this layout exactly. Deviation breaks validation.

```
warehouse_env/                       <- env root (openenv validate runs here)
├── openenv.yaml                     <- spec metadata (checked for existence)
├── pyproject.toml                   <- REQUIRED: must have [project.scripts] server entry
├── uv.lock                          <- REQUIRED: generated by `uv lock`
├── README.md                        <- HF Spaces YAML header goes here
├── models.py                        <- WarehouseAction, WarehouseObservation
├── __init__.py                      <- exports (optional but conventional)
│
├── server/                          <- server subdirectory (hardcoded in validator)
│   ├── app.py                       <- REQUIRED: must contain def main()
│   ├── warehouse_environment.py     <- WarehouseEnvironment class
│   ├── Dockerfile                   <- for HF Spaces deployment
│   └── __init__.py
│
├── warehouse/                       <- internal simulation package
│   ├── __init__.py
│   ├── grid.py                      <- GridMap, cell constants
│   ├── robots.py                    <- RobotManager, collision resolution
│   ├── tasks.py                     <- TaskConfig, TASK_REGISTRY
│   └── episode.py                   <- EpisodeState, Order dataclasses
│
└── tests/                           <- pytest (excluded from Docker)
    ├── test_grid.py
    ├── test_robots.py
    └── test_env.py
```

### Pattern 1: Inheriting from OpenEnv Base Classes

**What:** `WarehouseEnvironment` inherits `Environment[WarehouseAction, WarehouseObservation, WarehouseState]`. `WarehouseAction` inherits `Action`. `WarehouseObservation` inherits `Observation`. `WarehouseState` inherits `State`.

**When to use:** Always — `openenv validate --url` checks that `/schema` returns schemas for action/observation/state. The framework derives these automatically from your Pydantic subclasses.

```python
# Source: openenv/core/env_server/types.py (inspected directly)
from openenv.core.env_server.types import Action, Observation, State
from openenv.core.env_server.interfaces import Environment
from pydantic import Field
from typing import Optional

# --- Action ---
class RobotAction(Action):
    """Single robot's action — NOT the top-level action sent to step()."""
    robot_id: int = Field(..., description="Robot ID (0-indexed)")
    action_type: str = Field(..., description="move_up|move_down|move_left|move_right|pick|drop|wait")

class WarehouseAction(Action):
    """Multi-robot action batch — ONE of these per step() call."""
    robots: list[RobotAction] = Field(default_factory=list,
        description="Actions for each robot. Missing robots get 'wait'.")

# --- Observation ---
class RobotState(BaseModel):
    id: int
    row: int
    col: int
    carrying_item: bool
    assigned_order_id: Optional[str]
    is_active: bool

class WarehouseObservation(Observation):
    # Observation base provides: done: bool, reward: float|None, metadata: dict
    grid: list[list[str]] = Field(..., description="2D grid; R0/R1/S/P/X/.")
    robots: list[RobotState] = Field(...)
    order_queue: list[dict] = Field(default_factory=list)
    step_count: int = Field(default=0)
    max_steps: int = Field(default=50)
    task_id: str = Field(default="solo_delivery")
    description: str = Field(default="")

# --- State (for /state endpoint) ---
class WarehouseState(State):
    # State base provides: episode_id: str|None, step_count: int
    task_id: str = Field(default="")
    grid: list[list[str]] = Field(default_factory=list)
    robots: list[dict] = Field(default_factory=list)
    orders: list[dict] = Field(default_factory=list)
    done: bool = Field(default=False)
```

### Pattern 2: Environment Implementation

**What:** Three required methods. `state` is a property (not a method). `reset()` accepts `**kwargs` so `task_id` flows through from the HTTP ResetRequest.

```python
# Source: openenv/core/env_server/interfaces.py (inspected directly)
class WarehouseEnvironment(Environment[WarehouseAction, WarehouseObservation, WarehouseState]):

    SUPPORTS_CONCURRENT_SESSIONS: bool = False  # single-env HTTP mode

    def __init__(self):
        super().__init__()
        self._episode: Optional[EpisodeState] = None

    def reset(self, seed: Optional[int] = None, episode_id: Optional[str] = None,
              task_id: str = "solo_delivery", **kwargs) -> WarehouseObservation:
        # task_id flows in from POST /reset body because ResetRequest has extra="allow"
        if task_id not in TASK_REGISTRY:
            raise ValueError(f"Unknown task_id: {task_id!r}")
        config = TASK_REGISTRY[task_id]
        self._episode = EpisodeState.from_config(config)
        return self._make_observation()

    def step(self, action: WarehouseAction, **kwargs) -> WarehouseObservation:
        # action is already deserialized by openenv framework
        if self._episode is None or self._episode.done:
            raise RuntimeError("Call reset() before step()")
        reward = self._episode.advance(action.robots)
        obs = self._make_observation()
        obs.reward = reward.value
        obs.done = self._episode.done
        return obs

    @property
    def state(self) -> WarehouseState:
        # Returns WarehouseState (State subclass), not a plain dict
        if self._episode is None:
            return WarehouseState()
        return WarehouseState(
            episode_id=str(id(self._episode)),
            step_count=self._episode.step_count,
            task_id=self._episode.task_id,
            grid=self._episode.grid.to_grid_strings(),
            robots=[r.to_dict() for r in self._episode.robots],
            orders=[o.to_dict() for o in self._episode.orders],
            done=self._episode.done,
        )
```

### Pattern 3: HTTP Server Wiring (`server/app.py`)

**What:** Use `create_app()` factory. This is the only file `openenv validate` inspects for the `main()` function.

```python
# Source: openenv/cli/templates/openenv_env/server/app.py (template inspected directly)
from openenv.core.env_server.http_server import create_app
from models import WarehouseAction, WarehouseObservation
from server.warehouse_environment import WarehouseEnvironment

app = create_app(
    WarehouseEnvironment,      # class (factory pattern), NOT an instance
    WarehouseAction,
    WarehouseObservation,
    env_name="warehouse_env",
    max_concurrent_envs=1,
)

def main(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main()
```

### Pattern 4: Required pyproject.toml

`openenv validate` checks: (1) `pyproject.toml` exists, (2) `[project.scripts]` has `server` key, (3) server value contains `:main`, (4) `openenv-core>=0.2.0` or `openenv>=0.2.0` is in dependencies.

```toml
[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "openenv-warehouse-env"
version = "0.1.0"
description = "Multi-robot warehouse environment for OpenEnv"
requires-python = ">=3.10"
dependencies = [
    "openenv-core[core]>=0.2.3",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0"]

[project.scripts]
server = "warehouse_env.server.app:main"

[tool.setuptools]
include-package-data = true
packages = ["warehouse_env", "warehouse_env.server"]
package-dir = { "warehouse_env" = ".", "warehouse_env.server" = "server" }
```

### Pattern 5: openenv.yaml (minimal passing format)

`openenv validate` only checks file existence, not field content. But use the canonical template format:

```yaml
spec_version: 1
name: warehouse_env
type: space
runtime: fastapi
app: server.app:app
port: 8000
```

### Pattern 6: task_id Flow Through HTTP Layer

`ResetRequest` has `extra="allow"` in its model config. This means arbitrary extra fields sent to `POST /reset` are included in `kwargs` dumped to the env's `reset()`. Our `reset()` method must accept `task_id: str = "solo_delivery"` as a keyword argument.

```python
# HTTP client sends:
# POST /reset
# {"task_id": "coordinated_delivery"}

# Framework calls:
# env.reset(task_id="coordinated_delivery")

# Because ResetRequest.model_config = ConfigDict(extra="allow")
# and framework does: kwargs = request.model_dump(exclude_unset=True)
# then: env.reset(**kwargs)
```

### Pattern 7: Reward Reporting

OpenEnv's `Observation` base has a `reward: bool | int | float | None` field. The `serialize_observation()` utility extracts `reward` and `done` from the observation and puts them at the top level of the HTTP response. The `Reward(value, breakdown)` model from user decision D-12 should be included in `metadata` dict of the Observation (not as a separate return value). The HTTP step response is always `{observation: {...}, reward: float|None, done: bool}`.

The user's decision D-01 specifies `step() -> tuple[Observation, Reward, bool, dict]`. This is the Python API contract for internal/testing use. The HTTP API uses OpenEnv's wire format which puts reward at the top level. We satisfy both by: (a) internal `step()` sets `obs.reward = reward.value` and stores `reward.breakdown` in `obs.metadata["reward_breakdown"]`, (b) the HTTP layer auto-extracts `obs.reward` for the wire format.

### Anti-Patterns to Avoid

- **Returning `State` as a plain dict from `state` property:** The framework expects a `State` subclass instance. Plain dicts will fail type checking and break the `/state` endpoint's `response_model`.
- **Passing an env instance to `create_app()`:** Must pass the class (factory pattern), not `WarehouseEnvironment()`. The framework calls the class to create new instances per-request.
- **Router prefix on endpoints:** `create_app()` registers all routes at root. Do not add APIRouter with prefix — it would double the path.
- **Missing `main()` in server/app.py:** `openenv validate` scans for `def main(` literal string. The function must be named exactly `main`.
- **Missing `if __name__ == "__main__"` guard calling `main()`:** The validator also checks for both `__name__` and `main()` occurrence in the file.
- **Using `extra="forbid"` on Action subclass:** `Action` base already has `extra="forbid"`. Do not override with `extra="allow"` unless intentional. Custom fields must be explicitly declared.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP server with /reset /step /state /health /schema /mcp /ws | Custom FastAPI routes | `create_app()` from openenv-core | Framework provides all 8+ endpoints, OpenAPI docs, WebSocket support, MCP protocol |
| Action/Observation serialization | Custom JSON encoder | `serialize_observation()` internal to framework | Framework handles `reward`/`done` extraction, `model_dump()` |
| Action deserialization from HTTP body | Manual dict->model mapping | `deserialize_action()` internal to framework | Framework validates, raises HTTP 422 on bad input |
| Schema endpoint | Custom schema generation | Automatic via Pydantic model JSON schemas | Framework generates `/schema` from your model classes |
| Health endpoint | Custom health check | Automatic via `create_app()` | Framework registers GET /health → `{"status": "healthy"}` |

**Key insight:** Implementing custom FastAPI routes for reset/step/state bypasses the framework's MCP layer, WebSocket support, and schema introspection. The entire HTTP layer is provided — only implement `Environment` subclass methods.

---

## Common Pitfalls

### Pitfall 1: `openenv validate` Requires `uv.lock`

**What goes wrong:** `openenv validate` reports "Missing uv.lock" even if all other files are present, blocking validation pass.

**Why it happens:** The validator explicitly checks for `uv.lock` file in the environment root. pip-based projects without uv tooling miss this.

**How to avoid:** Run `uv lock` from the environment directory after creating `pyproject.toml`. This generates `uv.lock` from declared dependencies. Commit `uv.lock` to git.

**Warning signs:** Validation output contains "Missing uv.lock - run 'uv lock' to generate it".

### Pitfall 2: `server/app.py` Must Contain Literal `def main(` AND `main()` Call

**What goes wrong:** Validator scans `server/app.py` for the string `def main(` — if the function is named differently or is in a different file, validation fails.

**Why it happens:** Validator uses string matching, not AST parsing. The check is: `"def main(" in app_content` AND `("__name__" in app_content and "main()" in app_content)`.

**How to avoid:** Put the `main()` function in `server/app.py`. Include `if __name__ == "__main__": main()`. Do not rename or move this function.

### Pitfall 3: `state` Is a Property, Not a Method

**What goes wrong:** Defining `def state(self) -> dict` as a regular method instead of `@property`. The `Environment` ABC declares `state` as `@property @abstractmethod`. Calling `env.state()` raises TypeError.

**Why it happens:** The original user API spec says `state()` endpoint — this is the HTTP endpoint path `/state`, not a Python method call with parentheses.

**How to avoid:** Always use `@property` decorator. The HTTP route at `/state` calls `env.state` (no parens) internally.

### Pitfall 4: Action's `extra="forbid"` Rejects Unknown Fields

**What goes wrong:** Sending `{"robot_id": 0, "action_type": "move_up", "extra_field": "x"}` raises a 422 error from Pydantic's validation.

**Why it happens:** The base `Action` class has `model_config = ConfigDict(extra="forbid")`. LLMs may produce extra fields.

**How to avoid:** Our `WarehouseAction` can override `model_config` if needed, or document the exact expected schema clearly. For LLM robustness, consider `extra="ignore"`.

### Pitfall 5: HTTP `step()` Creates a Fresh Env Instance Per Request

**What goes wrong:** `POST /reset` sets up episode state, then `POST /step` uses a freshly created `WarehouseEnvironment()` with no episode state — causing `None` episode error.

**Why it happens:** The `reset_handler` in `http_server.py` calls `_env = self._env_factory()`, uses it, then calls `_env.close()`. Same pattern for `step_handler`. The env instance is not persisted between requests in simulation mode when using the default single-env approach.

**How to avoid:** The framework maintains state for WebSocket sessions but NOT between separate HTTP reset/step calls. For the demo/hackathon use case, redesign to keep env state in the server singleton. Override `create_app()` pattern or use a module-level env singleton:

```python
# In server/app.py — persistent singleton approach
_env_instance = WarehouseEnvironment()

app = create_app(
    lambda: _env_instance,  # factory returns singleton, not new instance
    WarehouseAction,
    WarehouseObservation,
    env_name="warehouse_env",
)
```

This is the recommended approach for the hackathon — simple, stateful, single-user.

**Warning signs:** `env.step()` raises "Call reset() before step()" because `_episode` is `None` on every HTTP request.

### Pitfall 6: `ResetResponse` Wraps Observation in a Nested Dict

**What goes wrong:** HTTP `/reset` response is `{"observation": {...}, "reward": null, "done": false}` — the observation fields are nested under `"observation"` key, not at top level.

**Why it happens:** `ResetResponse` and `StepResponse` have an `observation: Dict[str, Any]` field that wraps the serialized observation.

**How to avoid:** When writing the `inference.py` client or any direct HTTP consumer, access `response["observation"]["grid"]`, not `response["grid"]`. This is the correct wire format.

---

## Code Examples

### Complete Minimal WarehouseEnvironment

```python
# server/warehouse_environment.py
from uuid import uuid4
from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State
from models import WarehouseAction, WarehouseObservation
from warehouse.tasks import TASK_REGISTRY
from warehouse.episode import EpisodeState

class WarehouseEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS: bool = False

    def __init__(self):
        super().__init__()
        self._episode: EpisodeState | None = None

    def reset(self, seed=None, episode_id=None, task_id="solo_delivery", **kwargs):
        if task_id not in TASK_REGISTRY:
            raise ValueError(f"Unknown task_id: {task_id!r}. Valid: {list(TASK_REGISTRY)}")
        config = TASK_REGISTRY[task_id]
        self._episode = EpisodeState.from_config(config, episode_id=episode_id or str(uuid4()))
        return self._build_observation()

    def step(self, action: WarehouseAction, **kwargs):
        if self._episode is None:
            raise RuntimeError("reset() must be called before step()")
        reward_obj = self._episode.advance(action.robots)
        obs = self._build_observation()
        obs.reward = reward_obj.value
        obs.done = self._episode.done
        obs.metadata["reward_breakdown"] = reward_obj.breakdown
        return obs

    @property
    def state(self):
        if self._episode is None:
            return State(episode_id=None, step_count=0)
        ep = self._episode
        from warehouse.models import WarehouseState
        return WarehouseState(
            episode_id=ep.episode_id,
            step_count=ep.step_count,
            task_id=ep.task_id,
            grid=ep.grid.to_grid_strings(ep.robots),
            robots=[r.to_dict() for r in ep.robots],
            orders=[o.to_dict() for o in ep.orders],
            done=ep.done,
        )

    def _build_observation(self) -> WarehouseObservation:
        ep = self._episode
        return WarehouseObservation(
            grid=ep.grid.to_grid_strings(ep.robots),
            robots=[r.to_robot_state() for r in ep.robots],
            order_queue=[o.to_order_state() for o in ep.orders if o.status != "delivered"],
            step_count=ep.step_count,
            max_steps=ep.max_steps,
            task_id=ep.task_id,
            description=ep.describe(),
            done=ep.done,
            reward=None,
        )
```

### Simultaneous Multi-Robot Step Resolution

```python
# warehouse/episode.py
def advance(self, robot_actions: list[RobotAction]) -> RewardObj:
    """Advance all robots simultaneously. Missing robots get 'wait'."""
    # Build action map with defaults
    action_map = {r.robot_id: "wait" for r in self.robots}
    for ra in robot_actions:
        atype = ra.action_type if ra.action_type in VALID_ACTIONS else "wait"
        action_map[ra.robot_id] = atype

    # Phase 1: Compute intended next positions
    intents: dict[int, tuple[int, int]] = {}
    for robot in self.robots:
        if not robot.is_active:
            intents[robot.id] = (robot.row, robot.col)
            continue
        atype = action_map.get(robot.id, "wait")
        intents[robot.id] = self._compute_intent(robot, atype)

    # Phase 2: Conflict detection
    position_claims: dict[tuple[int,int], list[int]] = {}
    for rid, pos in intents.items():
        position_claims.setdefault(pos, []).append(rid)

    # Phase 3: Apply moves
    reward = RewardObj()
    for robot in self.robots:
        target = intents[robot.id]
        claimants = position_claims[target]
        if len(claimants) > 1:
            # Collision — all claimants stay in place
            reward.add_collision()
        else:
            robot.row, robot.col = target

    # Phase 4: Handle pick/drop for non-conflicting robots
    for robot in self.robots:
        atype = action_map.get(robot.id, "wait")
        if atype == "pick":
            reward.add(self._try_pick(robot))
        elif atype == "drop":
            reward.add(self._try_drop(robot))

    self.step_count += 1
    self.done = self._check_done()
    return reward
```

### Grid Serialization with Robot Overlay

```python
# warehouse/grid.py
def to_grid_strings(self, robots: list[Robot]) -> list[list[str]]:
    """Render grid as 2D list with robots overlaid."""
    # Start from base cell map
    grid = [[self.cell_type(r, c) for c in range(self.cols)]
            for r in range(self.rows)]
    # Overlay active robots (R0, R1, ...)
    for robot in robots:
        if robot.is_active:
            grid[robot.row][robot.col] = f"R{robot.id}"
    return grid
```

### openenv.yaml (minimal passing)

```yaml
spec_version: 1
name: warehouse_env
type: space
runtime: fastapi
app: server.app:app
port: 8000
```

### README.md HF Spaces Header

```yaml
---
title: Warehouse Env
emoji: 🏭
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
---
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| openenv-core as separate package | `openenv` package with `openenv.core` namespace | v0.2.3 | Import from `openenv.core.env_server.types`, not `openenv_core`. The `openenv_core` namespace still works but shows DeprecationWarning. |
| Manual FastAPI routes | `create_app()` factory wraps everything | v0.2.x | Do not write `/reset`, `/step`, `/state` routes manually. |
| requirements.txt only | `pyproject.toml` + `uv.lock` | v0.2.3 | `openenv validate` requires pyproject.toml and uv.lock. requirements.txt alone fails validation. |
| Port 8000 | Port 8000 (template default) | current | Template uses 8000, not 7860. HF Spaces README must have `app_port: 8000`. |

**Deprecated/outdated:**
- `openenv_core` import namespace: deprecated, use `openenv.core` instead
- Direct dict returns from `state()`: must return a `State` subclass

---

## Open Questions

1. **Step response wire format vs. user's tuple API**
   - What we know: OpenEnv HTTP wire is `{observation: {...}, reward: float, done: bool}`. User spec D-01 says tuple `(Observation, Reward, bool, dict)`.
   - What's unclear: The user's tuple API is for internal/testing use only (direct Python). HTTP clients get the wire format. `inference.py` in Phase 3 will use HTTP.
   - Recommendation: Implement `step()` to return `WarehouseObservation` (with `reward`, `done` set). Keep internal `_step_logic()` that returns the tuple for Python-only callers if needed. The HTTP layer handles the rest.

2. **Singleton vs. per-request env instance**
   - What we know: `create_app()` calls `_env_factory()` on every `/reset` and `/step` HTTP request (confirmed in source). State does NOT persist between HTTP requests unless you use the singleton pattern.
   - What's unclear: Whether the hackathon judges use WebSocket (stateful) or HTTP (per-request).
   - Recommendation: Use module-level singleton env: `lambda: _env_instance`. Simple and correct for single-user hackathon use.

3. **OrderState fields for Phase 2 graders**
   - What we know: CONTEXT.md leaves field selection to Claude's discretion. Phase 2 needs delivery tracking.
   - Recommendation: Include `order_id: str`, `shelf_pos: tuple[int,int]`, `packing_pos: tuple[int,int]`, `status: str` ("pending"|"picked"|"delivered"), `created_at_step: int`, `assigned_robot_id: Optional[int]`. Deadline and priority can be added in Phase 2.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | Runtime | Yes | 3.13.2 | — |
| openenv-core | ENV-08 | Yes | 0.2.3 | — |
| pydantic | ENV-04/05/06 | Yes | 2.12.5 | — |
| fastapi | HTTP server | Yes | 0.135.1 (via openenv-core) | — |
| uvicorn | HTTP server | Yes | 0.41.0 (via openenv-core) | — |
| uv | `openenv validate` uv.lock | Yes | 0.11.1 | — |
| pytest | Testing | Available via pip install | latest | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (not yet installed) |
| Config file | `pyproject.toml` [tool.pytest.ini_options] — Wave 0 |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENV-01 | `step(actions)` returns obs with correct types | unit | `pytest tests/test_env.py::test_step_returns_observation -x` | Wave 0 |
| ENV-02 | `reset(task_id=...)` returns WarehouseObservation | unit | `pytest tests/test_env.py::test_reset_returns_observation -x` | Wave 0 |
| ENV-03 | `state` property returns WarehouseState (State subclass) | unit | `pytest tests/test_env.py::test_state_returns_state_subclass -x` | Wave 0 |
| ENV-04 | Observation is Pydantic BaseModel subclass | unit | `pytest tests/test_models.py::test_observation_is_basemodel -x` | Wave 0 |
| ENV-05 | Action is Pydantic BaseModel subclass | unit | `pytest tests/test_models.py::test_action_is_basemodel -x` | Wave 0 |
| ENV-06 | Reward model has value:float and breakdown:dict | unit | `pytest tests/test_models.py::test_reward_model -x` | Wave 0 |
| ENV-07 | openenv.yaml exists | file check | `pytest tests/test_validate.py::test_openenv_yaml_exists -x` | Wave 0 |
| ENV-08 | `openenv validate` passes | integration | `pytest tests/test_validate.py::test_openenv_validate_passes -x` | Wave 0 |
| GRID-01 | Grid initializes with S/R/P/X/. cells | unit | `pytest tests/test_grid.py::test_cell_types -x` | Wave 0 |
| GRID-02 | All 6 action types are handled | unit | `pytest tests/test_robots.py::test_all_action_types -x` | Wave 0 |
| GRID-03 | Two robots colliding stay put and get penalty | unit | `pytest tests/test_robots.py::test_collision_detection -x` | Wave 0 |
| GRID-04 | Robot pick→drop flow completes an order | unit | `pytest tests/test_env.py::test_order_completion -x` | Wave 0 |
| GRID-05 | Episode ends at max_steps or all orders done | unit | `pytest tests/test_env.py::test_episode_termination -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green + `openenv validate` passes before Phase 2

### Wave 0 Gaps
- [ ] `tests/__init__.py`
- [ ] `tests/test_env.py` — covers ENV-01, ENV-02, ENV-03, GRID-04, GRID-05
- [ ] `tests/test_models.py` — covers ENV-04, ENV-05, ENV-06
- [ ] `tests/test_grid.py` — covers GRID-01
- [ ] `tests/test_robots.py` — covers GRID-02, GRID-03
- [ ] `tests/test_validate.py` — covers ENV-07, ENV-08 (calls subprocess `openenv validate`)
- [ ] pytest in dev dependencies: add to `pyproject.toml` `[project.optional-dependencies] dev`

---

## Sources

### Primary (HIGH confidence)
- Installed `openenv-core` 0.2.3 package source (inspected directly)
  - `openenv/cli/_validation.py` — exact validation checks performed by `openenv validate`
  - `openenv/core/env_server/types.py` — Action, Observation, State, ResetRequest, StepRequest base classes with full field specs
  - `openenv/core/env_server/interfaces.py` — Environment ABC with reset/step/state signatures
  - `openenv/core/env_server/http_server.py` — create_app(), HTTPEnvServer, route registration, serialization
  - `openenv/core/env_server/serialization.py` — serialize_observation() and deserialize_action() internals
  - `openenv/cli/templates/openenv_env/` — canonical pyproject.toml, openenv.yaml, server/app.py, models.py, Dockerfile templates
- Live validation test (confirmed): `openenv validate` passes on directory with: openenv.yaml + pyproject.toml (correct scripts) + server/app.py (has main()) + uv.lock

### Secondary (MEDIUM confidence)
- HF Spaces Docker documentation: https://huggingface.co/docs/hub/spaces-sdks-docker — app_port must match uvicorn port, tag `openenv` required
- OpenEnv HuggingFace blog post: https://huggingface.co/blog/openenv — conceptual overview

### Tertiary (LOW confidence)
- None — all critical claims verified from package source

---

## Metadata

**Confidence breakdown:**
- OpenEnv spec (openenv.yaml, validate checks): HIGH — inspected live package source
- HTTP route structure: HIGH — inspected HTTPEnvServer.register_routes() in http_server.py
- Base class inheritance requirements: HIGH — inspected types.py and interfaces.py
- Grid simulation patterns: HIGH — from architecture research (ARCHITECTURE.md)
- HF Spaces deployment: MEDIUM — from official HF docs, pitfalls research

**Research date:** 2026-04-07
**Valid until:** 2026-05-07 (openenv-core is fast-moving; re-verify if >30 days)

---

## RESEARCH COMPLETE

**Phase:** 1 - Core Environment
**Confidence:** HIGH

### Key Findings

1. **`openenv validate` checks 4 things, not YAML content:** presence of `openenv.yaml`, `pyproject.toml` with `[project.scripts] server = "....:main"`, `server/app.py` with `def main(` and `main()` call, and `uv.lock`. YAML fields are not validated by the local validator.

2. **Mandatory inheritance:** `WarehouseEnvironment` must inherit from `openenv.core.env_server.interfaces.Environment`. `WarehouseAction` from `openenv.core.env_server.types.Action`. `WarehouseObservation` from `openenv.core.env_server.types.Observation`. `WarehouseState` from `openenv.core.env_server.types.State`. Without this, the `/schema` runtime endpoint fails.

3. **`state` is a property, not a method:** The `Environment` ABC declares `state` with `@property @abstractmethod`. The `/state` HTTP endpoint calls `env.state` (no parens).

4. **Multi-robot actions require wrapping:** OpenEnv `step(action)` takes one `Action`. To support `list[RobotAction]`, define `WarehouseAction(Action)` with a `robots: list[RobotAction]` field. This is the natural Pydantic approach.

5. **Singleton env for stateful HTTP:** `create_app()` creates a fresh env instance per HTTP request by default. Use `lambda: _env_instance` factory to maintain episode state across `/reset` + `/step` calls.

6. **Port is 8000, not 7860:** The OpenEnv template uses port 8000. HF Spaces README must have `app_port: 8000`. The PITFALLS.md assumption of 7860 is wrong for this framework.

### File Created
`D:\projs\scaenv\.planning\phases\01-core-environment\01-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| openenv validate requirements | HIGH | Inspected _validation.py source directly; ran live test confirming pass |
| HTTP route structure | HIGH | Inspected http_server.py register_routes() method |
| Base class API | HIGH | Inspected types.py and interfaces.py; cross-checked with template |
| Grid simulation | HIGH | Architecture research + established Python patterns |
| HF Spaces deployment | MEDIUM | Official docs verified; port 8000 confirmed from template |

### Open Questions
- Singleton vs per-request env instance: use singleton `lambda: _env_instance` — confirmed approach
- Reward wire format: set `obs.reward = reward.value`; put breakdown in `obs.metadata`

### Ready for Planning
Research complete. Planner can now create PLAN.md with tasks that implement `WarehouseEnvironment(Environment)`, wire `create_app()`, scaffold the required file structure, and pass `openenv validate`.
