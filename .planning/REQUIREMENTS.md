# Requirements: WarehouseEnv

**Defined:** 2026-04-07
**Core Value:** A working, spec-compliant OpenEnv submission deployed to HF Spaces before April 8 11:59 PM

## v1 Requirements

### Environment Core

- [ ] **ENV-01**: `WarehouseEnv` class implements `step(action)` → `(observation, reward, done, info)`
- [ ] **ENV-02**: `WarehouseEnv` implements `reset()` → initial `Observation`
- [ ] **ENV-03**: `WarehouseEnv` implements `state()` → current full state dict
- [x] **ENV-04**: `Observation` is a typed Pydantic model (robot positions, order queue, grid map, step count)
- [x] **ENV-05**: `Action` is a typed Pydantic model (robot_id, action_type: move/pick/drop/wait)
- [x] **ENV-06**: `Reward` is a typed Pydantic model (value: float, breakdown: dict)
- [ ] **ENV-07**: `openenv.yaml` metadata file present with required fields (name, version, description, tasks)
- [ ] **ENV-08**: `openenv validate` passes without errors

### Grid Simulation

- [x] **GRID-01**: Warehouse grid supports cell types: Shelf (S), Robot (R), Packing station (P), Blocked (X), Free (.)
- [x] **GRID-02**: Robots can execute 6 action types: move_up, move_down, move_left, move_right, pick, drop
- [x] **GRID-03**: Collision detection — two robots cannot occupy the same cell; collision triggers penalty
- [x] **GRID-04**: Order queue: each order is (shelf_id → packing_station_id); robots pick from shelf and drop at station
- [x] **GRID-05**: Episode ends when all orders fulfilled OR max_steps reached

### Tasks & Graders

- [ ] **TASK-01**: Task "solo_delivery" (easy) — 1 robot, 5 orders, no disruptions, 10×10 grid; grader scores orders_fulfilled / 5
- [ ] **TASK-02**: Task "coordinated_delivery" (medium) — 3 robots, 10 orders, 1 blocked aisle at step 20, 12×12 grid; grader scores (orders_fulfilled / 10) with collision penalty
- [ ] **TASK-03**: Task "crisis_management" (hard) — 5 robots, 20 orders, robot breakdown at step 15 + surge (+5 orders) at step 25, 15×15 grid; composite grader
- [ ] **TASK-04**: All graders return deterministic float in [0.0, 1.0]
- [ ] **TASK-05**: All graders have clear pass/fail criteria documented

### Reward Function

- [ ] **REW-01**: +10.0 when an order is successfully delivered (pick from shelf → drop at packing station)
- [ ] **REW-02**: +5.0 bonus when order delivered in under N steps (task-specific threshold)
- [ ] **REW-03**: -8.0 per robot collision (two robots attempt same cell)
- [ ] **REW-04**: -1.0 per step taken without progress (robot moves away from target or waits unnecessarily)
- [ ] **REW-05**: -3.0 when order delivered after time threshold (late penalty)
- [ ] **REW-06**: +3.0 when robot successfully reroutes around a newly blocked cell
- [ ] **REW-07**: -10.0 when order expires without delivery (episode ends with unfulfilled orders)
- [ ] **REW-08**: Reward normalized to [0.0, 1.0] range for grader score output

### Disruption System

- [ ] **DISR-01**: Blocked Aisle disruption — at configurable step N, one aisle cell becomes X (impassable); robots must reroute
- [ ] **DISR-02**: Robot Breakdown disruption — at configurable step N, one robot is marked inactive; remaining robots can accept its pending orders
- [ ] **DISR-03**: Surge Orders disruption — at configurable step N, additional orders injected into the queue

### Inference Script

- [ ] **INF-01**: `inference.py` in project root; uses `openai.OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)` for all LLM calls
- [ ] **INF-02**: Reads `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN` from environment variables
- [ ] **INF-03**: Emits exactly `[START] task=<name> env=warehouse model=<model>` at episode begin
- [ ] **INF-04**: Emits `[STEP] step=<n> action=<str> reward=<0.00> done=<true|false> error=<msg|null>` after each `env.step()`
- [ ] **INF-05**: Emits `[END] success=<true|false> steps=<n> score=<0.00> rewards=<r1,r2,...>` after `env.close()`
- [ ] **INF-06**: Runs all 3 tasks sequentially; total runtime < 20 min on 2 vCPU / 8 GB
- [ ] **INF-07**: LLM agent observes state and picks action (move/pick/drop/wait) per step

### Deployment

- [ ] **DEPLOY-01**: `Dockerfile` builds successfully with `docker build`
- [ ] **DEPLOY-02**: Container starts with `docker run` and serves HTTP on port 7860 (HF Spaces default)
- [ ] **DEPLOY-03**: GET `/` or health endpoint returns 200 OK
- [ ] **DEPLOY-04**: POST `/reset` and POST `/step` endpoints respond correctly (or equivalent OpenEnv server routes)
- [ ] **DEPLOY-05**: Deployed HF Space is tagged with `openenv`; Space URL responds to automated ping

### Documentation

- [ ] **DOC-01**: `README.md` includes environment description and motivation
- [ ] **DOC-02**: `README.md` includes action space and observation space definitions
- [ ] **DOC-03**: `README.md` includes task descriptions with expected difficulty
- [ ] **DOC-04**: `README.md` includes setup and usage instructions (local + Docker)
- [ ] **DOC-05**: `README.md` includes baseline scores for all 3 tasks

## v2 Requirements

### Enhancements (Post-Hackathon)

- **ENH-01**: Battery/recharge disruption — robot must return to charge station before continuing
- **ENH-02**: Visual rendering — ASCII grid printed per step for human observation
- **ENH-03**: Multi-task parallel evaluation — run all 3 tasks simultaneously
- **ENH-04**: LLM grader with structured prompt for nuanced scoring

## Out of Scope

| Feature | Reason |
|---------|--------|
| GUI / rendering | No time; judges use programmatic evaluation not visual |
| LLM-based graders | Non-deterministic, costs API tokens, fails reproducibility check |
| Real pathfinding (A*, BFS) | Manhattan heuristic sufficient for grid demo; adds complexity |
| Multi-agent communication | Agents act independently; message passing adds protocol complexity |
| Battery/recharge disruption | Cut for deadline; 3 disruption types satisfies hard requirement |
| OAuth / auth | Not needed for HF Spaces public endpoint |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ENV-01..08 | Phase 1 | Pending |
| GRID-01..05 | Phase 1 | Pending |
| TASK-01..05 | Phase 2 | Pending |
| REW-01..08 | Phase 2 | Pending |
| DISR-01..03 | Phase 2 | Pending |
| INF-01..07 | Phase 3 | Pending |
| DEPLOY-01..05 | Phase 3 | Pending |
| DOC-01..05 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 38 total
- Mapped to phases: 38
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-07*
*Last updated: 2026-04-07 after initial definition*
