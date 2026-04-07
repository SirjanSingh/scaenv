"""Tests for warehouse_env/tasks.py — TaskConfig and TASK_REGISTRY."""
import pytest
from warehouse_env.tasks import TaskConfig, TASK_REGISTRY


class TestTaskRegistry:
    def test_has_three_tasks(self):
        assert len(TASK_REGISTRY) == 3

    def test_has_solo_delivery(self):
        assert "solo_delivery" in TASK_REGISTRY
        assert isinstance(TASK_REGISTRY["solo_delivery"], TaskConfig)

    def test_has_coordinated_delivery(self):
        assert "coordinated_delivery" in TASK_REGISTRY
        assert isinstance(TASK_REGISTRY["coordinated_delivery"], TaskConfig)

    def test_has_crisis_management(self):
        assert "crisis_management" in TASK_REGISTRY
        assert isinstance(TASK_REGISTRY["crisis_management"], TaskConfig)


class TestSoloDelivery:
    def setup_method(self):
        self.task = TASK_REGISTRY["solo_delivery"]

    def test_grid_size(self):
        assert self.task.grid_rows == 10
        assert self.task.grid_cols == 10

    def test_num_robots(self):
        assert self.task.num_robots == 1

    def test_initial_orders_count(self):
        assert len(self.task.initial_orders) == 5

    def test_max_steps(self):
        assert self.task.max_steps == 100

    def test_order_dict_structure(self):
        for order in self.task.initial_orders:
            assert "order_id" in order
            assert "shelf_pos" in order
            assert "packing_pos" in order

    def test_task_id(self):
        assert self.task.task_id == "solo_delivery"


class TestCoordinatedDelivery:
    def setup_method(self):
        self.task = TASK_REGISTRY["coordinated_delivery"]

    def test_grid_size(self):
        assert self.task.grid_rows == 12
        assert self.task.grid_cols == 12

    def test_num_robots(self):
        assert self.task.num_robots == 3

    def test_initial_orders_count(self):
        assert len(self.task.initial_orders) == 10

    def test_max_steps(self):
        assert self.task.max_steps == 150

    def test_has_disruption_events(self):
        assert len(self.task.disruption_events) >= 1
        event = self.task.disruption_events[0]
        assert "step" in event
        assert "type" in event
        assert "params" in event

    def test_order_dict_structure(self):
        for order in self.task.initial_orders:
            assert "order_id" in order
            assert "shelf_pos" in order
            assert "packing_pos" in order


class TestCrisisManagement:
    def setup_method(self):
        self.task = TASK_REGISTRY["crisis_management"]

    def test_grid_size(self):
        assert self.task.grid_rows == 15
        assert self.task.grid_cols == 15

    def test_num_robots(self):
        assert self.task.num_robots == 5

    def test_initial_orders_count(self):
        assert len(self.task.initial_orders) == 20

    def test_max_steps(self):
        assert self.task.max_steps == 200

    def test_has_disruption_events(self):
        assert len(self.task.disruption_events) >= 1

    def test_order_dict_structure(self):
        for order in self.task.initial_orders:
            assert "order_id" in order
            assert "shelf_pos" in order
            assert "packing_pos" in order


class TestTaskConfigDataclass:
    def test_is_dataclass(self):
        import dataclasses
        assert dataclasses.is_dataclass(TaskConfig)

    def test_has_required_fields(self):
        task = TASK_REGISTRY["solo_delivery"]
        assert hasattr(task, "task_id")
        assert hasattr(task, "name")
        assert hasattr(task, "description")
        assert hasattr(task, "grid_rows")
        assert hasattr(task, "grid_cols")
        assert hasattr(task, "num_robots")
        assert hasattr(task, "shelf_positions")
        assert hasattr(task, "packing_positions")
        assert hasattr(task, "robot_start_positions")
        assert hasattr(task, "initial_orders")
        assert hasattr(task, "max_steps")
        assert hasattr(task, "disruption_events")
        assert hasattr(task, "time_bonus_window")
