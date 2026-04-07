# Domain Pitfalls

**Domain:** OpenEnv hackathon submission — multi-agent warehouse benchmark environment
**Researched:** 2026-04-07
**Confidence:** MEDIUM (HF Spaces pitfalls verified against official docs; OpenEnv-specific validator rules derived from spec knowledge + PROJECT.md context because openenv.yaml source was gated)

---

## Critical Pitfalls

Mistakes that cause disqualification, zero scores, or deployment failures that cannot be recovered from after the deadline.

---

### Pitfall 1: Server Not Listening on 0.0.0.0

**What goes wrong:** The FastAPI/uvicorn process binds to `127.0.0.1` (localhost) instead of `0.0.0.0`. The Docker container starts cleanly, HF Spaces shows it as running, but every external HTTP request — including the automated `openenv validate` ping and health checks — returns connection refused.

**Why it happens:** `uvicorn app:main` defaults to `127.0.0.1`. Developers test locally (where localhost works) and miss the flag entirely.

**Consequences:** Space is marked unhealthy; `openenv validate` fails at the connectivity check before even reaching endpoint validation. Judges cannot run `reset()`.

**Prevention:**
```dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
```
Never omit `--host 0.0.0.0`. Verify locally with `docker run -p 7860:7860` and `curl http://localhost:7860/reset` before pushing.

**Detection:** Space shows "Running" but `curl https://<space>.hf.space/reset` returns no response or connection refused.

---

### Pitfall 2: app_port Mismatch Between README and CMD

**What goes wrong:** The Space README YAML declares `app_port: 8000` (or omits it, defaulting to 7860) but uvicorn is told to listen on a different port. HF Spaces routes external traffic to `app_port` only — everything else is blocked.

**Why it happens:** Developer changes the uvicorn port for local testing convenience and forgets to update the README YAML, or vice versa.

**Consequences:** Same as Pitfall 1 — all external requests silently fail.

**Prevention:** Keep `app_port` in README.md and `--port` in Dockerfile CMD in sync. Default to 7860 for both — it is the HF Spaces standard.

**README YAML must have:**
```yaml
sdk: docker
app_port: 7860
tags:
  - openenv
```

**Detection:** Check both files side by side before every push.

---

### Pitfall 3: Missing `openenv` Tag on the Space

**What goes wrong:** The HF Space is deployed and functional, but the automated hackathon discovery/validation pipeline cannot find it because the Space is not tagged with `openenv`.

**Why it happens:** Tags are set in the README.md YAML block and are easy to forget in deadline rush.

**Consequences:** Submission is invisible to the evaluation pipeline. Even a perfectly working environment scores zero if judges cannot find it.

**Prevention:**
```yaml
tags:
  - openenv
```
Add this to the README.md YAML block. Verify by checking the Space page on HF Hub — tags appear below the Space title.

---

### Pitfall 4: openenv.yaml Missing Required Fields

**What goes wrong:** `openenv validate` runs a schema check against `openenv.yaml` in the repo root. Any missing required field causes hard failure before a single endpoint is tested.

**Why it happens:** Teams copy a partial example or hand-write the file without consulting the full schema.

**Consequences:** Immediate validation failure. The environment is not evaluated at all.

**Prevention:** The `openenv.yaml` file must include at minimum:
- `name` — environment name string
- `version` — semantic version string (e.g., `"1.0.0"`)
- `description` — text description of what the environment does
- `observation_space` — typed schema describing the observation model
- `action_space` — typed schema describing the action model
- `tasks` — list with at least one task entry, each with `id`, `description`, and scoring metadata
- `endpoints` — explicit declaration of the three required endpoints (`/reset`, `/step`, `/state`)

**Detection:** Run `openenv validate` locally before pushing. If the package is unavailable, validate the YAML manually against any published reference environment's `openenv.yaml`.

---

### Pitfall 5: Endpoint Naming Deviations

**What goes wrong:** The spec requires exactly `/reset`, `/step`, and `/state` as HTTP POST endpoints. Any deviation — `/env/reset`, `/api/step`, `/reset/` (trailing slash), or using GET instead of POST — causes `openenv validate` to fail the endpoint presence check.

**Why it happens:** FastAPI developers habitually namespace endpoints (e.g., `/api/v1/reset`) and may add router prefixes without realizing the spec requires bare paths.

**Consequences:** Validation fails on endpoint discovery even if all logic is correct.

