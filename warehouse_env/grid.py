"""Grid engine for WarehouseEnv.

Uses a dict-based two-layer architecture:
  - _base: static layout (S and P cells set at reset time)
  - _blocked: dynamic disruption overlay (set added at runtime)
  - _robots: robot position overlay (pos -> robot label)

Robots are rendered as their label (e.g. 'R0') in to_2d_list(),
but get_cell() returns the underlying base cell (ignoring robots).
"""

CELL_FREE = "."
CELL_SHELF = "S"
CELL_PACKING = "P"
CELL_BLOCKED = "X"


class Grid:
    """Warehouse grid with dict-based storage and disruption overlay."""

    def __init__(self, rows: int, cols: int) -> None:
        self.rows = rows
        self.cols = cols
        self._base: dict[tuple[int, int], str] = {}   # static layout: S and P cells
        self._blocked: set[tuple[int, int]] = set()    # dynamic disruption overlay
        self._robots: dict[tuple[int, int], str] = {}  # pos -> robot label e.g. "R0"

    # ------------------------------------------------------------------
    # Base layout
    # ------------------------------------------------------------------

    def set_cell(self, r: int, c: int, cell_type: str) -> None:
        """Set static base layout cell (S or P). Used at reset time."""
        self._base[(r, c)] = cell_type

    def get_cell(self, r: int, c: int) -> str:
        """Return the effective cell type at (r, c), NOT including robot overlay.

        Returns CELL_BLOCKED for out-of-bounds coordinates.
        _blocked overlay takes priority over _base.
        """
        if r < 0 or r >= self.rows or c < 0 or c >= self.cols:
            return CELL_BLOCKED
        if (r, c) in self._blocked:
            return CELL_BLOCKED
        return self._base.get((r, c), CELL_FREE)

    # ------------------------------------------------------------------
    # Dynamic blocked overlay
    # ------------------------------------------------------------------

    def add_block(self, r: int, c: int) -> None:
        """Add a dynamic block at (r, c) — e.g. for disruption events."""
        self._blocked.add((r, c))

    def remove_block(self, r: int, c: int) -> None:
        """Remove dynamic block at (r, c). No-op if not present."""
        self._blocked.discard((r, c))

    # ------------------------------------------------------------------
    # Passability
    # ------------------------------------------------------------------

    def is_passable(self, r: int, c: int) -> bool:
        """Return True if a robot can move into (r, c).

        Passable: CELL_FREE and CELL_PACKING (robots must enter to drop).
        Not passable: CELL_BLOCKED (including out-of-bounds) and CELL_SHELF.
        """
        cell = self.get_cell(r, c)
        return cell in (CELL_FREE, CELL_PACKING)

    # ------------------------------------------------------------------
    # Robot overlay
    # ------------------------------------------------------------------

    def place_robot(self, r: int, c: int, label: str) -> None:
        """Place a robot at (r, c) with the given label (e.g. 'R0')."""
        self._robots[(r, c)] = label

    def remove_robot(self, r: int, c: int, label: str) -> None:
        """Remove robot at (r, c) if its label matches. No-op otherwise."""
        if self._robots.get((r, c)) == label:
            del self._robots[(r, c)]

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_2d_list(self) -> list[list[str]]:
        """Build the 2D grid for Observation.

        For each cell: if a robot is present, the cell value is the robot label;
        otherwise the base cell value (via get_cell) is used.
        Returns list of rows, each row is a list of cell strings.
        """
        grid: list[list[str]] = []
        for r in range(self.rows):
            row: list[str] = []
            for c in range(self.cols):
                if (r, c) in self._robots:
                    row.append(self._robots[(r, c)])
                else:
                    row.append(self.get_cell(r, c))
            grid.append(row)
        return grid

    # ------------------------------------------------------------------
    # Episode lifecycle
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear dynamic state (_blocked and _robots) while preserving static layout (_base)."""
        self._blocked.clear()
        self._robots.clear()
