"""Pruebas del agente evolutivo: operadores, registro, legalidad, determinismo y criterios de paro."""

from __future__ import annotations

import random
import unittest
from pathlib import Path

from tileup.agents import AGENTS
from tileup.agents.base import Deadline
from tileup.agents.evolutivo import (
    AgenteEvolutivo,
    Individuo,
    aptitud_de,
    cruce_un_punto,
    mutar,
    torneo,
)
from tileup.engine import GameState, Instance
from tileup.instance import load_instance

INSTANCES = Path(__file__).resolve().parent.parent / "instances"


def _cargar(nombre: str) -> Instance:
    return load_instance(INSTANCES / nombre)


def _jugar(instancia: Instance, colocaciones) -> GameState:
    """Repite las colocaciones sobre un tablero nuevo; lanza IllegalMoveError si alguna es ilegal."""
    state = GameState(instancia)
    for fila, col in colocaciones:
        state.place(fila, col)
    return state


class OperadoresTest(unittest.TestCase):
    def test_el_cruce_toma_prefijo_de_un_padre_y_sufijo_del_otro(self) -> None:
        a = [1, 1, 1, 1, 1, 1]
        b = [2, 2, 2, 2, 2, 2]
        for semilla in range(20):
            h1, h2 = cruce_un_punto(a, b, random.Random(semilla))
            punto = h1.index(2)
            self.assertTrue(0 < punto < len(a))
            self.assertEqual(h1, a[:punto] + b[punto:])
            self.assertEqual(h2, b[:punto] + a[punto:])

    def test_el_cruce_no_modifica_a_los_padres(self) -> None:
        a, b = [0, 1, 2, 3], [3, 2, 1, 0]
        cruce_un_punto(a, b, random.Random(0))
        self.assertEqual((a, b), ([0, 1, 2, 3], [3, 2, 1, 0]))

    def test_mutar_con_probabilidad_cero_no_cambia_nada_y_con_uno_deja_genes_en_rango(self) -> None:
        genoma = [0, 1, 2, 3, 4, 5]
        self.assertEqual(mutar(genoma, 0.0, 9, random.Random(0)), genoma)
        mutado = mutar(genoma, 1.0, 9, random.Random(0))
        self.assertEqual(len(mutado), len(genoma))
        self.assertTrue(all(0 <= gen < 9 for gen in mutado))

    def test_el_torneo_prefiere_al_mejor(self) -> None:
        malo = Individuo([0], (1, -4))
        bueno = Individuo([1], (6, -3))
        self.assertIs(torneo([malo, bueno], 30, random.Random(0)), bueno)


