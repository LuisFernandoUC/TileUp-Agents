"""Pruebas del validador independiente: debe aceptar lo legal y rechazar lo ilegal."""

import random
import unittest
from pathlib import Path

from tileup.engine import GameState, Instance, Tile
from tileup.solution import format_solution
from validator import ValidationInputError, validate_text

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = (ROOT / "instances" / "ejemplo.txt").read_text(encoding="utf-8")
EXAMPLE_SOLUTION = (ROOT / "instances" / "ejemplo_solucion.txt").read_text(encoding="utf-8")
LOSS = "2 4\n5\n1 1\n2 1\n3 1\n4 1\n1 1\n"


class AcceptTest(unittest.TestCase):
    def test_statement_example(self):
        report = validate_text(EXAMPLE, EXAMPLE_SOLUTION)
        self.assertTrue(report.valid, report.errors)
        self.assertEqual((report.placed, report.occupied, report.largest), (6, 3, 6))
        self.assertEqual(report.outcome, "victoria")

    def test_loss_is_legal(self):
        sol = "0 0 0\n1 0 1\n2 1 0\n3 1 1\n# colocadas=4 ocupadas=4 mayor=1\n"
        report = validate_text(LOSS, sol)
        self.assertTrue(report.valid, report.errors)
        self.assertEqual(report.outcome, "derrota")

    def test_partial_solution_is_legal(self):
        report = validate_text(EXAMPLE, "0 0 0\n1 1 1\n# colocadas=2 ocupadas=2 mayor=2\n")
        self.assertTrue(report.valid, report.errors)
        self.assertEqual(report.outcome, "incompleta")

    def test_empty_solution(self):
        report = validate_text(EXAMPLE, "# colocadas=0 ocupadas=0 mayor=0\n")
        self.assertTrue(report.valid, report.errors)

    def test_trace_has_one_entry_per_move(self):
        report = validate_text(EXAMPLE, EXAMPLE_SOLUTION, trace=True)
        self.assertEqual(len(report.trace), 6)


class RejectTest(unittest.TestCase):
    def assertRejected(self, solution, fragment, instance=EXAMPLE):
        report = validate_text(instance, solution)
        self.assertFalse(report.valid)
        self.assertTrue(any(fragment in e for e in report.errors), report.errors)

    def test_occupied_cell(self):
        self.assertRejected("0 0 0\n1 0 0\n# colocadas=2 ocupadas=1 mayor=2\n", "ya ocupada")

    def test_out_of_board(self):
        self.assertRejected("0 4 0\n# colocadas=1 ocupadas=1 mayor=2\n", "fuera del tablero")
        self.assertRejected("0 0 -1\n# colocadas=1 ocupadas=1 mayor=2\n", "fuera del tablero")

    def test_wrong_index_order(self):
        self.assertRejected("1 0 0\n# colocadas=1 ocupadas=1 mayor=1\n", "se esperaba 0")
        self.assertRejected("0 0 0\n0 1 1\n# colocadas=2 ocupadas=2 mayor=2\n", "se esperaba 1")

    def test_more_moves_than_tiles(self):
        sol = EXAMPLE_SOLUTION.replace("# colocadas", "6 3 3\n# colocadas")
        self.assertRejected(sol, "después de terminar")

    def test_move_after_loss(self):
        sol = "0 0 0\n1 0 1\n2 1 0\n3 1 1\n4 0 0\n# colocadas=5 ocupadas=4 mayor=2\n"
        self.assertRejected(sol, "después de terminar", instance=LOSS)

    def test_malformed_move_lines(self):
        self.assertRejected("0 0\n# colocadas=1 ocupadas=1 mayor=2\n", "3 enteros")
        self.assertRejected("0 a 0\n# colocadas=1 ocupadas=1 mayor=2\n", "no enteros")

    def test_comment_line_in_the_middle(self):
        self.assertRejected("0 0 0\n# hola\n1 1 1\n# colocadas=2 ocupadas=2 mayor=2\n", "última línea")

    def test_missing_summary(self):
        self.assertRejected("0 0 0\n", "falta la línea final")

    def test_summary_disagrees_with_replay(self):
        sol = EXAMPLE_SOLUTION.replace("ocupadas=3", "ocupadas=2")
        self.assertRejected(sol, "ocupadas=2")

    def test_summary_missing_field(self):
        self.assertRejected("0 0 0\n# colocadas=1 ocupadas=1\n", "mayor")

    def test_bad_instance_is_an_input_error(self):
        with self.assertRaises(ValidationInputError):
            validate_text("4 3\n2\n1 1\n", "# colocadas=0 ocupadas=0 mayor=0\n")


class DifferentialTest(unittest.TestCase):
    """El motor y el validador son implementaciones separadas: deben coincidir siempre."""

    def test_engine_and_validator_agree_on_random_games(self):
        rng = random.Random(7)
        for _ in range(300):
            n, k = rng.randint(1, 6), rng.randint(1, 6)
            tiles = tuple(Tile(rng.randint(1, k), rng.randint(1, 9)) for _ in range(rng.randint(0, 3 * n * n)))
            state = GameState(Instance(n, k, tiles))
            stop_at = rng.randint(0, len(tiles))  # a veces una partida incompleta
            while not state.is_terminal and state.placed < stop_at:
                state.place(*rng.choice(state.legal_moves()))
            instance_text = f"{n} {k}\n{len(tiles)}\n" + "".join(f"{c} {v}\n" for c, v in tiles)
            report = validate_text(instance_text, format_solution(state))
            self.assertTrue(report.valid, report.errors)
            self.assertEqual((report.placed, report.occupied, report.largest),
                             (state.placed, state.occupied, state.max_value))


if __name__ == "__main__":
    unittest.main()
