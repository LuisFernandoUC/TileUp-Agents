"""Agente de búsqueda: beam search informado, anytime, con ancho creciente.

Formulación (detalle y justificación en docs/agente_busqueda.md):

* Estado: (índice de la siguiente ficha, colores de las N*N celdas). Los valores se ignoran
  porque no influyen en la dinámica (la legalidad, la fusión y la ocupación dependen solo del color).
* Operador de sucesión: colocar la siguiente ficha en cualquier celda vacía (motor del juego).
* Costo de una acción: 5 - |G| (en 0..4), es decir, el cambio de ocupación más 3. Todas las
  soluciones completas tienen M acciones, así que el costo de camino es ocupación_final + 3M.
* Prueba de meta: se colocaron las M fichas. Si ninguna rama lo logra, se devuelve la más profunda.

Algoritmo: búsqueda por capas (una capa por ficha). En cada capa se generan todos los sucesores
de los estados del haz, se eliminan los repetidos y se conservan los ``width`` mejores según la
función de evaluación f. Se repite con width = 1, 2, 4, ... mientras quede tiempo, guardando la
mejor solución encontrada. Se detiene antes si:
  * se alcanza la cota inferior admisible (la solución es óptima), o
  * una pasada completa nunca tuvo que descartar estados (la búsqueda fue exhaustiva).

Eficiencia: los sucesores se puntúan sin clonar el estado. Por la propiedad P1 (nunca hay dos
fichas adyacentes del mismo color) la componente G de una colocación en p es p más sus vecinos
del mismo color, así que el efecto de la jugada se calcula mirando solo la vecindad de p. Solo
los ``width`` sucesores elegidos se materializan aplicando la jugada en el motor, que sigue
siendo la única autoridad sobre las reglas.
"""

from __future__ import annotations

import random

from ..engine import EMPTY, GameState, Instance, Status
from .base import Agent, AgentResult, Deadline, register


def solution_key(placed: int, occupied: int) -> tuple[int, int]:
    """Orden del concurso: más fichas colocadas y luego menos celdas ocupadas (menor es mejor)."""
    return (-placed, occupied)


def lower_bound(instance: Instance) -> int:
    """Cota inferior admisible de la ocupación final desde el tablero vacío.

    Un color que aparece nunca desaparece del tablero (la fusión deja una ficha de ese color),
    así que al final hay al menos una celda por cada color distinto de la secuencia.
    """
    return len({t.color for t in instance.tiles})


def zobrist_table(n: int, k: int) -> list[list[int]]:
    """Números aleatorios de 64 bits por (celda, color) para el hash Zobrist del tablero.

    Se generan con una semilla fija: el hash no es una fuente de azar del agente.
    """
    rng = random.Random(0x7117E)
    return [[rng.getrandbits(64) for _ in range(k + 1)] for _ in range(n * n)]


