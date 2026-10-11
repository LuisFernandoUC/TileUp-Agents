"""Pruebas del agente de búsqueda (beam search)."""

import random
import time
import unittest
from functools import lru_cache
from pathlib import Path

from tileup.agents import Deadline
from tileup.agents.beam_search import BeamSearchAgent, lower_bound
from tileup.engine import GameState, Instance, Tile
from tileup.instance import load_instance, parse_instance
from tools.generate_instance import generate

ROOT = Path(__file__).resolve().parent.parent


def replay(instance, placements):
    state = GameState(instance)
    for r, c in placements:
        state.place(r, c)  # lanza IllegalMoveError si el agente propuso algo ilegal
    return state


def exact_optimum(instance):
    """Resolvedor exacto independiente del agente: DFS con memoria sobre (índice, colores).

    Devuelve la mejor clave (-colocadas, ocupadas) alcanzable. Solo para instancias diminutas.
    """

    @lru_cache(maxsize=None)
    def best(index, colors):
        state = GameState(instance)
        state.colors = list(colors)
        state.next_index = index
        state.occupied = sum(1 for c in colors if c)
        if state.is_terminal:
            return (-state.placed, state.occupied)
        options = []
        for r, c in state.legal_moves():
            child = state.clone()
            child.place(r, c)
            options.append(best(child.next_index, tuple(child.colors)))
        return min(options)

    return best(0, (0,) * (instance.n * instance.n))


def make(n, k, tiles):
    return Instance(n, k, tuple(Tile(c, v) for c, v in tiles))


class EvaluationTest(unittest.TestCase):
    def test_incremental_evaluation_matches_full_evaluation(self):
        agent = BeamSearchAgent()
        rng = random.Random(11)
        checked = 0
        for _ in range(60):
            n, k = rng.randint(1, 5), rng.randint(1, 12)
            inst = make(n, k, [(rng.randint(1, k), 1) for _ in range(rng.randint(1, 3 * n * n))])
            demand = agent.demand_table(inst)
            state = GameState(inst)
            while not state.is_terminal:
                for p, _merged, occ, f in agent._successors(state, demand[state.next_index + 1]):
                    child = state.clone()
                    child.place(*divmod(p, n))
                    self.assertEqual(child.occupied, occ)
                    self.assertAlmostEqual(agent.evaluate(child, demand[child.next_index]), f)
                    checked += 1
                state.place(*rng.choice(state.legal_moves()))
        self.assertGreater(checked, 1000)

    def test_lower_bound_counts_distinct_colors(self):
        self.assertEqual(lower_bound(make(3, 5, [(1, 1), (3, 1), (1, 2), (5, 1)])), 3)
        self.assertEqual(lower_bound(make(3, 5, [])), 0)


class OptimalityTest(unittest.TestCase):
    def solve(self, instance, seconds=10.0, seed=1):
        result = BeamSearchAgent().solve(instance, seed, Deadline(seconds))
        return replay(instance, result.placements), result

    def test_statement_example(self):
        state, result = self.solve(load_instance(ROOT / "instances" / "ejemplo.txt"))
        self.assertEqual((state.placed, state.occupied), (6, 3))
        self.assertTrue(result.stats["optimo_demostrado"])

    def test_alternating_colors_needs_planning(self):
        state, _ = self.solve(load_instance(ROOT / "instances" / "colores_alternos.txt"))
        self.assertEqual((state.placed, state.occupied), (14, 2))

    def test_unavoidable_loss_places_as_many_as_possible(self):
        state, result = self.solve(load_instance(ROOT / "instances" / "derrota_inevitable.txt"))
        self.assertEqual(state.placed, 4)
        self.assertTrue(result.stats["optimo_demostrado"])  # búsqueda exhaustiva

    def test_matches_independent_exact_solver_on_tiny_instances(self):
        rng = random.Random(5)
        for i in range(12):
            n = rng.choice([2, 3])
            k = rng.randint(2, n * n + 1)
            m = rng.randint(4, 10)
            inst = parse_instance(generate(n, k, m, seed=1000 + i))
            with self.subTest(n=n, k=k, m=m):
                state, result = self.solve(inst)
                self.assertTrue(result.stats["optimo_demostrado"])
                self.assertEqual((-state.placed, state.occupied), exact_optimum(inst))

    def test_easy_regime_reaches_lower_bound(self):
        inst = parse_instance(generate(5, 6, 120, seed=3))  # D <= N^2/2: el óptimo es D (P6)
        state, result = self.solve(inst)
        self.assertEqual(state.placed, 120)
        self.assertEqual(state.occupied, lower_bound(inst))


class AnytimeTest(unittest.TestCase):
    def test_respects_deadline_and_returns_legal_solution(self):
        inst = parse_instance(generate(10, 60, 600, seed=9))
        start = time.perf_counter()
        result = BeamSearchAgent().solve(inst, 1, Deadline(0.5))
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 0.75)
        state = replay(inst, result.placements)
        self.assertGreater(state.placed, 0)

    def test_quick_completion_finishes_easy_game(self):
        inst = parse_instance(generate(8, 4, 400, seed=2))
        state = GameState(inst)
        placed = BeamSearchAgent.complete_quickly(state, Deadline(10))
        self.assertEqual(placed, 400)
        self.assertTrue(state.is_terminal)

    def test_more_width_never_hurts_reported_result(self):
        # La mejor solución se conserva entre pasadas: un tope de ancho mayor no empeora.
        inst = parse_instance(generate(4, 14, 80, seed=4))
        keys = []
        for cap in (1, 8, 64):
            result = BeamSearchAgent(max_width=cap).solve(inst, 1, Deadline(60))
            state = replay(inst, result.placements)
            keys.append((-state.placed, state.occupied))
        self.assertEqual(keys, sorted(keys, reverse=True))


class DeterminismTest(unittest.TestCase):
    def test_same_seed_same_solution_with_fixed_width(self):
        inst = parse_instance(generate(5, 22, 125, seed=6))
        runs = [BeamSearchAgent(max_width=16).solve(inst, 7, Deadline(60)).placements for _ in range(2)]
        self.assertEqual(runs[0], runs[1])


if __name__ == "__main__":
    unittest.main()
