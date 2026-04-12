---
sdk: docker
app_port: 7860
tags:
  - openenv
---

# WarehouseEnv — Multi-Robot Warehouse Benchmark

OpenEnv-compliant multi-robot warehouse environment built for the Meta x PyTorch / Scaler OpenEnv Hackathon by **Team PyGuys**.

## What This Is

WarehouseEnv is a grid-based warehouse simulation where one or more LLM-driven robots pick items from shelves and deliver them to packing stations under real-world-like constraints. It is designed as a benchmark for multi-agent coordination, adaptive planning, and disruption recovery under the [OpenEnv](https://github.com/openenv-project/openenv) specification.

**Key design principles:**
- Three tasks of escalating difficulty — from single-robot navigation to 5-robot crisis coordination
- Mid-episode disruptions (blocked aisles, robot breakdowns, order surges) that force runtime adaptation
- Deterministic graders with meaningful partial-credit scoring — no cliff-edge pass/fail
- Pure Python + Pydantic — no NumPy, no simulation frameworks, minimal Docker image

## Action & Observation Space

**Action space**

Each step accepts a `WarehouseAction` containing a list of per-robot actions:

```json
{"robots": [{"robot_id": 0, "action_type": "move_down"}, {"robot_id": 1, "action_type": "pick"}]}
```

Valid `action_type` values: `move_up`, `move_down`, `move_left`, `move_right`, `pick`, `drop`, `wait`.

Inactive (broken-down) robots must be omitted from the list.

**Observation space**

Each `step()` and `reset()` returns a `WarehouseObservation` with:

| Field | Type | Description |
|---|---|---|
| `grid` | `list[list[str]]` | 2D grid; cells: `R0`/`R1`/`S`/`P`/`X`/`.` |
| `robots` | `list[RobotState]` | Per-robot position, carrying status, active flag |
| `order_queue` | `list[dict]` | All orders with status: `pending` / `picked` / `delivered` |
| `step_count` | `int` | Current step within episode |
| `max_steps` | `int` | Episode length for this task |
| `task_id` | `str` | Active task identifier |
| `description` | `str` | Auto-generated natural language summary for LLM prompts |
| `done` | `bool` | Whether the episode has ended |
| `reward` | `float` | Current grader score in `(0.01, 0.99)` — strictly bounded for validator compliance |

## Tasks

| Task | Difficulty | Robots | Orders | Grid | Max Steps | Disruptions |
|---|---|---|---|---|---|---|
| `solo_delivery` | Easy | 1 | 5 | 10×10 | 100 | None |
| `coordinated_delivery` | Medium | 3 | 10 | 12×12 | 150 | Blocked aisle at step 20 |
| `crisis_management` | Hard | 5 | 20 + 5 surge | 15×15 | 200 | Robot breakdown at step 15; surge orders at step 25 |

**solo_delivery** — One robot navigates a 10×10 grid to fulfill 5 orders. Tests basic path planning and pick/drop sequencing. Grader: `fulfilled / 5`.

**coordinated_delivery** — Three robots share a 12×12 grid to fulfill 10 orders. A blocked aisle appears at step 20, requiring real-time rerouting. Collision penalty applied per pair. Grader: `max(0, fulfilled/10 − 0.05×collisions)`.

**crisis_management** — Five robots handle 20 initial orders on a 15×15 grid. Robot 2 breaks down permanently at step 15. Five surge orders are injected at step 25. Grader: `0.5×order_completion + 0.3×robot_survival + 0.2×surge_completion`.

## Disruption System

Disruptions fire at pre-scheduled steps and are visible in `obs.description` immediately:

| Disruption | Task | Step | Effect |
|---|---|---|---|
| `blocked_aisle` | coordinated_delivery | 20 | Two cells become impassable (`X`); robots on those cells are displaced |
| `robot_breakdown` | crisis_management | 15 | Robot 2 deactivated permanently; its carried order returned to pending |
| `surge_orders` | crisis_management | 25 | 5 new orders injected into the queue |

## Reward & Grading

`obs.reward` at every step equals the **current grader score** — a live task completion signal in `(0.01, 0.99)`. This means:

- Rewards start near `0.01` (nothing delivered) and climb as orders complete
- The final step's reward equals the terminal task score used by the validator
- Raw shaped reward (delivery bonuses, collision penalties) is preserved in `obs.metadata["raw_reward"]`

All scores are strictly in `(0.01, 0.99)` — never exactly `0.0` or `1.0` — per OpenEnv validator requirements.

## LLM Agent — inference.py

`inference.py` implements an LLM agent that drives all robots via a single OpenAI-compatible API call per step.

**Coordination techniques:**
- **BFS shortest-path navigation** — each robot computes its true shortest path around walls, blocked cells, and other robots. Two-pass: first respects other robots' positions, then ignores them if blocked (they may have moved).
- **Greedy nearest-neighbour order assignment** — idle robots are assigned their closest unassigned order by Manhattan distance, not round-robin. Prevents two robots charging the same shelf.
- **Per-robot AVOID cell list** — every robot instruction explicitly lists the current cells occupied by other robots.
- **Stuck detection** — after 3 steps at the same position, the robot receives a perpendicular escape hint.
- **Surge pre-warning** — in `crisis_management`, idle robots are alerted 7 steps before the step-25 surge to pre-position near shelves.

**Environment variables required:**

```bash
export API_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
export HF_TOKEN=AIza...          # Google AI Studio API key (any OpenAI-compatible key)
export MODEL_NAME=gemini-2.5-flash   # optional, this is the default
python inference.py
```

Runs all 3 tasks sequentially and writes `[START]` / `[STEP]` / `[END]` lines to stdout and `simulation.log`.

## Benchmark Scores

**LLM agent (Gemini 2.5 Flash):**

| Task | Score | Orders | Steps Used | Notes |
|---|---|---|---|---|
| `solo_delivery` | **0.99** | 5/5 | 91/100 | All orders delivered |
| `coordinated_delivery` | **0.40** | 9/10 | 150/150 | 1 order undelivered at timeout; score penalised by collisions early in episode |
| `crisis_management` | **0.64** | 20/25 | 200/200 | Robot 2 broke at step 15; 3 surge orders in-transit at timeout |

**Dumb baseline (all robots `wait` every step):**

| Task | Score | Notes |
|---|---|---|
| `solo_delivery` | 0.01 | No orders fulfilled |
| `coordinated_delivery` | 0.01 | No orders fulfilled |
| `crisis_management` | 0.24 | Survival component only: 4/5 robots still active |

## Setup & Usage

**Local install**

```bash
pip install -e .
```

**Run the OpenEnv HTTP server**

```bash
uvicorn server.app:app --host 0.0.0.0 --port 7860
# or via entry point:
server
```

**Docker**

```bash
docker build -t warehouse-env .
docker run -p 7860:7860 -e PORT=7860 warehouse-env
```

**Cloud Run (GCP)**

```bash
gcloud run deploy warehouse-env \
  --source . \
  --region asia-south1 \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 3 \
  --memory 512Mi \
  --port 8080
```

Every push to `master` automatically builds and redeploys via `cloudbuild.yaml`.

## Project Structure

```
warehouse_env/
  env.py          — WarehouseEnv: reset(), step(), state property
  models.py       — Pydantic models: WarehouseAction, WarehouseObservation, ...
  grid.py         — Grid engine: passability, robot placement, blocked cells
  tasks.py        — TASK_REGISTRY: TaskConfig for all 3 tasks
  reward.py       — Layered reward calculator (delivery, collision, timeout, ...)
  graders.py      — GRADER_REGISTRY: deterministic task-score functions
  disruptions.py  — Disruption handlers: blocked_aisle, robot_breakdown, surge_orders
server/
  app.py          — FastAPI app via openenv create_app(); singleton env instance
inference.py      — LLM agent: BFS nav, nearest-neighbour assignment, surge pre-warning
openenv.yaml      — OpenEnv environment manifest
Dockerfile        — Docker build for HF Spaces / Cloud Run
```