class BeamSearchAgent(Agent):
    name = "busqueda"
    effort_name = "nodos_expandidos"

    def __init__(self, lookahead: int = 4, decay: float = 0.6, beta: float = 2.0,
                 initial_width: int = 1, growth: int = 2, max_width: int | None = None) -> None:
        self.lookahead = lookahead
        self.decay = decay
        self.beta = beta
        self.initial_width = initial_width
        self.growth = growth
        self.max_width = max_width  # tope opcional (para experimentos sin límite de tiempo)

    # ------------------------------------------------------------------ evaluación

    def demand_table(self, instance: Instance) -> list[list[tuple[int, float]]]:
        """Para cada profundidad d: demanda ponderada por color de las próximas fichas."""
        tiles = instance.tiles
        table = []
        for d in range(instance.m + 1):
            demand: dict[int, float] = {}
            weight = 1.0
            for tile in tiles[d : d + self.lookahead]:
                demand[tile.color] = demand.get(tile.color, 0.0) + weight
                weight *= self.decay
            table.append(sorted(demand.items()))
        return table

    @staticmethod
    def slot_counts(state: GameState) -> list[int]:
        """slots[c] = pares (celda vacía, vecina de color c). c tiene "hueco" si slots[c] > 0."""
        colors = state.colors
        nbrs = state._nbrs
        slots = [0] * (state.instance.k + 1)
        for cell, color in enumerate(colors):
            if color == EMPTY:
                for nb in nbrs[cell]:
                    slots[colors[nb]] += 1
        slots[EMPTY] = 0
        return slots

    def evaluate(self, state: GameState, demand: list[tuple[int, float]]) -> float:
        """f(s) = ocupación + beta * demanda próxima sin hueco disponible (menor es mejor).

        Un color tiene hueco si alguna de sus fichas tiene una celda vacía vecina: la próxima
        ficha de ese color puede fusionarse ahí sin aumentar la ocupación. Cada ficha próxima
        cuyo color no tiene hueco probablemente sumará una celda ocupada.

        Esta versión recorre todo el tablero; la búsqueda usa el cálculo incremental equivalente
        de ``_successors`` (las pruebas verifican que ambos coinciden).
        """
        slots = self.slot_counts(state)
        unsupported = sum(w for color, w in demand if slots[color] == 0)
        return state.occupied + self.beta * unsupported

    def _successors(self, parent: GameState, demand: list[tuple[int, float]]):
        """Genera (celda, fichas fusionadas, ocupación, f) de cada sucesor sin clonar el estado."""
        colors = parent.colors
        nbrs = parent._nbrs
        color = parent.instance.tiles[parent.next_index].color
        slots = self.slot_counts(parent)
        beta = self.beta
        occupied = parent.occupied
        for p, cp in enumerate(colors):
            if cp != EMPTY:
                continue
            merged = [q for q in nbrs[p] if colors[q] == color]
            delta: dict[int, int] = {}
            # (A) p deja de estar vacía: se pierden los pares (p, vecina ocupada).
            for nb in nbrs[p]:
                cn = colors[nb]
                if cn != EMPTY:
                    delta[cn] = delta.get(cn, 0) - 1
            for q in merged:
                # (B) q deja de ser ficha de `color`: se pierden los pares (vacía, q), salvo (p, q) ya restado.
                for e in nbrs[q]:
                    if e != p and colors[e] == EMPTY:
                        delta[color] = delta.get(color, 0) - 1
                # (C) q queda vacía: se ganan los pares (q, vecina ocupada) del tablero resultante.
                for nb in nbrs[q]:
                    cn = color if nb == p else colors[nb]  # dos fusionadas nunca son vecinas (P1)
                    if cn != EMPTY:
                        delta[cn] = delta.get(cn, 0) + 1
            # (D) p queda con `color`: se ganan los pares (vecina vacía, p).
            for e in nbrs[p]:
                if colors[e] == EMPTY or e in merged:
                    delta[color] = delta.get(color, 0) + 1
            unsupported = 0.0
            for c, w in demand:
                if slots[c] + delta.get(c, 0) <= 0:
                    unsupported += w
            occ = occupied + 1 - len(merged)
            yield p, merged, occ, occ + beta * unsupported

    # ------------------------------------------------------------------ búsqueda

    def solve(self, instance: Instance, seed: int, deadline: Deadline) -> AgentResult:
        rng = random.Random(seed)
        self._demand = self.demand_table(instance)
        self._zobrist = zobrist_table(instance.n, instance.k)
        bound = lower_bound(instance)
        stats = {"pasadas": 0, "ancho_final": 0, "nodos_generados": 0, "optimo_demostrado": False}
        self._expanded = 0
        self._generated = 0

        # Se reserva tiempo para la compleción rápida por si la primera pasada no alcanza a terminar.
        reserve = min(0.3 * deadline.remaining(), instance.m * 4e-5)
        search_deadline = Deadline(max(0.0, deadline.remaining() - reserve))

        best: GameState | None = None
        width = self.initial_width
        while True:
            result, complete, exhaustive = self.beam_pass(instance, width, rng, search_deadline)
            better = best is None or solution_key(result.placed, result.occupied) < solution_key(best.placed, best.occupied)
            # Una pasada interrumpida solo se usa si aún no hay ninguna completa, para que el
            # resultado dependa lo menos posible de la velocidad de la máquina.
            if better and (complete or best is None):
                best = result
            if not complete:
                break
            stats["pasadas"] += 1
            stats["ancho_final"] = width
            if exhaustive or (best.status is Status.WON and best.occupied <= bound):
                stats["optimo_demostrado"] = True
                break
            if search_deadline.expired() or (self.max_width is not None and width >= self.max_width):
                break
            width *= self.growth

        if not best.is_terminal:
            # La búsqueda se interrumpió sin ninguna pasada completa: se termina la partida con
            # una política rápida para no desperdiciar fichas que se podían colocar.
            best = best.clone()
            stats["completadas_rapido"] = self.complete_quickly(best, deadline)

        stats["nodos_generados"] = self._generated
        return AgentResult(placements=best.placements, effort=self._expanded, stats=stats)

    @staticmethod
    def complete_quickly(state: GameState, deadline: Deadline) -> int:
        """Coloca las fichas restantes junto a una del mismo color si es posible (fusión sin
        aumentar la ocupación) y, si no, en la celda vacía con más vecinas vacías, para que el
        color nuevo quede con hueco y se estorbe lo menos posible a los demás. Devuelve cuántas colocó."""
        colors = state.colors
        nbrs = state._nbrs
        n = state.n
        start = state.placed
        while not state.is_terminal and not deadline.expired():
            color = state.instance.tiles[state.next_index].color
            target = None
            for cell in [i for i, c in enumerate(colors) if c == color]:
                for nb in nbrs[cell]:
                    if colors[nb] == EMPTY:
                        target = nb
                        break
                if target is not None:
                    break
            if target is None:
                most_free = -1
                for cell, c in enumerate(colors):
                    if c == EMPTY:
                        free = sum(1 for nb in nbrs[cell] if colors[nb] == EMPTY)
                        if free > most_free:
                            most_free, target = free, cell
            state.place(*divmod(target, n))
        return state.placed - start

    def beam_pass(self, instance: Instance, width: int, rng: random.Random, deadline: Deadline):
        """Una pasada de beam search con ancho fijo.

        Devuelve (mejor estado, pasada completa, nunca se descartó nada).
        """
        n = instance.n
        full = n * n
        m = instance.m
        zobrist = self._zobrist
        layer: list[tuple[GameState, int]] = [(GameState(instance), 0)]  # (estado, hash)
        best_terminal = None  # (clave de solución, padre, celda)
        exhaustive = True
        complete = True
        for depth in range(m):
            demand = self._demand[depth + 1]
            color = instance.tiles[depth].color
            candidates = []
            seen = set()
            for index, (parent, h) in enumerate(layer):
                if deadline.expired():
                    complete = False
                    break
                self._expanded += 1
                for p, merged, occ, f in self._successors(parent, demand):
                    self._generated += 1
                    child_hash = h ^ zobrist[p][color]
                    for q in merged:
                        child_hash ^= zobrist[q][color]
                    if child_hash in seen:
                        continue
                    seen.add(child_hash)
                    if depth + 1 == m or occ == full:  # sucesor terminal: victoria o derrota
                        key = solution_key(depth + 1, occ)
                        if best_terminal is None or key < best_terminal[0]:
                            best_terminal = (key, parent, p)
                        continue
                    # rng.random() rompe empates entre estados de igual f (depende de la semilla).
                    candidates.append((f, rng.random(), index, p, child_hash))
            if not complete or not candidates:
                break
            if len(candidates) > width:
                exhaustive = False
                candidates.sort()
                del candidates[width:]
            next_layer = []
            for _, _, index, p, child_hash in candidates:
                child = layer[index][0].clone()
                child.place(*divmod(p, n))
                next_layer.append((child, child_hash))
            layer = next_layer

        options = []
        if best_terminal is not None:
            _, parent, p = best_terminal
            terminal = parent.clone()
            terminal.place(*divmod(p, n))
            options.append(terminal)
        options += [state for state, _ in layer]
        best = min(options, key=lambda s: solution_key(s.placed, s.occupied))
        return best, complete, exhaustive and complete


register(BeamSearchAgent)
