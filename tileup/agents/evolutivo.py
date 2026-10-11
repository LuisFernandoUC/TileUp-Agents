"""Agente evolutivo para TileUp: algoritmo genético generacional con elitismo.

Núcleo que conecta el algoritmo con el motor:

* ``genoma_aleatorio``: crea un individuo (el genotipo).
* ``decodificar_a`` / ``_b`` / ``_c``: juegan la partida que describe un genoma (genotipo -> fenotipo).
* ``aptitud_de``: convierte la partida jugada en la aptitud del concurso ``(colocadas, -ocupadas)``.
* ``Evaluador``: decodifica, puntúa y cuenta las evaluaciones (la medida de esfuerzo). Su aptitud añade
  un tercer valor, ``-ocupación promedio``, que desempata entre partidas que pierden.

Algoritmo:

* ``torneo``, ``cruce_un_punto`` y ``mutar``: selección y operadores de variación.
* ``AgenteEvolutivo``: el ciclo evaluar -> seleccionar -> variar -> reemplazar, con su criterio de paro.

Los valores por defecto de los parámetros salen del barrido de ``tools/tune_evolutivo.py``
(ver docs/agente_evolutivo.md).

Representación: un individuo es una lista de M enteros en ``0..N*N-1``; el gen *i* decide dónde va la
ficha *i*. Cómo se interpreta el gen depende del decodificador. En todos, el genoma queda tal cual y
cualquier genoma produce una partida legal:

* Opción A: el gen es la celda (``fila * N + columna``). Si está ocupada al llegar la ficha, se repara
  avanzando a la siguiente celda en orden cíclico hasta encontrar una libre.
* Opción B: el gen es un índice entre las celdas vacías en ese momento.
* Opción C (la usada por defecto): si hay celdas vacías junto a una ficha del mismo color (donde la ficha
  se fusiona y baja la ocupación), el gen elige entre ellas, de mayor a menor tamaño de fusión; si no
  hay ninguna, se comporta como la opción A. El algoritmo evolutivo sigue siendo quien busca, pero no
  gasta evaluaciones en jugadas que no fusionan cuando podían hacerlo.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import NamedTuple

from ..engine import EMPTY, GameState, Instance, neighbors_table
from .base import Agent, AgentResult, Deadline, register

Genoma = list[int]
AptitudConcurso = tuple[int, int]  # (colocadas, -ocupadas): el orden oficial
Aptitud = tuple[int, int, float]  # el orden oficial + (-ocupación promedio) para desempatar
Decodificador = Callable[..., GameState]  # (instancia, genoma, suma_ocupacion=None) -> estado final


def genoma_aleatorio(rng: random.Random, instance: Instance) -> Genoma:
    """Un individuo aleatorio: una celda al azar para cada una de las M fichas.

    Toda la aleatoriedad del agente debe salir del ``rng`` que se recibe (sembrado con la semilla).
    """
    total = instance.n * instance.n
    return [rng.randrange(total) for _ in range(instance.m)]


def _validar_genoma(instance: Instance, genoma: Genoma) -> None:
    if len(genoma) != instance.m:
        raise ValueError(f"el genoma tiene {len(genoma)} genes y la instancia {instance.m} fichas")


def decodificar_a(instance: Instance, genoma: Genoma, suma_ocupacion: list[int] | None = None) -> GameState:
    """Juega con el motor la partida que describe ``genoma`` y devuelve el estado final.

    Cualquier genoma de longitud M produce una partida legal: si la celda del gen está ocupada,
    se prueba la siguiente (módulo N*N). Siempre existe una libre mientras la partida no haya
    terminado, porque ``is_terminal`` incluye el caso de tablero lleno.

    Si la partida termina antes de agotar los genes (derrota), los genes restantes no se usan.
    Si se pasa ``suma_ocupacion`` (lista de un elemento), se le suman las celdas ocupadas tras
    cada jugada: sirve para calcular la ocupación promedio de la partida.
    """
    _validar_genoma(instance, genoma)
    n = instance.n
    total = n * n
    state = GameState(instance)
    colors = state.colors  # referencia viva: place() modifica esta misma lista
    for gen in genoma:
        if state.is_terminal:
            break
        celda = gen % total  # no hace nada si el gen ya está en rango; evita índices negativos
        while colors[celda] != EMPTY:
            celda = (celda + 1) % total
        state.place(celda // n, celda % n)
        if suma_ocupacion is not None:
            suma_ocupacion[0] += state.occupied
    return state


def decodificar_b(instance: Instance, genoma: Genoma, suma_ocupacion: list[int] | None = None) -> GameState:
    """Opción B: el gen es un índice entre las celdas vacías de ese momento (siempre legal, sin reparar)."""
    _validar_genoma(instance, genoma)
    n = instance.n
    state = GameState(instance)
    colors = state.colors
    for gen in genoma:
        if state.is_terminal:
            break
        vacias = [i for i, c in enumerate(colors) if c == EMPTY]
        celda = vacias[gen % len(vacias)]
        state.place(celda // n, celda % n)
        if suma_ocupacion is not None:
            suma_ocupacion[0] += state.occupied
    return state


def decodificar_c(instance: Instance, genoma: Genoma, suma_ocupacion: list[int] | None = None) -> GameState:
    """Opción C: el gen elige entre las celdas donde la ficha se fusiona, y si no hay, como la opción A.

    Por la propiedad P1 (nunca hay dos fichas vecinas del mismo color), el tamaño de la fusión en una
    celda vacía es 1 + el número de vecinas del mismo color. Los candidatos se ordenan por ese
    tamaño (mayor primero) y luego por celda, así que el resultado es determinista.
    """
    _validar_genoma(instance, genoma)
    n = instance.n
    total = n * n
    vecinos = neighbors_table(n)
    fichas = instance.tiles
    state = GameState(instance)
    colors = state.colors
    for gen in genoma:
        if state.is_terminal:
            break
        color = fichas[state.next_index].color
        fusion: dict[int, int] = {}  # celda vacía -> vecinas del mismo color
        for i in range(total):
            if colors[i] == color:
                for vecina in vecinos[i]:
                    if colors[vecina] == EMPTY:
                        fusion[vecina] = fusion.get(vecina, 0) + 1
        if fusion:
            candidatas = sorted(fusion, key=lambda celda: (-fusion[celda], celda))
            celda = candidatas[gen % len(candidatas)]
        else:
            celda = gen % total
            while colors[celda] != EMPTY:
                celda = (celda + 1) % total
        state.place(celda // n, celda % n)
        if suma_ocupacion is not None:
            suma_ocupacion[0] += state.occupied
    return state


DECODIFICADORES: dict[str, Decodificador] = {"A": decodificar_a, "B": decodificar_b, "C": decodificar_c}


def aptitud_de(state: GameState) -> AptitudConcurso:
    """Aptitud lexicográfica, a maximizar: más fichas colocadas y luego menos celdas ocupadas.

    Es el orden del concurso. En una derrota el tablero termina lleno, así que entre las
    partidas que pierden solo importa cuántas fichas lograron colocar.
    """
    return (state.placed, -state.occupied)


class Evaluador:
    """Evalúa individuos y cuenta cuántas simulaciones reales se hicieron.

    ``evaluaciones`` es la medida de esfuerzo del agente evolutivo. Solo ``evaluar`` la
    incrementa; ``jugar`` (para armar la solución final) no cuenta, porque no es parte de la búsqueda.
    """

    def __init__(self, instance: Instance, decodificar: Decodificador = decodificar_a) -> None:
        self.instance = instance
        self.decodificar = decodificar
        self.evaluaciones = 0

    def evaluar(self, genoma: Genoma) -> Aptitud:
        """Aptitud ``(colocadas, -ocupadas, -ocupación promedio)``.

        El tercer valor desempata entre partidas con las mismas fichas y la misma ocupación final
        (por ejemplo, las que pierden): gana la que mantuvo el tablero más libre durante el juego.
        """
        self.evaluaciones += 1
        suma = [0]
        state = self.decodificar(self.instance, genoma, suma)
        colocadas, menos_ocupadas = aptitud_de(state)
        return (colocadas, menos_ocupadas, -suma[0] / max(colocadas, 1))

    def jugar(self, genoma: Genoma) -> GameState:
        return self.decodificar(self.instance, genoma)


# --------------------------------------------------------------------------- individuos y operadores


class Individuo(NamedTuple):
    """Un genoma junto con su aptitud ya calculada.

    Por convención los genomas nunca se modifican en el sitio: los operadores devuelven listas
    nuevas. Así un individuo puede pasar a la siguiente generación (élites) o reutilizarse sin copiarlo.
    """

    genoma: Genoma
    aptitud: Aptitud


def torneo(poblacion: list[Individuo], k: int, rng: random.Random) -> Individuo:
    """Selección por torneo: se sortean k individuos (con reemplazo) y gana el de mayor aptitud.

    Los empates se resuelven por el orden del sorteo, que sale del ``rng``, así que sigue siendo
    determinista para una semilla dada.
    """
    candidatos = [poblacion[rng.randrange(len(poblacion))] for _ in range(k)]
    return max(candidatos, key=lambda individuo: individuo.aptitud)


def cruce_un_punto(a: Genoma, b: Genoma, rng: random.Random) -> tuple[Genoma, Genoma]:
    """Cruce de un punto: dos hijos complementarios (prefijo de uno + sufijo del otro).

    El prefijo deja el tablero exactamente como lo dejaba el padre que lo aportó.
    """
    if len(a) < 2:
        return a[:], b[:]
    punto = rng.randrange(1, len(a))
    return a[:punto] + b[punto:], b[:punto] + a[punto:]


def mutar(genoma: Genoma, pm: float, total_celdas: int, rng: random.Random) -> Genoma:
    """Mutación por gen: cada gen se reemplaza por una celda al azar con probabilidad ``pm``."""
    return [rng.randrange(total_celdas) if rng.random() < pm else gen for gen in genoma]


# --------------------------------------------------------------------------- el agente


class _Parar(Exception):
    """Señal interna para salir del ciclo evolutivo indicando el motivo del paro."""

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


@register
class AgenteEvolutivo(Agent):
    """Algoritmo genético generacional con elitismo.

    Parámetros (los valores por defecto salen del barrido de ``tools/tune_evolutivo.py``):

    * ``poblacion``: tamaño de la población.
    * ``pc``: probabilidad de cruzar una pareja de padres.
    * ``k``: tamaño del torneo.
    * ``elites``: cuántos mejores pasan intactos a la siguiente generación.
    * ``pm``: probabilidad de mutación por gen; si es ``None`` se usa ``pm_factor / M``.
    * ``pm_factor``: genes mutados por hijo en promedio cuando ``pm`` es ``None`` (1.0 = uno por hijo).
    * ``paciencia_fraccion``: fracción del tope de evaluaciones que puede pasar sin mejorar la mejor
      aptitud antes de parar, en (0, 1]. Con 1.0 el estancamiento nunca llega a disparar antes del tope.
    * ``tope_evaluaciones``: presupuesto máximo de evaluaciones de aptitud.
    * ``decodificador``: ``"A"`` (gen = celda, con reparación), ``"B"`` (gen = índice entre las vacías)
      o ``"C"`` (gen = elección entre las celdas que fusionan; ver ``decodificar_c``).

    Paro: el primero que ocurra entre (1) cota alcanzada, (2) estancamiento, (3) tope de
    evaluaciones. El reloj es solo un corte de seguridad. Siempre se evalúa al menos un individuo,
    de modo que haya una solución legal que entregar aunque el tiempo ya se haya agotado.

    El estancamiento se mide en EVALUACIONES y no en generaciones: así no depende del tamaño de la
    población ni de cuántos hijos heredan la aptitud de un padre sin simularse. Además, si una
    generación completa no produce ningún genoma nuevo, la población ya no puede cambiar y se
    considera estancada (evita un bucle sin fin con ``pm = 0`` y ``pc = 0``).
    """

    name = "evolutivo"
    effort_name = "evaluaciones_aptitud"

    def __init__(
        self,
        poblacion: int = 200,
        pc: float = 0.9,
        k: int = 3,
        elites: int = 2,
        pm: float | None = None,
        pm_factor: float = 1.5,
        paciencia_fraccion: float = 1.0,
        tope_evaluaciones: int = 10_000,
        decodificador: str = "C",
    ) -> None:
        if poblacion < 2:
            raise ValueError("la población debe tener al menos 2 individuos")
        if not 0 <= elites < poblacion:
            raise ValueError("elites debe cumplir 0 <= elites < poblacion")
        if k < 1:
            raise ValueError("el torneo debe sortear al menos 1 individuo")
        if not 0.0 <= pc <= 1.0 or (pm is not None and not 0.0 <= pm <= 1.0):
            raise ValueError("pc y pm deben estar en [0, 1]")
        if not 0.0 < paciencia_fraccion <= 1.0:
            raise ValueError("paciencia_fraccion debe estar en (0, 1]")
        if tope_evaluaciones < 1:
            raise ValueError("tope_evaluaciones debe ser positivo")
        if pm_factor <= 0:
            raise ValueError("pm_factor debe ser positivo")
        if decodificador not in DECODIFICADORES:
            raise ValueError("decodificador debe ser 'A', 'B' o 'C'")
        self.poblacion = poblacion
        self.pc = pc
        self.k = k
        self.elites = elites
        self.pm = pm
        self.pm_factor = pm_factor
        self.paciencia_fraccion = paciencia_fraccion
        self.tope_evaluaciones = tope_evaluaciones
        self.decodificador = decodificador

    def solve(self, instance: Instance, seed: int, deadline: Deadline) -> AgentResult:
        rng = random.Random(seed)  # toda la aleatoriedad del agente sale de aquí
        evaluador = Evaluador(instance, decodificar=DECODIFICADORES[self.decodificador])
        total_celdas = instance.n * instance.n
        pm = self.pm if self.pm is not None else min(1.0, self.pm_factor / max(instance.m, 1))
        # Cota (propiedad P5): ganar con tantas celdas ocupadas como colores distintos es óptimo.
        objetivo: AptitudConcurso = (instance.m, -len({ficha.color for ficha in instance.tiles}))
        # Evaluaciones que pueden pasar sin mejorar la mejor aptitud antes de declarar estancamiento.
        limite_estancamiento = max(1, int(self.paciencia_fraccion * self.tope_evaluaciones))
        mejor: Individuo | None = None
        evaluaciones_ultima_mejora = 0  # valor del contador de evaluaciones cuando mejoró `mejor`

        def evaluar(genoma: Genoma) -> Individuo:
            nonlocal mejor, evaluaciones_ultima_mejora
            if mejor is not None:  # el primer individuo siempre se evalúa
                if evaluador.evaluaciones >= self.tope_evaluaciones:
                    raise _Parar("tope_evaluaciones")
                if evaluador.evaluaciones - evaluaciones_ultima_mejora >= limite_estancamiento:
                    raise _Parar("estancamiento")
                if deadline.expired():
                    raise _Parar("reloj")
            individuo = Individuo(genoma, evaluador.evaluar(genoma))
            if mejor is None or individuo.aptitud > mejor.aptitud:
                mejor = individuo
                evaluaciones_ultima_mejora = evaluador.evaluaciones
            if individuo.aptitud[:2] >= objetivo:
                raise _Parar("cota")
            return individuo

        generaciones = 0
        motivo = "estancamiento"
        try:
            poblacion = [evaluar(genoma_aleatorio(rng, instance)) for _ in range(self.poblacion)]
            while True:
                if evaluador.evaluaciones >= self.tope_evaluaciones:
                    raise _Parar("tope_evaluaciones")
                if deadline.expired():
                    raise _Parar("reloj")
                evaluaciones_antes = evaluador.evaluaciones
                poblacion = self._siguiente_generacion(poblacion, evaluar, rng, pm, total_celdas)
                generaciones += 1
                if evaluador.evaluaciones == evaluaciones_antes:
                    # Ningún hijo nuevo: todos copiaron a un padre, la población ya no puede cambiar.
                    raise _Parar("estancamiento")
        except _Parar as fin:
            # Si el paro llega a mitad de una generación, esa generación se descarta, pero `mejor`
            # ya recogió cualquier individuo bueno que se alcanzó a evaluar.
            motivo = fin.motivo

        state = evaluador.jugar(mejor.genoma)
        stats = {
            "generaciones": generaciones,
            "paro": motivo,
            "optimo_alcanzado": motivo == "cota",
            "evaluaciones_ultima_mejora": evaluaciones_ultima_mejora,
        }
        return AgentResult(placements=state.placements, effort=evaluador.evaluaciones, stats=stats)

    def _siguiente_generacion(
        self,
        poblacion: list[Individuo],
        evaluar: Callable[[Genoma], Individuo],
        rng: random.Random,
        pm: float,
        total_celdas: int,
    ) -> list[Individuo]:
        """Reemplazo generacional con elitismo: las élites pasan; el resto son hijos."""
        ordenada = sorted(poblacion, key=lambda individuo: individuo.aptitud, reverse=True)
        nueva = ordenada[: self.elites]
        while len(nueva) < self.poblacion:
            a = torneo(poblacion, self.k, rng)
            b = torneo(poblacion, self.k, rng)
            if rng.random() < self.pc:
                hijo1, hijo2 = cruce_un_punto(a.genoma, b.genoma, rng)
            else:
                hijo1, hijo2 = a.genoma, b.genoma
            for genoma in (mutar(hijo1, pm, total_celdas, rng), mutar(hijo2, pm, total_celdas, rng)):
                # La aptitud es determinista: un hijo idéntico a un padre hereda su aptitud sin simular.
                if genoma == a.genoma:
                    nueva.append(a)
                elif genoma == b.genoma:
                    nueva.append(b)
                else:
                    nueva.append(evaluar(genoma))
                if len(nueva) == self.poblacion:
                    break
        return nueva