**Prevention:**
```python
@app.post("/reset")
@app.post("/step")
@app.post("/state")
```
No router prefix. No trailing slash. POST method, not GET. Verify with `curl -X POST http://localhost:7860/reset`.

---

### Pitfall 6: Pydantic Model Type Mismatch with OpenEnv Spec

**What goes wrong:** The spec requires Observation, Action, and Reward models to be typed Pydantic `BaseModel` subclasses with specific field types. Using `dict`, `Any`, bare Python primitives, or non-Pydantic response types causes the validator's schema introspection to fail.

**Why it happens:** Developers return raw dicts from FastAPI endpoints (which FastAPI silently accepts and serializes) without registering proper response_model types.

**Consequences:** `openenv validate` schema check fails. Even if the endpoint responds with valid JSON, the type contract is not met.

**Prevention:**
```python
from pydantic import BaseModel
from typing import List, Dict

class WarehouseObservation(BaseModel):
    grid: List[List[str]]
    robots: Dict[str, dict]
    items: List[dict]
    step: int
    done: bool

@app.post("/reset", response_model=WarehouseObservation)
def reset():
    ...
```
All three endpoints must declare `response_model` with a Pydantic class. The Action input to `/step` must also be a Pydantic model, not a raw dict.

---

### Pitfall 7: Grader Returns Score Outside [0.0, 1.0]

**What goes wrong:** A task grader returns a float outside the closed interval [0.0, 1.0]. This may happen due to un-clamped reward accumulation, division by zero (returning `inf`), or a calculation error producing a negative number.

**Why it happens:** Reward functions accumulate values across steps (+10, -8, etc.) and the final score is derived from that sum. If normalization logic is wrong, raw accumulated rewards leak through.

**Consequences:** The evaluation pipeline rejects the score, marks the task as invalid, or produces undefined comparison behavior. Per PROJECT.md: "Each task grader must return float in [0.0, 1.0]."

**Prevention:**
```python
def compute_score(raw_reward: float, max_possible: float) -> float:
    score = raw_reward / max_possible
    return max(0.0, min(1.0, score))  # hard clamp always
```
Always apply `max(0.0, min(1.0, score))` as the final return. Never return raw reward sums as scores.

**Detection:** Unit test each grader with edge cases: zero steps taken, all items delivered, timeout hit, all robots broken.

---

### Pitfall 8: Non-Deterministic Grader Scores

**What goes wrong:** The grader returns different scores on repeated identical runs due to random element injection (e.g., `random.random()` in scoring logic, timestamp-based tiebreakers, or Python dict ordering assumptions in Python < 3.7).

**Why it happens:** Developers confuse the environment's stochastic disruption system (which should be seeded) with the grader (which must be pure).

**Consequences:** Judges cannot reproduce baseline scores. Results differ between the baseline script run and the human review run. This raises plagiarism/manipulation flags.

**Prevention:** Graders must be pure functions of their inputs — no random calls, no time.time(), no external state. If the environment is stochastic (disruptions), the grader receives the final state and evaluates it deterministically. Seed all randomness in the environment reset, not in the grader.

---

## Moderate Pitfalls

---

### Pitfall 9: inference.py Stdout Format Violations

**What goes wrong:** The baseline script `inference.py` uses `[START]`, `[STEP]`, and `[END]` markers in stdout but the format is inconsistent — missing a marker, printing extra lines before `[START]`, emitting non-JSON content between markers, or flushing stdout out of order.

**Why it happens:** `print()` statements added for debugging are left in the code, or the structured output logic is only applied to the happy path (exceptions skip the markers).

**Consequences:** The evaluation pipeline fails to parse the baseline output, recording zero or null scores for all tasks.

**Prevention:**
- Wrap the entire task loop in try/except; emit `[END]` with error status even on exception
- Use `sys.stdout.flush()` after each marker line
- Never print anything before `[START]` — not even import warnings or deprecation notices
- Suppress noisy library imports: `import warnings; warnings.filterwarnings("ignore")`

**Test:** Run `python inference.py 2>/dev/null | grep -E '^\[(START|STEP|END)\]'` and verify every expected marker appears exactly once in the right order.

---

### Pitfall 10: Missing or Wrong Environment Variables in inference.py

**What goes wrong:** `inference.py` references `API_BASE_URL`, `MODEL_NAME`, or `HF_TOKEN` environment variables but they are not set in the HF Space secrets/variables panel. The OpenAI client call raises an authentication or connection error, crashing the baseline run.

