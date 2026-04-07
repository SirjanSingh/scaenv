"""Tests for warehouse_env/grid.py — Grid engine."""
import pytest
from warehouse_env.grid import Grid, CELL_FREE, CELL_SHELF, CELL_PACKING, CELL_BLOCKED


class TestGridConstants:
    def test_constants(self):
        assert CELL_FREE == "."
        assert CELL_SHELF == "S"
        assert CELL_PACKING == "P"
        assert CELL_BLOCKED == "X"


class TestGridBasic:
    def test_to_2d_list_empty_grid(self):
        g = Grid(rows=10, cols=10)
        result = g.to_2d_list()
        assert len(result) == 10
        for row in result:
            assert len(row) == 10
            for cell in row:
                assert cell == "."

    def test_set_and_get_shelf(self):
        g = Grid(rows=10, cols=10)
        g.set_cell(1, 1, CELL_SHELF)
        assert g.get_cell(1, 1) == "S"

    def test_set_and_get_packing(self):
        g = Grid(rows=10, cols=10)
        g.set_cell(8, 2, CELL_PACKING)
        assert g.get_cell(8, 2) == "P"

    def test_get_free_cell(self):
        g = Grid(rows=10, cols=10)
        assert g.get_cell(5, 5) == "."

    def test_out_of_bounds_returns_blocked(self):
        g = Grid(rows=10, cols=10)
        assert g.get_cell(-1, 0) == "X"
        assert g.get_cell(0, -1) == "X"
        assert g.get_cell(10, 0) == "X"
        assert g.get_cell(0, 10) == "X"


class TestGridBlocked:
    def test_add_block(self):
        g = Grid(rows=10, cols=10)
        g.add_block(3, 3)
        assert g.get_cell(3, 3) == "X"

    def test_add_block_is_not_passable(self):
        g = Grid(rows=10, cols=10)
        g.add_block(3, 3)
        assert g.is_passable(3, 3) is False

    def test_remove_block(self):
        g = Grid(rows=10, cols=10)
        g.add_block(3, 3)
        g.remove_block(3, 3)
        assert g.get_cell(3, 3) == "."
        assert g.is_passable(3, 3) is True

    def test_remove_block_noop_if_not_present(self):
        g = Grid(rows=10, cols=10)
        g.remove_block(5, 5)  # should not raise
        assert g.get_cell(5, 5) == "."


class TestGridPassability:
    def test_free_cell_is_passable(self):
        g = Grid(rows=10, cols=10)
        assert g.is_passable(5, 5) is True

    def test_shelf_cell_is_not_passable(self):
        g = Grid(rows=10, cols=10)
        g.set_cell(1, 1, CELL_SHELF)
        assert g.is_passable(1, 1) is False

    def test_packing_cell_is_passable(self):
        g = Grid(rows=10, cols=10)
        g.set_cell(8, 2, CELL_PACKING)
        assert g.is_passable(8, 2) is True

    def test_blocked_cell_is_not_passable(self):
        g = Grid(rows=10, cols=10)
        g.add_block(3, 3)
        assert g.is_passable(3, 3) is False

    def test_out_of_bounds_is_not_passable(self):
        g = Grid(rows=10, cols=10)
        assert g.is_passable(-1, 0) is False
        assert g.is_passable(10, 10) is False


class TestGridRobots:
    def test_place_robot(self):
        g = Grid(rows=10, cols=10)
        g.place_robot(2, 3, "R0")
        assert g.to_2d_list()[2][3] == "R0"

    def test_remove_robot(self):
        g = Grid(rows=10, cols=10)
        g.place_robot(2, 3, "R0")
        g.remove_robot(2, 3, "R0")
        assert g.to_2d_list()[2][3] == "."

    def test_remove_robot_restores_base_cell(self):
        g = Grid(rows=10, cols=10)
        g.set_cell(8, 2, CELL_PACKING)
        g.place_robot(8, 2, "R1")
        assert g.to_2d_list()[8][2] == "R1"
        g.remove_robot(8, 2, "R1")
        assert g.to_2d_list()[8][2] == "P"

    def test_remove_robot_noop_if_label_mismatch(self):
        g = Grid(rows=10, cols=10)
        g.place_robot(2, 3, "R0")
        g.remove_robot(2, 3, "R1")  # wrong label — no-op
        assert g.to_2d_list()[2][3] == "R0"

    def test_get_cell_does_not_include_robot(self):
        """get_cell shows base cell; robots appear only in to_2d_list."""
        g = Grid(rows=10, cols=10)
        g.place_robot(2, 3, "R0")
        assert g.get_cell(2, 3) == "."


class TestGridReset:
    def test_reset_clears_blocked_and_robots(self):
        g = Grid(rows=10, cols=10)
        g.set_cell(1, 1, CELL_SHELF)
        g.add_block(3, 3)
        g.place_robot(5, 5, "R0")
        g.reset()
        # blocked removed
        assert g.get_cell(3, 3) == "."
        # robot removed
        assert g.to_2d_list()[5][5] == "."
        # base layout preserved
        assert g.get_cell(1, 1) == "S"

    def test_reset_preserves_base(self):
        g = Grid(rows=10, cols=10)
        g.set_cell(8, 2, CELL_PACKING)
        g.reset()
        assert g.get_cell(8, 2) == "P"


class TestGridCoordinated:
    def test_12x12_grid(self):
        g = Grid(rows=12, cols=12)
        shelves = [(1, 1), (1, 3), (1, 5), (1, 7), (1, 9),
                   (3, 1), (3, 3), (3, 5), (3, 7), (3, 9)]
        packing = [(10, 3), (10, 6), (10, 9)]
        for r, c in shelves:
            g.set_cell(r, c, CELL_SHELF)
        for r, c in packing:
            g.set_cell(r, c, CELL_PACKING)
        grid_2d = g.to_2d_list()
        assert len(grid_2d) == 12
        assert len(grid_2d[0]) == 12
        assert grid_2d[1][1] == "S"
        assert grid_2d[10][3] == "P"
