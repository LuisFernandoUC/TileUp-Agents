"""Pruebas unitarias del motor, aislado de la lectura de archivos y de los agentes."""

import random
import unittest

from tileup.engine import EMPTY, GameState, IllegalMoveError, Instance, Status, Tile


def make(n, k, tiles):
    return GameState(Instance(n=n, k=k, tiles=tuple(Tile(c, v) for c, v in tiles)))


def occupied_cells(state):
    return {divmod(i, state.n): (c, state.values[i]) for i, c in enumerate(state.colors) if c != EMPTY}


class PlacementWithoutMergeTest(unittest.TestCase):
    def test_single_tile_stays_where_placed(self):
        s = make(3, 2, [(1, 4), (1, 1)])
        result = s.place(1, 1)
        self.assertEqual(result.group_size, 1)
        self.assertEqual(result.value, 4)
        self.assertEqual(s.cell(1, 1), Tile(1, 4))
        self.assertEqual(s.occupied, 1)
        self.assertEqual(s.placed, 1)

    def test_adjacent_different_color_does_not_merge(self):
        s = make(3, 2, [(1, 1), (2, 1), (1, 1)])
        s.place(0, 0)
        result = s.place(0, 1)
        self.assertEqual(result.group_size, 1)
        self.assertEqual(occupied_cells(s), {(0, 0): (1, 1), (0, 1): (2, 1)})

    def test_diagonal_same_color_does_not_merge(self):
        s = make(3, 1, [(1, 2), (1, 3), (1, 1)])
        s.place(0, 0)
        result = s.place(1, 1)
        self.assertEqual(result.group_size, 1)
        self.assertEqual(s.occupied, 2)


class MergeTest(unittest.TestCase):
    def test_merge_of_two(self):
        s = make(3, 2, [(1, 2), (1, 3), (2, 1)])
        s.place(0, 0)
        result = s.place(0, 1)
        self.assertEqual(result.group_size, 2)
        self.assertEqual(result.value, 5)
        # La ficha resultante queda en p (la celda recién colocada), no en la otra.
        self.assertEqual(occupied_cells(s), {(0, 1): (1, 5)})
        self.assertEqual(s.occupied, 1)

    def test_merge_of_three_in_a_line(self):
        s = make(3, 2, [(1, 1), (1, 2), (1, 4), (2, 1)])
        s.place(1, 0)
        s.place(1, 2)
        result = s.place(1, 1)
        self.assertEqual(result.group_size, 3)
        self.assertEqual(occupied_cells(s), {(1, 1): (1, 7)})

    def test_merge_of_five_in_a_cross(self):
        s = make(3, 2, [(1, 1), (1, 2), (1, 3), (1, 4), (1, 5)])
        for r, c in [(0, 1), (1, 0), (1, 2), (2, 1)]:
            self.assertEqual(s.place(r, c).group_size, 1)
        result = s.place(1, 1)
        self.assertEqual(result.group_size, 5)
        self.assertEqual(occupied_cells(s), {(1, 1): (1, 15)})

    def test_merge_ignores_other_colors_in_neighbourhood(self):
        s = make(3, 3, [(1, 1), (2, 5), (3, 7), (1, 2)])
        s.place(0, 1)  # color 1
        s.place(1, 0)  # color 2
        s.place(1, 2)  # color 3
        result = s.place(1, 1)  # color 1, vecino de las tres
        self.assertEqual(result.group_size, 2)
        self.assertEqual(occupied_cells(s), {(1, 1): (1, 3), (1, 0): (2, 5), (1, 2): (3, 7)})

    def test_merge_does_not_chain(self):
        # Tras fusionar en (0,1), la ficha resultante (color 1) no se fusiona con nada más,
        # y la ficha de color 2 en (0,2) no se ve afectada.
        s = make(2, 2, [(1, 1), (2, 1), (1, 1)])
        s.place(0, 0)
        s.place(1, 1)
        result = s.place(0, 1)
        self.assertEqual(result.group_size, 2)
        self.assertEqual(occupied_cells(s), {(0, 1): (1, 2), (1, 1): (2, 1)})

    def test_merged_cell_can_merge_again_later(self):
        s = make(3, 1, [(1, 1), (1, 1), (1, 1)])
        s.place(0, 0)
        s.place(0, 1)  # -> (0,1) = 2
        result = s.place(0, 2)  # -> (0,2) = 3
        self.assertEqual(result.value, 3)
        self.assertEqual(occupied_cells(s), {(0, 2): (1, 3)})


