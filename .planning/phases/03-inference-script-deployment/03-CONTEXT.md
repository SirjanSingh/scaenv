# Phase 3: Inference Script & Deployment - Context

**Gathered:** 2026-04-07
**Status:** Ready for planning
**Source:** /gsd:discuss-phase

<domain>
## Phase Boundary

Deliver: (1) `inference.py` in the project root that runs all 3 tasks sequentially via an LLM agent loop emitting `[START]`/`[STEP]`/`[END]` stdout lines, (2) a `Dockerfile` that builds and serves the OpenEnv HTTP server on port 7860, (3) HF Space deployment with `openenv` tag, and (4) a `README.md` with all 5 required sections.

This phase does NOT change game logic, graders, reward functions, or disruptions — those are complete in Phases 1–2. Server routing is already wired in `server/app.py` via `create_app()`.

</domain>

<decisions>
## Implementation Decisions

### LLM Agent Loop (inference.py)

- **D-01:** One LLM API call per timestep for ALL robots simultaneously. Single prompt returns a JSON list of `[{robot_id, action_type}, ...]` for all active robots. Inactive (broken) robots are excluded from the list.
- **D-02:** Prompt content: `obs.description` only — the auto-generated natural language summary already in `WarehouseObservation`. No extra grid serialization. This is the minimum viable prompt that gives the LLM all context it needs.
- **D-03:** Prompt template (EXACT — planner must use this verbatim):
  ```
  You are controlling warehouse robots. Current state:
  {obs.description}

  Return a JSON array of actions for each active robot. Each action: {"robot_id": <int>, "action_type": "<move_up|move_down|move_left|move_right|pick|drop|wait>"}
  Only include active robots. Example: [{"robot_id": 0, "action_type": "move_down"}]

  Actions JSON:
  ```
- **D-04:** LLM client: `openai.OpenAI(base_url=os.environ["API_BASE_URL"], api_key=os.environ["HF_TOKEN"])`. Model: `os.environ["MODEL_NAME"]`. All 3 env vars required — raise `EnvironmentError` if missing at startup.
- **D-05:** Parse the LLM response by extracting JSON array from the response text (extract between `[` and last `]`). Build `WarehouseAction(actions=[RobotAction(robot_id=..., action_type=...) for ...])`.
- **D-06:** **Error handling**: on any exception (API error, timeout, JSON parse failure, validation error) — default ALL active robots to `action_type='wait'` for that step. Log the error in the `[STEP]` line `error=` field. Episode continues, never crashes.
- **D-07:** Stdout format (EXACT per INF-03..05 — planner must match exactly):
  - Episode start: `[START] task=<name> env=warehouse model=<MODEL_NAME>`
  - Each step: `[STEP] step=<n> action=<comma-joined action_types> reward=<0.00> done=<true|false> error=<msg|null>`
  - Episode end: `[END] success=<true|false> steps=<n> score=<0.00> rewards=<r1,r2,...>`
- **D-08:** `success` in `[END]` = `True` if at least 1 order was fulfilled (score > 0). `rewards` = comma-joined list of all step reward values rounded to 2dp.
- **D-09:** Run all 3 tasks sequentially: `solo_delivery` → `coordinated_delivery` → `crisis_management`. Max steps per task: use `task_config.max_steps` (100/150/200 respectively).
- **D-10:** After each task, call `GRADER_REGISTRY[task_id](env)` to get the final score and include in `[END]` line.

### Server Port

- **D-11:** `server/app.py` `main()` reads `PORT = int(os.environ.get("PORT", 7860))`. HF Spaces sets `PORT=7860` automatically. Local dev defaults to 7860. This replaces the current hardcoded `port: int = 8000` default.
- **D-12:** `host` stays `"0.0.0.0"` — required for HF Spaces container networking.

### Dockerfile

- **D-13:** Base image: `python:3.11-slim` — stable, smaller than 3.12-slim, compatible with all deps.
- **D-14:** Install deps via `pip install -e .` (uses `pyproject.toml`). No requirements.txt needed — `pyproject.toml` already has all deps.
- **D-15:** Expose port 7860. CMD: `["python", "-m", "server.app"]` or `["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]`.
- **D-16:** Add `uvicorn` to `pyproject.toml` dependencies (currently missing — `server/app.py` imports it).
- **D-17:** Dockerfile must set `ENV PORT=7860` explicitly for HF Spaces compatibility.

