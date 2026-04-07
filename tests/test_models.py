"""Tests for warehouse_env/models.py — TDD RED phase."""
import pytest
from warehouse_env.models import (
    RobotAction,
    WarehouseAction,
    RobotState,
    OrderState,
    WarehouseObservation,
    WarehouseState,
    WarehouseReward,
)


class TestRobotAction:
    def test_valid_action(self):
        a = RobotAction(robot_id=0, action_type="move_up")
        assert a.robot_id == 0
        assert a.action_type == "move_up"

    def test_invalid_action_type_still_validates(self):
        a = RobotAction(robot_id=0, action_type="INVALID")
        assert a.action_type == "INVALID"

    def test_json_roundtrip(self):
        a = RobotAction(robot_id=1, action_type="pick")
        dumped = a.model_dump()
        restored = RobotAction.model_validate(dumped)
        assert restored.robot_id == 1
        assert restored.action_type == "pick"

    def test_model_dump_json(self):
        a = RobotAction(robot_id=0, action_type="wait")
        json_str = a.model_dump_json()
        assert "robot_id" in json_str


class TestWarehouseAction:
    def test_empty_robots_default(self):
        a = WarehouseAction()
        assert a.robots == []

    def test_with_robot(self):
        ra = RobotAction(robot_id=0, action_type="wait")
        a = WarehouseAction(robots=[ra])
        assert len(a.robots) == 1
        assert a.robots[0].robot_id == 0

    def test_roundtrip(self):
        ra = RobotAction(robot_id=0, action_type="move_down")
        a = WarehouseAction(robots=[ra])
        dumped = a.model_dump()
        restored = WarehouseAction.model_validate(dumped)
        assert restored.robots[0].action_type == "move_down"

    def test_inherits_action(self):
        from openenv.core.env_server.types import Action
        a = WarehouseAction()
        assert isinstance(a, Action)

    def test_model_dump_json(self):
        a = WarehouseAction(robots=[RobotAction(robot_id=0, action_type="wait")])
        json_str = a.model_dump_json()
        assert "robots" in json_str


class TestRobotState:
    def test_basic_instantiation(self):
        r = RobotState(id=0, row=2, col=3, carrying_item=False, assigned_order_id=None, is_active=True)
        assert r.id == 0
        assert r.row == 2
        assert r.col == 3
        assert r.carrying_item is False
        assert r.assigned_order_id is None
        assert r.is_active is True

    def test_to_dict(self):
        r = RobotState(id=0, row=2, col=3, carrying_item=False)
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["id"] == 0

    def test_model_dump_json(self):
        r = RobotState(id=0, row=0, col=0, carrying_item=False)
        json_str = r.model_dump_json()
        assert "carrying_item" in json_str


class TestOrderState:
    def test_basic_instantiation(self):
        o = OrderState(
            order_id="o1",
            shelf_pos=(1, 1),
            packing_pos=(7, 3),
            status="pending",
            created_at_step=0,
        )
        assert o.order_id == "o1"
        assert o.shelf_pos == (1, 1)
        assert o.packing_pos == (7, 3)
        assert o.status == "pending"
        assert o.created_at_step == 0

    def test_defaults(self):
        o = OrderState(order_id="o2", shelf_pos=(1, 1), packing_pos=(8, 2))
        assert o.status == "pending"
        assert o.created_at_step == 0
        assert o.assigned_robot_id is None

    def test_to_dict(self):
        o = OrderState(order_id="o1", shelf_pos=(1, 1), packing_pos=(7, 3))
        d = o.to_dict()
        assert isinstance(d, dict)
        assert d["order_id"] == "o1"

    def test_model_dump_json(self):
        o = OrderState(order_id="o1", shelf_pos=(1, 1), packing_pos=(7, 3))
        json_str = o.model_dump_json()
        assert "order_id" in json_str


class TestWarehouseObservation:
    def test_instantiates_with_defaults(self):
        obs = WarehouseObservation()
        assert obs.grid == []
        assert obs.robots == []
        assert obs.order_queue == []
        assert obs.step_count == 0
        assert obs.max_steps == 50
        assert obs.task_id == "solo_delivery"
        assert obs.description == ""

    def test_inherits_observation(self):
        from openenv.core.env_server.types import Observation
        obs = WarehouseObservation()
        assert isinstance(obs, Observation)

    def test_inherited_done_reward(self):
        obs = WarehouseObservation()
        assert obs.done is False
        assert obs.reward is None

    def test_model_dump_json(self):
        obs = WarehouseObservation()
        json_str = obs.model_dump_json()
        assert "grid" in json_str


class TestWarehouseState:
    def test_instantiates_with_defaults(self):
        s = WarehouseState()
        assert s.task_id == ""
        assert s.grid == []
        assert s.robots == []
        assert s.orders == []
        assert s.done is False

    def test_inherits_state(self):
        from openenv.core.env_server.types import State
        s = WarehouseState()
        assert isinstance(s, State)

    def test_inherited_fields(self):
        s = WarehouseState()
        assert s.episode_id is None
        assert s.step_count == 0

    def test_model_dump_json(self):
        s = WarehouseState()
        json_str = s.model_dump_json()
        assert "task_id" in json_str


class TestWarehouseReward:
    def test_basic_instantiation(self):
        r = WarehouseReward(value=10.0, breakdown={"delivery": 10.0})
        assert r.value == 10.0
        assert r.breakdown["delivery"] == 10.0

    def test_empty_breakdown_default(self):
        r = WarehouseReward(value=0.0)
        assert r.breakdown == {}

    def test_model_dump_json(self):
        r = WarehouseReward(value=5.0, breakdown={"fast_bonus": 5.0})
        json_str = r.model_dump_json()
        assert "value" in json_str
