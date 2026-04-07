"""WarehouseEnv package — multi-agent warehouse coordination environment."""

# Public re-exports for convenience
from warehouse_env.models import (
    WarehouseAction,
    WarehouseObservation,
    WarehouseState,
    WarehouseReward,
    RobotAction,
    RobotState,
    OrderState,
)

try:
    from warehouse_env.env import WarehouseEnv
except ImportError:
    # env.py is created in Plan 01-02; package is still importable for models-only use
    WarehouseEnv = None  # type: ignore[assignment,misc]

__all__ = [
    "WarehouseEnv",
    "WarehouseAction",
    "WarehouseObservation",
    "WarehouseState",
    "WarehouseReward",
    "RobotAction",
    "RobotState",
    "OrderState",
]
