"""Programmatic graders for WarehouseEnv tasks.

Each grader reads env._episode internals at episode end (done=True) and
returns a deterministic float in (0.0, 1.0) — strictly exclusive of endpoints.

Called by inference.py after env.step() returns done=True:
    score = GRADER_REGISTRY[task_id](env)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from warehouse_env.env import WarehouseEnv

# Clamp bounds: scores must be strictly in (0, 1), never exactly 0.0 or 1.0
_SCORE_MIN = 0.01
_SCORE_MAX = 0.99


def _clamp_score(score: float) -> float:
    """Clamp a score to (_SCORE_MIN, _SCORE_MAX) for validator compliance."""
    return round(max(_SCORE_MIN, min(_SCORE_MAX, score)), 6)


def grade_solo_delivery(env: "WarehouseEnv") -> float:
    """TASK-01 grader: orders_fulfilled / 5. Pure completion ratio.

    Decision D-19: grade = fulfilled / 5 (max 5 orders).
    """
    if env._episode is None:
        return _SCORE_MIN
    ep = env._episode
    fulfilled = sum(1 for o in ep.orders if o.status == "delivered")
    return _clamp_score(fulfilled / 5)


def grade_coordinated_delivery(env: "WarehouseEnv") -> float:
    """TASK-02 grader: base completion minus collision penalty.

    Decision D-20:
      base = orders_fulfilled / 10
      penalty = 0.05 * total_collisions (from ep.collision_count)
      score = max(0.0, base - penalty)
    """
    if env._episode is None:
        return _SCORE_MIN
    ep = env._episode
    fulfilled = sum(1 for o in ep.orders if o.status == "delivered")
    base = fulfilled / 10
    collision_count = getattr(ep, "collision_count", 0)
    penalty = 0.05 * collision_count
    return _clamp_score(base - penalty)


def grade_crisis_management(env: "WarehouseEnv") -> float:
    """TASK-03 grader: composite of 3 weighted factors.

    Decision D-21:
      order_score   (weight 0.5): fraction of ALL orders (initial + surge) delivered
      survival_score(weight 0.3): fraction of originally-active robots still active at end
      disruption_score(weight 0.2): fraction of surge orders (injected at step 25)
                                    that were delivered

    Initial order count = 20 (from crisis_management TaskConfig).
    Surge order count = 5 (from disruption_events params num_orders=5 at step 25).
    Total possible = 25 orders.
    """
    if env._episode is None:
        return _SCORE_MIN
    ep = env._episode

    total_orders = len(ep.orders)
    fulfilled = sum(1 for o in ep.orders if o.status == "delivered")

    # order_score: fraction of all orders delivered
    order_score = fulfilled / total_orders if total_orders > 0 else 0.0

    # survival_score: fraction of originally-active robots still active
    # ep.robots always has 5 robots for crisis_management; "originally active" = all 5
    total_robots = len(ep.robots)
    active_robots = sum(1 for r in ep.robots if r.is_active)
    survival_score = active_robots / total_robots if total_robots > 0 else 0.0

    # disruption_score: fraction of surge orders delivered
    # Surge orders are those with created_at_step > 0 (injected by DISR-03 mid-episode)
    surge_orders = [o for o in ep.orders if o.created_at_step > 0]
    if surge_orders:
        surge_fulfilled = sum(1 for o in surge_orders if o.status == "delivered")
        disruption_score = surge_fulfilled / len(surge_orders)
    else:
        # No surge happened yet (called before step 25) — treat as neutral
        disruption_score = 0.0

    composite = (
        order_score * 0.5
        + survival_score * 0.3
        + disruption_score * 0.2
    )
    return _clamp_score(composite)


# ---------------------------------------------------------------------------
# Dispatch registry — matches TASK_REGISTRY keys from warehouse_env/tasks.py
# ---------------------------------------------------------------------------

GRADER_REGISTRY: dict[str, Callable[["WarehouseEnv"], float]] = {
    "solo_delivery": grade_solo_delivery,
    "coordinated_delivery": grade_coordinated_delivery,
    "crisis_management": grade_crisis_management,
}