**Why it happens:** Developers test locally with `.env` files and forget that HF Spaces needs variables set explicitly in the Settings tab. The Docker container does not inherit the host environment.

**Consequences:** Baseline script crashes silently or emits error output that breaks the stdout parser.

**Prevention:**
```python
import os
api_base = os.environ.get("API_BASE_URL")
model_name = os.environ.get("MODEL_NAME")
hf_token = os.environ.get("HF_TOKEN")

if not api_base or not model_name:
    print("[START]")
    print(json.dumps({"error": "Missing required env vars", "score": 0.0}))
    print("[END]")
    sys.exit(1)
```
Fail fast with a structured error that still satisfies the stdout parser.

---

### Pitfall 11: Docker Image Startup Time Exceeds HF Spaces Timeout

**What goes wrong:** The Space is marked unhealthy because the container takes too long to reach a state where it can accept HTTP requests. HF Spaces has a default `startup_duration_timeout` of 30 minutes, but automated validation may use a shorter liveness window.

**Why it happens:** Heavy dependencies installed at runtime, model downloads on startup, or pip install inside the CMD (instead of during build).

**Consequences:** Automated validation pings arrive before the server is ready, get connection refused, and mark the environment as down.

**Prevention:**
- Install ALL dependencies during `docker build` (RUN pip install), not at container startup
- Use `python:3.11-slim` as base image, not `python:3.11` (saves ~400 MB)
- With pure Python + Pydantic only (per PROJECT.md), the image should build in under 2 minutes and start in under 5 seconds
- Add a brief startup log: `logger.info("Server ready on port 7860")` so build logs confirm readiness

---

### Pitfall 12: Blocking the Main Thread During Reset/Step

**What goes wrong:** A single `/reset` or `/step` call that takes several seconds (e.g., running a full episode simulation synchronously) blocks uvicorn's event loop, making all subsequent requests time out.

**Why it happens:** FastAPI is async but if route handlers are synchronous and computationally heavy, they hold the GIL and block other requests.

**Consequences:** Under the automated evaluation pipeline's concurrent pings, the server appears unresponsive after the first slow call.

**Prevention:** For pure Python grid simulation (no I/O), synchronous handlers are fine as long as per-call computation is fast. Each `step()` should execute in < 10 ms for a 20x20 grid. If state becomes complex, consider `asyncio.to_thread()` for CPU-bound work.

---

### Pitfall 13: Docker Permission Errors Causing Runtime Crashes

**What goes wrong:** The container starts but crashes when trying to write to a temp directory, create a log file, or import a library that needs write access to its cache directory. HF Spaces runs containers as user ID 1000 (non-root).

**Why it happens:** Files copied into the image as root cannot be written by user 1000. Libraries like `huggingface_hub` or `transformers` try to write to `~/.cache/` which may not be writable.

**Consequences:** Import errors or FileNotFoundError at runtime. The server never starts.

**Prevention:**
```dockerfile
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH
WORKDIR $HOME/app
COPY --chown=user . $HOME/app
RUN pip install --no-cache-dir -r requirements.txt
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
```
Since this project uses pure Python + Pydantic (no model downloads), permission issues are low risk — but still follow the pattern above.

---

### Pitfall 14: inference.py Timeout — All 3 Tasks Must Complete in < 20 Minutes

**What goes wrong:** The inference script exceeds the 20-minute wall clock limit specified in PROJECT.md. This may happen if each LLM API call has high latency, or if the agent gets stuck in long episodes due to poor action selection.

**Why it happens:** No per-task timeout is set. A single task can consume the full budget if the agent loops indefinitely.

**Consequences:** The script is killed mid-run. Only completed task scores are recorded; remaining tasks score zero.

**Prevention:**
- Set a hard step limit per episode (e.g., 200 steps max)
- Set a per-task timeout using `signal.alarm()` or threading with `concurrent.futures.ThreadPoolExecutor`
- Budget: 20 min / 3 tasks = ~6 min per task. With LLM latency, assume 2 sec/call, max ~90 LLM calls per task.
- Log elapsed time at each `[STEP]` line so the evaluator can see progress

---

## Minor Pitfalls

---

### Pitfall 15: Grader Always Returns the Same Score (Trivial Grader)

