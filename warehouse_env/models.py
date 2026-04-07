"""Pydantic models for WarehouseEnv — actions, observations, state, reward."""
from typing import Optional
from pydantic import BaseModel, Field
from openenv.core.env_server.types import Action, Observation, State


class RobotAction(Action):
    """Per-robot action. action_type is plain str; validation/normalization happens in env.py."""
    robot_id: int = Field(description="Robot ID 0-indexed")
    action_type: str = Field(
        description="move_up|move_down|move_left|move_right|pick|drop|wait"
    )


class WarehouseAction(Action):
    """Top-level action passed to step() — ONE object per tick containing all robot actions."""
    robots: list[RobotAction] = Field(
        default_factory=list,
        description="Per-robot actions. Missing robots get 'wait'.",
    )


class RobotState(BaseModel):
    """Current state of a single robot."""
    id: int
    row: int
    col: int
    carrying_item: bool
    assigned_order_id: Optional[str] = None
    is_active: bool = True

    def to_dict(self) -> dict:
        return self.model_dump()


class OrderState(BaseModel):
    """State of a single warehouse order."""
    order_id: str
    shelf_pos: tuple[int, int]
    packing_pos: tuple[int, int]
    status: str = "pending"  # "pending" | "picked" | "delivered"
    created_at_step: int = 0
    assigned_robot_id: Optional[int] = None
    assigned_at_step: Optional[int] = None  # step when robot picked up this order (for fast-bonus)

    def to_dict(self) -> dict:
        return self.model_dump()


class WarehouseObservation(Observation):
    """Full observation returned by step() and reset().

    Inherits from openenv Observation which adds: done, reward, metadata.
    """
    grid: list[list[str]] = Field(
        default_factory=list,
        description="2D grid; cells R0/R1/S/P/X/.",
    )
    robots: list[RobotState] = Field(default_factory=list)
    order_queue: list[dict] = Field(
        default_factory=list,
        description="Serialized OrderState dicts",
    )
    step_count: int = Field(default=0)
    max_steps: int = Field(default=50)
    task_id: str = Field(default="solo_delivery")
    description: str = Field(
        default="",
        description="Auto-generated natural language summary",
    )


class WarehouseState(State):
    """Full state snapshot — returned by state property.

    Inherits from openenv State which adds: episode_id, step_count.
    """
    task_id: str = Field(default="")
    grid: list[list[str]] = Field(default_factory=list)
    robots: list[dict] = Field(default_factory=list)
    orders: list[dict] = Field(default_factory=list)
    done: bool = Field(default=False)


class WarehouseReward(BaseModel):
    """Reward breakdown for a single step.

    NOT an openenv base type per ENV-06 / research Pattern 7.
    Returned in Observation.metadata['reward_detail'].
    """
    value: float
    breakdown: dict[str, float] = Field(default_factory=dict)
    # Example breakdown keys: delivery, fast_bonus, collision,
    # wasted_step, late_penalty, reroute_bonus, timeout