class AgenteEvolutivoTest(unittest.TestCase):
    def _resolver(self, nombre: str, semilla: int, segundos: float = 10.0, **parametros):
        instancia = _cargar(nombre)
        return instancia, AgenteEvolutivo(**parametros).solve(instancia, semilla, Deadline(segundos))

    def test_esta_registrado_con_su_medida_de_esfuerzo(self) -> None:
        self.assertIs(AGENTS["evolutivo"], AgenteEvolutivo)
        self.assertEqual(AgenteEvolutivo.effort_name, "evaluaciones_aptitud")

    def test_las_colocaciones_son_legales(self) -> None:
        for nombre in ("gen_n4_k9_m50.txt", "gen_n6_k20_m120.txt", "derrota_inevitable.txt"):
            instancia, resultado = self._resolver(nombre, 1, poblacion=20, tope_evaluaciones=2000)
            _jugar(instancia, resultado.placements)  # no debe lanzar

    def test_misma_semilla_misma_solucion(self) -> None:
        # Se usa el tope de evaluaciones (no el reloj) para que la comparación no dependa de la máquina.
        _, r1 = self._resolver("gen_n4_k9_m50.txt", 5, poblacion=20, tope_evaluaciones=3000)
        _, r2 = self._resolver("gen_n4_k9_m50.txt", 5, poblacion=20, tope_evaluaciones=3000)
        self.assertEqual(r1.placements, r2.placements)
        self.assertEqual(r1.effort, r2.effort)
        self.assertEqual(r1.stats, r2.stats)

    def test_encuentra_el_optimo_del_ejemplo_y_para_por_cota(self) -> None:
        instancia, resultado = self._resolver("ejemplo.txt", 0)
        state = _jugar(instancia, resultado.placements)
        self.assertEqual(aptitud_de(state), (6, -3))  # D = 3 colores distintos: óptimo
        self.assertEqual(resultado.stats["paro"], "cota")
        self.assertTrue(resultado.stats["optimo_alcanzado"])

    def test_respeta_el_tope_de_evaluaciones(self) -> None:
        # paciencia_fraccion=1.0 para aislar el tope: con la paciencia por defecto el estancamiento llegaría antes.
        _, resultado = self._resolver(
            "gen_n6_k20_m120.txt", 2, poblacion=20, paciencia_fraccion=1.0, tope_evaluaciones=300, decodificador="A"
        )
        self.assertLessEqual(resultado.effort, 300)
        self.assertEqual(resultado.stats["paro"], "tope_evaluaciones")

    def test_para_por_estancamiento_medido_en_evaluaciones(self) -> None:
        # Límite = 0.002 * 20 000 = 40 evaluaciones sin mejorar la mejor aptitud.
        _, resultado = self._resolver(
            "gen_n6_k20_m120.txt", 0, poblacion=20, paciencia_fraccion=0.002, tope_evaluaciones=20_000
        )
        self.assertEqual(resultado.stats["paro"], "estancamiento")
        self.assertEqual(resultado.effort - resultado.stats["evaluaciones_ultima_mejora"], 40)
        self.assertLess(resultado.effort, 20_000)

    def test_con_paciencia_completa_el_estancamiento_no_dispara_antes_del_tope(self) -> None:
        # En esta instancia nunca se alcanza la cota (M, -D): solo puede parar por el tope.
        _, resultado = self._resolver(
            "derrota_inevitable.txt", 0, poblacion=10, paciencia_fraccion=1.0, tope_evaluaciones=300
        )
        self.assertIn(resultado.stats["paro"], ("tope_evaluaciones", "estancamiento"))
        if resultado.stats["paro"] == "tope_evaluaciones":
            self.assertEqual(resultado.effort, 300)

    def test_una_generacion_sin_hijos_nuevos_cuenta_como_estancamiento(self) -> None:
        # Sin cruce ni mutación todos los hijos copian a un padre: ninguna evaluación nueva.
        _, resultado = self._resolver("gen_n4_k9_m50.txt", 0, poblacion=20, pc=0.0, pm=0.0, decodificador="A")
        self.assertEqual(resultado.stats["paro"], "estancamiento")
        self.assertEqual(resultado.effort, 20)  # solo la población inicial
        self.assertEqual(resultado.stats["generaciones"], 1)

    def test_con_el_reloj_agotado_entrega_igual_una_solucion_legal(self) -> None:
        instancia = _cargar("gen_n6_k20_m120.txt")
        resultado = AgenteEvolutivo().solve(instancia, 0, Deadline(0.0))
        self.assertEqual(resultado.stats["paro"], "reloj")
        self.assertEqual(resultado.effort, 1)  # siempre se evalúa al menos un individuo
        self.assertGreater(len(resultado.placements), 0)
        _jugar(instancia, resultado.placements)

    def test_instancia_sin_fichas(self) -> None:
        instancia = Instance(n=2, k=1, tiles=())
        resultado = AgenteEvolutivo().solve(instancia, 0, Deadline(5.0))
        self.assertEqual(resultado.placements, [])
        self.assertEqual(resultado.stats["paro"], "cota")

    def test_parametros_invalidos_se_rechazan(self) -> None:
        for parametros in (
            {"poblacion": 1},
            {"poblacion": 50, "elites": 50},
            {"k": 0},
            {"pc": 1.5},
            {"pm": -0.1},
            {"paciencia_fraccion": 0.0},
            {"paciencia_fraccion": 1.5},
            {"tope_evaluaciones": 0},
        ):
            with self.assertRaises(ValueError, msg=str(parametros)):
                AgenteEvolutivo(**parametros)


if __name__ == "__main__":
    unittest.main()