**What goes wrong:** A grader that always returns `1.0` or `0.5` regardless of agent behavior passes format validation but is flagged by human reviewers as a non-meaningful benchmark. It renders the environment useless for RL training signal.

**Why it happens:** Placeholder graders written during scaffolding are not replaced before submission.

**Prevention:** Each grader must produce meaningfully different scores for different agent behaviors. Test with a random agent (should score low), a greedy agent (should score medium), and an optimal path (should score high).

---

### Pitfall 16: "Plagiarized or Trivially Modified" Flag

**What goes wrong:** Judges flag the submission as insufficiently original. This can happen if the environment is a grid world with standard warehouse mechanics that is nearly identical to a published OpenEnv example (e.g., if a Wordle or GridWorld reference implementation is just renamed).

**Why it happens:** Heavy borrowing from example repos without adding novel mechanics.

**Consequences:** Disqualification or significant score penalty on the originality criterion.

**Prevention:** The multi-agent coordination + dynamic disruption angle (blocked aisles mid-episode, robot breakdown, surge orders) is the differentiator. These must be implemented and visible in the grader tasks — not just described in the README. Grader Task 3 (hard mode with disruptions active) is the clearest proof of originality. Ensure all three disruption types fire deterministically in tests so judges can observe them.

**Documentation defense:** README must explicitly describe each disruption type, show example before/after grid states, and reference real-world logistics applicability (Ocado/Amazon Robotics framing from PROJECT.md).

---

### Pitfall 17: State Endpoint Returns Stale or Inconsistent Data

**What goes wrong:** `/state` returns grid state that does not match what `/step` just computed — e.g., robot positions are from a previous step, or `done` flag is false after `/step` already returned `done: true`.

**Why it happens:** Environment state is split across multiple variables that are not updated atomically, or `/state` reads from a different copy of state than `/step` writes to.

**Consequences:** Agents built on top of the environment get confused. Judges testing the API manually will notice the inconsistency during human review.

**Prevention:** Keep a single authoritative `WarehouseState` object. Both `/step` and `/state` read/write the same instance. Never cache state separately.

---

### Pitfall 18: Missing `/` Root Endpoint Health Check

**What goes wrong:** PROJECT.md requires "HF Space URL returns 200." The automated pipeline may ping `GET /` before attempting `/reset`. If the root path is not defined, FastAPI returns a 404, which may be interpreted as an unhealthy Space.

**Why it happens:** FastAPI has no default `/` handler unless explicitly defined.

**Consequences:** Health check failure; automated scoring may not proceed.

**Prevention:**
```python
@app.get("/")
def health_check():
    return {"status": "ok", "env": "WarehouseEnv", "version": "1.0.0"}
```
This doubles as a human-readable confirmation the server is live.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|---|---|---|
| openenv.yaml creation | Missing required field causes silent validate failure | Write yaml first, run `openenv validate` before any other code |
| Endpoint wiring | Router prefix breaks endpoint path contract | Use bare `@app.post("/reset")` at app root, no prefix |
| Pydantic models | Using `dict` return type instead of response_model | Declare `response_model=` on all three endpoints |
| Grader implementation | Score not clamped to [0.0, 1.0] | Always apply `max(0.0, min(1.0, score))` |
| Docker build | Binding to 127.0.0.1 | CMD must include `--host 0.0.0.0` |
| HF Space config | Missing `openenv` tag | Add `tags: [openenv]` to README.md YAML block |
| inference.py | Stdout noise before [START] | Suppress all warnings, add markers in try/finally |
| Pre-submission | app_port mismatch | Audit README YAML and Dockerfile CMD are in sync |
| Human review | Grader appears trivial | Verify score variance across random vs. greedy vs. optimal agent |
| Human review | Environment looks derivative | Disruption mechanics must be live in code, not just README |

---

## Sources

- HF Spaces Docker documentation (official): https://huggingface.co/docs/hub/spaces-sdks-docker — HIGH confidence
- HF Spaces configuration reference (official): https://huggingface.co/docs/hub/spaces-config-reference — HIGH confidence
- HF Spaces overview / networking / lifecycle (official): https://huggingface.co/docs/hub/spaces-overview — HIGH confidence
- OpenEnv spec fields and endpoint contracts: derived from PROJECT.md context + openenv.yaml schema knowledge — MEDIUM confidence (source gated; verify with `openenv validate` locally)
- inference.py stdout format, grader rules, 20-min constraint: PROJECT.md — HIGH confidence (first-party requirements)
