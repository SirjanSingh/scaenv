"""Layered reward calculator for WarehouseEnv.

Called by env.py step() via: reward = calculate_reward(RewardContext(...))

Reward components (REW-01 through REW-07):
  REW-01  delivery:      +10.0 per order successfully delivered this step
  REW-02  fast_bonus:    +5.0 per order delivered within time_bonus_window steps of assignment
  REW-03  collision:     -8.0 per collision pair this step
  REW-04  wasted_step:   -1.0 per robot that chose 'wait' this step
  REW-05  late_penalty:  -3.0 per order delivered AFTER time_bonus_window
  REW-06  reroute_bonus: +3.0 per robot that successfully rerouted around a disrupted cell
  REW-07  timeout:       -10.0 per unfulfilled order when episode ends (is_done=True)

REW-08 (normalization) is handled in graders.py, not here. step() returns raw values.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from warehouse_env.models import OrderState, WarehouseReward

if TYPE_CHECKING:
    pass


@dataclass
class RewardContext:
    """All information calculate_reward needs for one step.

    Built by env.py after _apply_actions resolves positions and pick/drop outcomes.
    """
    # Orders delivered to packing station this step (status changed to "delivered")
    fulfilled_this_step: list[OrderState] = field(default_factory=list)

    # Orders delivered this step that were LATE (delivery_step - assigned_at_step > window)
    # Subset of fulfilled_this_step. Caller builds this — reward.py does not re-check.
    late_this_step: list[OrderState] = field(default_factory=list)

    # Robot IDs that executed 'wait' action this step (REW-04)
    wait_robot_ids: set[int] = field(default_factory=set)

    # Number of collision pairs this step (REW-03, each pair = -8.0)
    collision_pairs: int = 0

    # Robot IDs that successfully rerouted around a newly-disrupted cell (REW-06)
    reroute_robot_ids: set[int] = field(default_factory=set)

    # Orders still unfulfilled when episode ends (REW-07, is_done=True only)
    unfulfilled_at_done: list[OrderState] = field(default_factory=list)

    # True if this is the terminal step (ep.done after increment)
    is_done: bool = False

    # task_config.time_bonus_window — used to decide fast vs late
    task_time_bonus_window: int = 20


def calculate_reward(context: RewardContext) -> WarehouseReward:
    """Compute step reward from RewardContext. Returns WarehouseReward.

    Only non-zero components appear in breakdown dict (D-05).
    """
    breakdown: dict[str, float] = {}

    # REW-01: +10.0 per delivered order
    if context.fulfilled_this_step:
        breakdown["delivery"] = 10.0 * len(context.fulfilled_this_step)

    # REW-02: +5.0 fast bonus per on-time delivery
    on_time = [
        o for o in context.fulfilled_this_step
        if o not in context.late_this_step
    ]
    if on_time:
        breakdown["fast_bonus"] = 5.0 * len(on_time)

    # REW-03: -8.0 per collision pair
    if context.collision_pairs > 0:
        breakdown["collision"] = -8.0 * context.collision_pairs

    # REW-04: -1.0 per waiting robot
    if context.wait_robot_ids:
        breakdown["wasted_step"] = -1.0 * len(context.wait_robot_ids)

    # REW-05: -3.0 per late delivery
    if context.late_this_step:
        breakdown["late_penalty"] = -3.0 * len(context.late_this_step)

    # REW-06: +3.0 per robot that rerouted
    if context.reroute_robot_ids:
        breakdown["reroute_bonus"] = 3.0 * len(context.reroute_robot_ids)

    # REW-07: -10.0 per unfulfilled order at episode end
    if context.is_done and context.unfulfilled_at_done:
        breakdown["timeout"] = -10.0 * len(context.unfulfilled_at_done)

    total = sum(breakdown.values())
    return WarehouseReward(value=total, breakdown=breakdown)
