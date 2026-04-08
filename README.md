---
sdk: docker
app_port: 7860
tags:
  - openenv
---

# WarehouseEnv — Multi-Robot Warehouse Benchmark

OpenEnv-compliant multi-robot warehouse environment for the Meta x PyTorch / Scaler Hackathon.

## What This Is

WarehouseEnv is a grid-based warehouse simulation where one or more robots must pick items from shelves and deliver them to packing stations. It is designed as a benchmark environment for LLM-driven multi-agent coordination under the [OpenEnv](https://github.com/openenv-project/openenv) specification.

The environment supports three tasks of increasing difficulty, programmatic graders that return deterministic scores in [0.0, 1.0], and mid-episode disruptions (blocked aisles, robot breakdowns, surge orders) that test adaptive planning.

All game logic, reward shaping, and grading are implemented in pure Python + Pydantic — no NumPy, no external simulation frameworks. This keeps the Docker image small and dependencies minimal.

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
| `order_queue` | `list[dict]` | Pending and in-progress orders |
| `step_count` | `int` | Current step within episode |
| `max_steps` | `int` | Episode length for this task |
| `task_id` | `str` | Active task identifier |
| `description` | `str` | Auto-generated natural language summary for LLM prompts |
| `done` | `bool` | Whether the episode has ended |
| `reward` | `float` | Step reward |

## Tasks

| Task | Difficulty | Robots | Orders | Grid | Max Steps | Disruptions |
|---|---|---|---|---|---|---|
| `solo_delivery` | Easy | 1 | 5 | 10x10 | 100 | None |
| `coordinated_delivery` | Medium | 3 | 10 | 12x12 | 150 | Blocked aisle at step 20 |
| `crisis_management` | Hard | 5 | 20 | 15x15 | 200 | Robot breakdown at step 15; surge orders at step 25 |

**solo_delivery**: One robot navigates a 10x10 grid to fulfill 5 orders. Tests basic path planning and pick/drop sequencing.

**coordinated_delivery**: Three robots share a 12x12 grid to fulfill 10 orders. A blocked aisle appears at step 20, requiring rerouting. Tests multi-agent coordination and disruption handling.

**crisis_management**: Five robots handle 20 initial orders on a 15x15 grid. Robot 2 breaks down at step 15 (permanently inactive). Five surge orders are injected at step 25. Grader weights: 50% order completion, 30% robot survival, 20% surge order completion.

## Setup & Usage

**Local install**

```bash
pip install -e .
```

**Run the OpenEnv HTTP server**

```bash
uvicorn server.app:app --host 0.0.0.0 --port 7860
```

Or via the project entry point:

```bash
server
```

**Docker**

```bash
docker build -t warehouse-env .
docker run -p 7860:7860 -e PORT=7860 warehouse-env
```

**Cloud Run Deployment (Scale-to-Zero)**

The Docker image supports automatic scale-to-zero on Google Cloud Run — the container shuts down when no requests are coming in, so you pay nothing when idle.

```bash
# One-time setup: enable APIs and create Artifact Registry repo
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
gcloud artifacts repositories create scaenv-repo --repository-format=docker --location=asia-south1

# Deploy directly from source
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

After deployment, your API is live at `https://warehouse-env-<hash>.run.app`.

**CI/CD (GitHub → Cloud Build → Cloud Run)**

Every push to `master` automatically builds and deploys via Google Cloud Build. See `cloudbuild.yaml` for the pipeline config. To set up:

1. Connect your GitHub repo in [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers)
2. Create a trigger watching `master` branch, using `cloudbuild.yaml`
3. Grant Cloud Build the `Cloud Run Admin` and `Service Account User` roles

**Run inference.py (LLM agent)**

Requires `API_BASE_URL`, `MODEL_NAME`, and `HF_TOKEN` environment variables:

```bash
export API_BASE_URL=https://api-inference.huggingface.co/v1
export MODEL_NAME=meta-llama/Llama-3.1-8B-Instruct
export HF_TOKEN=hf_...
python inference.py
```

`inference.py` runs all 3 tasks sequentially and emits `[START]`/`[STEP]`/`[END]` lines to stdout per the OpenEnv inference spec.

## Baseline Scores

Scores for a dumb agent that sends `wait` for all robots every step:

| Task | Score | Notes |
|---|---|---|
| `solo_delivery` | 0.0 | No orders fulfilled (robot never moves) |
| `coordinated_delivery` | 0.0 | No orders fulfilled (robots never move) |
| `crisis_management` | 0.24 | Survival component: 4/5 robots still active at end (robot 2 breaks at step 15), 0 orders fulfilled |
