"""Motor del juego TileUp.

Implementa exactamente las reglas de la especificación:

* Tablero N x N, cada celda vacía o con una ficha <color, valor>.
* En cada paso se coloca la siguiente ficha de la secuencia en cualquier celda vacía.
* Fusión: sea G la componente conexa (vecindad ortogonal) del mismo color que contiene
  la celda p recién ocupada. Si |G| >= 2, las fichas de G se retiran y en p queda una
  única ficha de ese color cuyo valor es la suma de G. La fusión no encadena.
* Victoria: se colocaron las M fichas. Derrota: quedan fichas y el tablero está lleno.

El motor no conoce a los agentes: solo expone el estado, las jugadas legales y la
operación ``place``. Cualquier jugada ilegal produce ``IllegalMoveError``.

Representación: el tablero se guarda como dos listas planas de longitud N*N
(``colors`` y ``values``), indexadas por ``celda = fila * N + columna``. El color 0
(``EMPTY``) indica una celda vacía. Las listas planas hacen que copiar un estado y
calcular su clave sea barato, lo que importa para los agentes de búsqueda.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import NamedTuple

EMPTY = 0


class Tile(NamedTuple):
    """Ficha <c, v>: color en 1..K y valor entero positivo."""

    color: int
    value: int


@dataclass(frozen=True)
class Instance:
    """Instancia inmutable: dimensión N, cantidad de colores K y secuencia de fichas."""

    n: int
    k: int
    tiles: tuple[Tile, ...]

    @property
    def m(self) -> int:
        return len(self.tiles)


class Status(Enum):
    IN_PROGRESS = "en_curso"
    WON = "victoria"
    LOST = "derrota"


class IllegalMoveError(Exception):
    """Se intentó una jugada que las reglas no permiten."""


class MoveResult(NamedTuple):
    """Resultado de una colocación."""

    tile_index: int  # índice (desde 0) de la ficha colocada
    row: int
    col: int
    group_size: int  # |G|; 1 significa que no hubo fusión
    value: int  # valor final de la ficha que queda en p


@lru_cache(maxsize=None)
def neighbors_table(n: int) -> tuple[tuple[int, ...], ...]:
    """Vecinos ortogonales de cada celda de un tablero n x n (precalculado)."""
    table = []
    for cell in range(n * n):
        r, c = divmod(cell, n)
        nbrs = []
        if r > 0:
            nbrs.append(cell - n)
        if r < n - 1:
            nbrs.append(cell + n)
        if c > 0:
            nbrs.append(cell - 1)
        if c < n - 1:
            nbrs.append(cell + 1)
        table.append(tuple(nbrs))
    return tuple(table)


class GameState:
    """Estado mutable de una partida."""

    __slots__ = ("instance", "n", "colors", "values", "next_index", "occupied", "placements", "_nbrs")

    def __init__(self, instance: Instance) -> None:
        size = instance.n * instance.n
        self.instance = instance
        self.n = instance.n
        self.colors: list[int] = [EMPTY] * size
        self.values: list[int] = [0] * size
        self.next_index = 0  # índice de la primera ficha pendiente
        self.occupied = 0  # celdas ocupadas, mantenido de forma incremental
        self.placements: list[tuple[int, int]] = []  # (fila, columna) de cada colocación
        self._nbrs = neighbors_table(instance.n)

    # ------------------------------------------------------------------ consultas

    @property
    def status(self) -> Status:
        if self.next_index == self.instance.m:
            return Status.WON
        if self.occupied == self.n * self.n:
            return Status.LOST
        return Status.IN_PROGRESS

    @property
    def is_terminal(self) -> bool:
        return self.status is not Status.IN_PROGRESS

    @property
    def placed(self) -> int:
        """Cantidad de fichas colocadas hasta ahora."""
        return self.next_index

    @property
    def remaining(self) -> int:
        return self.instance.m - self.next_index

    @property
    def max_value(self) -> int:
        """Valor de la ficha mayor del tablero (0 si está vacío)."""
        return max(self.values, default=0)

    def next_tile(self) -> Tile | None:
        if self.next_index < self.instance.m:
            return self.instance.tiles[self.next_index]
        return None

    def cell(self, row: int, col: int) -> Tile | None:
        idx = row * self.n + col
        if self.colors[idx] == EMPTY:
            return None
        return Tile(self.colors[idx], self.values[idx])

    def empty_cells(self) -> list[int]:
        """Índices planos de las celdas vacías."""
        return [i for i, c in enumerate(self.colors) if c == EMPTY]

    def legal_moves(self) -> list[tuple[int, int]]:
        """Jugadas legales como (fila, columna). Vacío si la partida terminó."""
        if self.is_terminal:
            return []
        n = self.n
        return [divmod(i, n) for i in self.empty_cells()]

    def key(self) -> tuple:
        """Clave hashable que identifica el estado (para tablas de visitados)."""
        return (self.next_index, tuple(self.colors), tuple(self.values))

    # ------------------------------------------------------------------ acciones

    def place(self, row: int, col: int) -> MoveResult:
        """Coloca la siguiente ficha en (row, col) y aplica la fusión."""
        if self.is_terminal:
            raise IllegalMoveError(f"la partida ya terminó ({self.status.value})")
        n = self.n
        if not (0 <= row < n and 0 <= col < n):
            raise IllegalMoveError(f"celda ({row}, {col}) fuera del tablero {n}x{n}")
        p = row * n + col
        colors = self.colors
        if colors[p] != EMPTY:
            raise IllegalMoveError(f"celda ({row}, {col}) ocupada")

        tile_index = self.next_index
        color, value = self.instance.tiles[tile_index]
        values = self.values
        colors[p] = color
        values[p] = value
        self.occupied += 1

        # G = componente conexa maximal del color `color` que contiene a p (DFS).
        nbrs = self._nbrs
        group = [p]
        seen = {p}
        stack = [p]
        while stack:
            current = stack.pop()
            for nb in nbrs[current]:
                if nb not in seen and colors[nb] == color:
                    seen.add(nb)
                    group.append(nb)
                    stack.append(nb)

        if len(group) >= 2:
            total = 0
            for c in group:
                total += values[c]
                if c != p:
                    colors[c] = EMPTY
                    values[c] = 0
            values[p] = total
            self.occupied -= len(group) - 1

        self.next_index += 1
        self.placements.append((row, col))
        return MoveResult(tile_index, row, col, len(group), values[p])

    def clone(self) -> GameState:
        other = GameState.__new__(GameState)
        other.instance = self.instance
        other.n = self.n
        other.colors = self.colors.copy()
        other.values = self.values.copy()
        other.next_index = self.next_index
        other.occupied = self.occupied
        other.placements = self.placements.copy()
        other._nbrs = self._nbrs
        return other

    # ------------------------------------------------------------------ salida

    def render(self, color_fn=None) -> str:
        """Tablero como texto. ``color_fn(texto, color)`` permite decorar cada ficha."""
        n = self.n
        width = max(3, len(f"{self.instance.k}:{self.max_value}"))
        lines = ["    " + " ".join(f"{c:^{width}}" for c in range(n))]
        for r in range(n):
            cells = []
            for c in range(n):
                idx = r * n + c
                if self.colors[idx] == EMPTY:
                    cells.append(f"{'.':^{width}}")
                else:
                    text = f"{self.colors[idx]}:{self.values[idx]}"
                    text = f"{text:^{width}}"
                    cells.append(color_fn(text, self.colors[idx]) if color_fn else text)
            lines.append(f"{r:>3} " + " ".join(cells))
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"GameState(n={self.n}, colocadas={self.placed}/{self.instance.m}, "
            f"ocupadas={self.occupied}, estado={self.status.value})"
        )
