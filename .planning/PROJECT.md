# WarehouseEnv — Multi-Agent Coordination OpenEnv

## What This Is

An OpenEnv-compliant benchmark environment where multiple AI agents (robots) navigate a grid warehouse, pick items from shelves, and deliver them to packing stations — while handling dynamic mid-episode disruptions like blocked aisles and robot breakdowns. Built for the Meta x PyTorch / Scaler OpenEnv Hackathon Round 1 by team PyGuys (Sirjan Singh, Eeshan Singh Pokharia, Ritigya Gupta).

## Core Value

A working, spec-compliant OpenEnv submission deployed to HF Spaces before April 8 11:59 PM — judges can run `reset()`, `step()`, and `state()` against it and get valid responses.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] OpenEnv-compliant environment: typed Pydantic Observation/Action/Reward models, `step()`/`reset()`/`state()` endpoints, `openenv.yaml` metadata
- [ ] Grid warehouse simulation: S=Shelf, R=Robot, P=Packing station, X=Blocked, .=Free path; multi-robot agents pick items and deliver to packing stations
- [ ] 3 tasks with programmatic graders (easy → medium → hard), each returning score 0.0–1.0
- [ ] Layered reward function: +10 delivery, +5 fast bonus, -8 collision, -1 wasted step, -3 late, +3 reroute, -10 timeout
- [ ] Dynamic disruptions: blocked aisle (random mid-episode), robot breakdown, surge orders
- [ ] `inference.py` in root using OpenAI client with `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`; emits `[START]`/`[STEP]`/`[END]` stdout format
- [ ] Dockerfile that builds and runs cleanly (2 vCPU / 8 GB constraint)
- [ ] Deployed to Hugging Face Spaces with `openenv` tag; HF Space URL returns 200 and responds to `reset()`
- [ ] README with env description, action/observation spaces, task descriptions, setup instructions, baseline scores

### Out of Scope

- GUI/visualization — scoring is programmatic, no rendering needed for judges
- LLM-based agent graders — pure programmatic graders only (deterministic, reproducible, no API cost)
- Real pathfinding algorithms (A*, Dijkstra) — Manhattan distance heuristic is sufficient for grid demo
- Multi-agent communication protocol — agents act independently, no message passing
- Battery/recharge disruption — cut to stay under time budget (3 disruption types sufficient)

## Context

- **Hackathon**: Meta x PyTorch / Scaler OpenEnv Round 1, deadline April 8 11:59 PM
- **Framework**: OpenEnv spec — `openenv-core` Python package, Pydantic models, `openenv.yaml`, `openenv validate` tool
- **Deployment**: Hugging Face Spaces (Docker SDK), must respond to automated pings
- **Evaluation pipeline**: automated `openenv validate` → baseline script re-run → standard agent run → human review by Meta/HF engineers
- **Framing**: Multi-agent coordination testbed — not a game, but a benchmark for evaluating autonomous agents under dynamic constraints (applicable to real logistics AI, Ocado/Amazon Robotics style systems)
- **Stack**: Pure Python + Pydantic, no heavy deps, minimal Docker image

## Constraints

- **Deadline**: April 8 11:59 PM — every feature decision optimizes for shipping over perfection
- **Runtime**: inference.py must complete all 3 tasks in < 20 min on 2 vCPU / 8 GB RAM
- **API**: All LLM calls via OpenAI client SDK using `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN` env vars
- **Spec**: `openenv validate` must pass — typed models, all 3 endpoints, `openenv.yaml` required
- **Scoring**: Each task grader must return float in [0.0, 1.0]; must be deterministic
- **Stack**: Pure Python + Pydantic only — no NumPy, no pathfinding libs (keeps Docker image tiny)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Pure Python + Pydantic only | Minimal deps = fast Docker build, no version conflicts, fits 8 GB constraint | — Pending |
| Programmatic graders only | Deterministic, no API cost, reproducible across evaluator runs | — Pending |
| Frame as multi-agent coord testbed | Defends "real-world utility" claim — not a game/toy, directly relevant to logistics AI | — Pending |
| Cut battery/recharge disruption | 3 disruption types sufficient; saves ~2h of dev time under deadline | — Pending |
| YOLO mode, coarse granularity | Deadline crunch — minimize planning overhead, maximize execution time | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-07 after initialization*