class TerminationTest(unittest.TestCase):
    def test_loss_when_board_full_and_tiles_pending(self):
        s = make(2, 4, [(1, 1), (2, 1), (3, 1), (4, 1), (1, 1)])
        for r, c in [(0, 0), (0, 1), (1, 0)]:
            s.place(r, c)
            self.assertIs(s.status, Status.IN_PROGRESS)
        s.place(1, 1)
        self.assertIs(s.status, Status.LOST)
        self.assertTrue(s.is_terminal)
        self.assertEqual(s.placed, 4)
        self.assertEqual(s.legal_moves(), [])

    def test_filling_board_with_last_tile_is_a_win(self):
        s = make(2, 4, [(1, 1), (2, 1), (3, 1), (4, 1)])
        for r, c in [(0, 0), (0, 1), (1, 0), (1, 1)]:
            s.place(r, c)
        self.assertEqual(s.occupied, 4)
        self.assertIs(s.status, Status.WON)

    def test_merge_on_last_free_cell_avoids_loss(self):
        s = make(2, 3, [(1, 1), (2, 1), (3, 1), (1, 1), (2, 1)])
        for r, c in [(0, 0), (0, 1), (1, 1)]:
            s.place(r, c)
        s.place(1, 0)  # color 1 junto a (0,0): fusión, se libera (0,0)
        self.assertIs(s.status, Status.IN_PROGRESS)
        self.assertEqual(s.occupied, 3)

    def test_one_by_one_board(self):
        s = make(1, 1, [(1, 5), (1, 5)])
        s.place(0, 0)
        self.assertIs(s.status, Status.LOST)

    def test_win_after_all_tiles(self):
        s = make(2, 1, [(1, 1), (1, 1)])
        s.place(0, 0)
        self.assertIs(s.status, Status.IN_PROGRESS)
        s.place(0, 1)
        self.assertIs(s.status, Status.WON)
        self.assertIsNone(s.next_tile())

    def test_empty_sequence_is_won_from_the_start(self):
        s = make(2, 1, [])
        self.assertIs(s.status, Status.WON)


class IllegalMoveTest(unittest.TestCase):
    def test_occupied_cell(self):
        s = make(2, 2, [(1, 1), (2, 1)])
        s.place(0, 0)
        with self.assertRaises(IllegalMoveError):
            s.place(0, 0)
        self.assertEqual(s.placed, 1)  # el intento ilegal no consume la ficha

    def test_out_of_bounds(self):
        s = make(2, 1, [(1, 1)])
        for r, c in [(-1, 0), (0, -1), (2, 0), (0, 2)]:
            with self.assertRaises(IllegalMoveError):
                s.place(r, c)
        self.assertEqual(s.placed, 0)

    def test_move_after_game_over(self):
        s = make(2, 1, [(1, 1)])
        s.place(0, 0)
        with self.assertRaises(IllegalMoveError):
            s.place(1, 1)


class StateUtilitiesTest(unittest.TestCase):
    def test_clone_is_independent(self):
        s = make(2, 2, [(1, 1), (2, 1)])
        s.place(0, 0)
        t = s.clone()
        t.place(1, 1)
        self.assertEqual(s.placed, 1)
        self.assertEqual(s.occupied, 1)
        self.assertEqual(s.placements, [(0, 0)])
        self.assertEqual(t.placements, [(0, 0), (1, 1)])

    def test_key_identifies_equal_states(self):
        a = make(2, 1, [(1, 1), (1, 1)])
        b = a.clone()
        a.place(0, 0)
        a.place(0, 1)
        b.place(1, 0)
        b.place(1, 1)
        self.assertNotEqual(a.key(), b.key())
        c = make(2, 1, [(1, 1), (1, 1)])
        c.place(1, 1)
        c.place(0, 1)
        self.assertEqual(a.key(), c.key())  # mismo tablero por caminos distintos

    def test_branching_factor_equals_empty_cells(self):
        s = make(3, 3, [(1, 1), (2, 1), (3, 1)])
        self.assertEqual(len(s.legal_moves()), 9)
        s.place(0, 0)
        s.place(2, 2)
        self.assertEqual(len(s.legal_moves()), 7)


class RandomPlayInvariantsTest(unittest.TestCase):
    """Partidas aleatorias (con semilla fija) para verificar invariantes de las reglas."""

    def check_invariants(self, s, placed_value_sum):
        n = s.n
        nonempty = [i for i, c in enumerate(s.colors) if c != EMPTY]
        self.assertEqual(s.occupied, len(nonempty))
        # La fusión conserva la suma de valores.
        self.assertEqual(sum(s.values), placed_value_sum)
        for i in nonempty:
            self.assertGreater(s.values[i], 0)
            r, c = divmod(i, n)
            # Como G es maximal, nunca quedan dos fichas adyacentes del mismo color.
            if c + 1 < n:
                self.assertNotEqual(s.colors[i], s.colors[i + 1])
            if r + 1 < n:
                self.assertNotEqual(s.colors[i], s.colors[i + n])

    def test_invariants_hold_in_random_games(self):
        rng = random.Random(2026)
        for _ in range(200):
            n = rng.randint(1, 6)
            k = rng.randint(1, 5)
            m = rng.randint(0, 3 * n * n)
            tiles = [(rng.randint(1, k), rng.randint(1, 9)) for _ in range(m)]
            s = make(n, k, tiles)
            value_sum = 0
            while not s.is_terminal:
                tile = s.next_tile()
                r, c = rng.choice(s.legal_moves())
                s.place(r, c)
                value_sum += tile.value
                self.check_invariants(s, value_sum)
            if s.status is Status.WON:
                self.assertEqual(s.placed, m)
            else:
                self.assertLess(s.placed, m)
                self.assertEqual(s.occupied, n * n)


if __name__ == "__main__":
    unittest.main()
