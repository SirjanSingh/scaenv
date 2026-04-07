# Roadmap: WarehouseEnv

## Overview

4-phase execution plan to ship a spec-compliant OpenEnv warehouse environment for the Meta x PyTorch / Scaler Hackathon by April 8 11:59 PM. Phase 1 builds the core environment skeleton with full OpenEnv compliance. Phase 2 adds the 3 tasks, graders, reward function, and disruption system. Phase 3 wires the inference script and deploys to HF Spaces. Each phase is independently verifiable and deliverable.

## Phases

- [x] **Phase 1: Core Environment** — OpenEnv-compliant warehouse grid with Pydantic models and step/reset/state API (completed 2026-04-07)
- [x] **Phase 2: Tasks, Graders & Disruptions** — 3 tasks (easy→hard), layered reward function, 3 disruption types  (completed 2026-04-07)
- [ ] **Phase 3: Inference Script & Deployment** — inference.py with [START]/[STEP]/[END] format, Dockerfile, HF Spaces deploy, README

## Phase Details

### Phase 1: Core Environment
**Goal**: A working `WarehouseEnv` class that fully satisfies the OpenEnv spec — typed Pydantic models, `step()`/`reset()`/`state()` endpoints, `openenv.yaml`, and `openenv validate` passes.
**Depends on**: Nothing (first phase)
**Requirements**: ENV-01, ENV-02, ENV-03, ENV-04, ENV-05, ENV-06, ENV-07, ENV-08, GRID-01, GRID-02, GRID-03, GRID-04, GRID-05
**Success Criteria** (what must be TRUE):
  1. `from warehouse_env import WarehouseEnv` works with no import errors
  2. `env.reset()` returns a valid `Observation` Pydantic model
  3. `env.step(action)` returns `(Observation, Reward, bool, dict)` with correct types
  4. `env.state()` returns a dict with full warehouse state
  5. `openenv validate` passes on the project directory
  6. Grid initializes with S/R/P/X/. cells; robots can move, pick, and drop
**Plans**: 2 plans

Plans:
- [x] 01-01: Pydantic models + warehouse grid engine (Observation, Action, Reward models; grid state; robot/order/cell logic)
- [x] 01-02: OpenEnv interface + spec compliance (step/reset/state methods; openenv.yaml; validate check)

### Phase 2: Tasks, Graders & Disruptions
**Goal**: 3 fully-defined tasks with deterministic programmatic graders (scores 0.0–1.0), a layered reward function with partial progress signals, and 3 disruption types that trigger mid-episode.
**Depends on**: Phase 1
**Requirements**: TASK-01, TASK-02, TASK-03, TASK-04, TASK-05, REW-01, REW-02, REW-03, REW-04, REW-05, REW-06, REW-07, REW-08, DISR-01, DISR-02, DISR-03
**Success Criteria** (what must be TRUE):
  1. `env.list_tasks()` returns 3 tasks: solo_delivery, coordinated_delivery, crisis_management
  2. Running solo_delivery to completion returns a score in [0.0, 1.0]
  3. Running coordinated_delivery mid-episode triggers the blocked aisle at step 20
  4. Running crisis_management triggers robot breakdown at step 15 and surge at step 25
  5. All grader scores are deterministic — running the same sequence twice gives the same score
  6. Reward function returns non-zero intermediate rewards (not just terminal)
**Plans**: 2 plans

Plans:
- [x] 02-01: Task definitions + graders (task registry; solo_delivery/coordinated_delivery/crisis_management; grader logic)
- [x] 02-02: Reward function + disruption system (layered reward calculator; blocked aisle/robot breakdown/surge order events)

### Phase 3: Inference Script & Deployment
**Goal**: `inference.py` emits correct [START]/[STEP]/[END] stdout, runs all 3 tasks under 20 min; Dockerfile builds and runs; HF Space deployed and pingable; README complete.
**Depends on**: Phase 2
**Requirements**: INF-01, INF-02, INF-03, INF-04, INF-05, INF-06, INF-07, DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04, DEPLOY-05, DOC-01, DOC-02, DOC-03, DOC-04, DOC-05
**Success Criteria** (what must be TRUE):
  1. `python inference.py` runs to completion with `API_BASE_URL`/`MODEL_NAME`/`HF_TOKEN` set; outputs valid [START]/[STEP]/[END] lines for all 3 tasks
  2. `docker build -t warehouse-env . && docker run -p 7860:7860 warehouse-env` succeeds and container serves on port 7860
  3. HF Space URL responds with 200 to GET ping
  4. HF Space URL responds to `POST /reset` and `POST /step` (or OpenEnv server equivalent)
  5. README exists with all 5 required sections
  6. Pre-submission validation script passes all checks
**Plans**: 2 plans

Plans:
- [ ] 03-01: inference.py + OpenEnv server (LLM agent loop; [START]/[STEP]/[END] stdout; FastAPI/HTTP server for HF Spaces)
- [ ] 03-02: Dockerfile + HF deployment + README (Dockerfile; docker build/run test; HF Space push; README with baseline scores)

## Progress

**Execution Order:** Phase 1 → Phase 2 → Phase 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Environment | 2/2 | Complete   | 2026-04-07 |
| 2. Tasks, Graders & Disruptions | 2/2 | Complete   | 2026-04-07 |
| 3. Inference Script & Deployment | 2/2 | Complete     | 2026-04-07 |