### HF Deployment

- **D-18:** HF Space uses Docker SDK (not Gradio). `README.md` must have HF Space YAML frontmatter with `sdk: docker`, `app_port: 7860`, `tags: [openenv]`.
- **D-19:** Deployment: `git push` to the HF Space repo (standard HF Spaces deploy workflow via `huggingface_hub` CLI or manual git remote).

### README Structure

- **D-20:** README must have exactly these 5 sections (DOC-01..05):
  1. `## What This Is` — env description and motivation
  2. `## Action & Observation Space` — action types, observation fields
  3. `## Tasks` — all 3 tasks with difficulty and expected behavior
  4. `## Setup & Usage` — local install, `uvicorn server.app:app`, Docker run, inference.py usage
  5. `## Baseline Scores` — dumb agent (all-wait) scores for all 3 tasks: `solo_delivery: 0.0`, `coordinated_delivery: 0.0`, `crisis_management: 0.24` (from observed test output)

### Claude's Discretion

- Exact uvicorn startup command in Dockerfile CMD vs entrypoint — implementation detail
- Whether to add a `/health` GET endpoint returning `{"status": "ok"}` for HF ping — planner decides based on HF Spaces requirements
- Whether inference.py needs a `__main__` guard or can be run directly
- pyproject.toml: whether to add `uvicorn` to main deps or `[project.optional-dependencies].server`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1–2 Artifacts (already built)
- `server/app.py` — existing HTTP server using `create_app()` singleton; needs PORT env var fix
- `warehouse_env/env.py` — `WarehouseEnv`, `list_tasks()`, `reset(task_id=...)`, `step()`
- `warehouse_env/models.py` — `WarehouseAction`, `RobotAction`, `WarehouseObservation` (has `description` field)
- `warehouse_env/graders.py` — `GRADER_REGISTRY` for scoring after episode
- `warehouse_env/tasks.py` — `TASK_REGISTRY` with `max_steps` per task
- `pyproject.toml` — current deps (need to add `uvicorn`)

### Project Context
- `.planning/PROJECT.md` — constraints: 20 min runtime, API_BASE_URL/MODEL_NAME/HF_TOKEN, Pure Python + Pydantic
- `.planning/REQUIREMENTS.md` — INF-01..07, DEPLOY-01..05, DOC-01..05 requirement IDs for this phase
- `.planning/ROADMAP.md` — Phase 3 success criteria

### Prior Phase Context
- `.planning/phases/01-core-environment/01-CONTEXT.md` — D-06: `description` field in Observation (confirmed exists)
- `.planning/phases/02-tasks-graders-disruptions/02-CONTEXT.md` — D-01: GRADER_REGISTRY dispatch pattern

</canonical_refs>

<specifics>
## Specific Ideas

- The `obs.description` field already generates natural language summaries like "Robot 0 at (2,3) carrying item, assigned to order #2 → packing station P1. Robot 1 idle at (4,1). 3 orders remaining. Step 12/50." — this is exactly what the LLM needs.
- `crisis_management` baseline score of 0.24 comes from survival component (4/5 robots alive) with 0 orders fulfilled — confirmed by test_run.py output.
- HF Spaces Docker SDK: the YAML frontmatter in README.md IS the Space configuration (sdk, app_port, tags) — no separate config file needed.
- `[STEP]` `action=` field: join all robot action_types comma-separated (e.g. `move_down,pick,wait`) — matches INF-04 spec.

</specifics>

<deferred>
## Deferred Ideas

- Retry logic for LLM errors — decided against (see D-06), adds complexity and may cascade under rate limits
- Multi-step LLM planning (batch K steps) — out of scope, likely poor performance
- `/health` endpoint — planner decides; not explicitly required by spec
- Visualization/rendering — explicitly out of scope (PROJECT.md)
- Per-robot LLM calls — too slow for 20 min budget

</deferred>

---

*Phase: 03-inference-script-deployment*
*Context gathered: 2026-04-07 via /gsd:discuss-phase*
