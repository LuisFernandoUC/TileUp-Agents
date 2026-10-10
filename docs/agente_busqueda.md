# Agente de búsqueda: beam search informado y anytime

Implementación: [`tileup/agents/beam_search.py`](../tileup/agents/beam_search.py). Nombre en la CLI: `busqueda`.

```bash
python -m tileup solve instances/gen_n4_k9_m50.txt --agent busqueda --seed 1 --time-limit 10
```

## 1. Elección del algoritmo

El problema es determinista y completamente observable, así que la partida entera se puede planificar antes
de colocar la primera ficha. El árbol de búsqueda es enorme: hasta (N²)^M caminos (ver [juego.md](juego.md),
§3), y una búsqueda completa (A\*, BFS, ramificación y acotamiento) solo termina en tableros diminutos.
Además, el límite de tiempo obliga a tener siempre una solución lista.

Por eso se eligió **beam search por capas con ancho creciente**, una búsqueda **informada**:

* Cada capa corresponde a una ficha. Todos los nodos de una capa tienen la misma profundidad, así que se comparan
  de forma justa con la función de evaluación.
* Es **anytime**: la primera pasada (ancho 1, equivalente a un greedy) termina enseguida y cada pasada siguiente,
  con el doble de ancho, puede mejorar la solución. Siempre se conserva la mejor encontrada.
* Es **completa en el límite**: si en una pasada ninguna capa tuvo que descartar estados, la búsqueda fue
  exhaustiva (una BFS con eliminación de repetidos) y la solución es óptima.

## 2. Formulación

| Elemento | Definición |
|---|---|
| **Estado** | (índice de la siguiente ficha, color de cada una de las N² celdas). Los valores se omiten: no afectan la legalidad, la fusión ni la ocupación (propiedad P2), solo la "ficha mayor", que no cuenta en el concurso. |
| **Estado inicial** | (0, tablero vacío). |
| **Operador de sucesión** | Colocar la ficha `índice` en cualquier celda vacía y aplicar la fusión del motor. Factor de ramificación = celdas vacías. |
| **Costo de una acción** | 5 − \|G\| ∈ {0, …, 4}, donde \|G\| es el tamaño de la componente fusionada. Es el cambio de ocupación (2 − \|G\|) desplazado en +3 para que ningún costo sea negativo. Toda solución completa tiene exactamente M acciones, así que el costo de camino es *ocupación final + 3M*: minimizar el costo equivale a minimizar la ocupación final. |
| **Prueba de meta** | índice = M (se colocaron todas las fichas). |
| **Si no hay meta alcanzable** | Un estado con el tablero lleno y fichas pendientes es terminal (derrota). Entre las ramas terminales se elige la más profunda, siguiendo el orden del concurso: más fichas colocadas y luego menos celdas ocupadas. |

Detección de repetidos: dentro de cada capa, los estados se identifican con un **hash Zobrist** de 64 bits del
tablero de colores, que se actualiza en O(1) por jugada. Una colisión descartaría por error un estado distinto;
con 64 bits la probabilidad es despreciable (del orden de 10⁻¹⁰ para un millón de estados por capa).

## 3. Función de evaluación (heurística)

Para un estado s cuya siguiente ficha es la número d:

> **f(s) = ocupación(s) + β · U(s)**, y se conservan los `ancho` estados con menor f.

* **ocupación(s)**: celdas ocupadas. Es el costo acumulado g (sin el desplazamiento constante 3d, que es igual en toda la capa).
* **U(s)**: demanda próxima sin hueco. Un color c *tiene hueco* si alguna ficha de color c tiene una celda vacía
  vecina, porque entonces la próxima ficha de c puede colocarse ahí y fusionarse sin aumentar la ocupación.
  Además, tras fusionar, la celda que se libera es vecina de la ficha resultante, así que el color conserva su hueco.
  U suma, para las próximas `lookahead` fichas, el peso decay^i de cada ficha cuyo color no tiene hueco: cada una
  probablemente sumará una celda ocupada.

**Admisibilidad: la heurística NO es admisible, y se declara.** U puede sobreestimar el costo futuro: un color
sin hueco hoy puede ganarlo después (una fusión libera celdas) y entonces esa ficha no suma ocupación. Además,
U no considera fusiones de 3 a 5 fichas, que *reducen* la ocupación. Lo que se pierde:

* No hay garantía de optimalidad por la heurística. De todos modos, beam search tampoco la daría con una heurística
  admisible, porque descarta estados.
* La optimalidad solo se **demuestra** por dos vías independientes de f: (1) alcanzar la cota inferior admisible
  D = cantidad de colores distintos de la secuencia (un color que aparece nunca desaparece del tablero, P5), o
  (2) una pasada exhaustiva. La salida informa `optimo_demostrado=True` en esos casos.

**Cálculo incremental.** Por la propiedad P1 (nunca hay dos fichas vecinas del mismo color), la componente G de
una colocación en p es p más sus vecinas del mismo color. Así, el efecto de la jugada sobre la ocupación y sobre los
huecos se calcula mirando solo la vecindad de p, sin clonar el estado. Solo los `ancho` sucesores elegidos se
aplican de verdad en el motor, que sigue siendo la única autoridad sobre las reglas. Una prueba verifica que el
cálculo incremental coincide con el cálculo completo en miles de sucesores.

## 4. Control del tiempo

* El programa le entrega al agente el límite menos un margen (10 %, entre 0.15 y 1 s) para escribir la solución.
* Las pasadas revisan el tiempo antes de expandir cada nodo. Si una pasada se interrumpe, se descarta, salvo
  que todavía no exista ninguna pasada completa.
* **Compleción rápida**: si se interrumpe incluso la primera pasada (tableros muy grandes con poco tiempo), la
  partida parcial se termina con una regla de costo bajo: junto a una ficha del mismo color si existe; si no, en la
  celda vacía con más vecinas vacías. Se le reserva min(30 % del tiempo, M · 40 µs).

## 5. Parámetros y procedimiento de ajuste

| Parámetro | Valor | Significado |
|---|---|---|
| `beta` (β) | 2.0 | peso de la demanda sin hueco |
| `lookahead` | 4 | fichas próximas consideradas en U |
| `decay` | 0.6 | peso geométrico de la ficha i-ésima |
| `initial_width`, `growth` | 1, 2 | anchos 1, 2, 4, 8, … |

Procedimiento (reproducible con `python tools/tune_search.py`; resultados en
[`results/tuning_busqueda.csv`](../results/tuning_busqueda.csv)):

1. **Instancias de entrenamiento** generadas con semillas 101–103, distintas de las de la comparación experimental,
   en el régimen difícil: (N, K, M) ∈ {(4,12,80), (4,14,80), (5,18,125), (5,21,125), (6,26,180), (6,30,180)}.
   En el régimen fácil (D ≤ N²/2), cualquier ajuste alcanza el óptimo.
2. **Rejilla**: β ∈ {0, 0.25, 0.5, 1, 2, 4} × lookahead ∈ {2, 4, 8, 16} × decay ∈ {0.6, 0.8, 1.0}, es decir, 72 combinaciones.
3. **Medida**: una pasada de ancho **fijo** (16 y 64) por instancia, en lugar de un límite de tiempo. Así el ajuste
   es determinista y no depende de la velocidad de la máquina.
4. **Criterio**: mayor promedio de fichas colocadas; desempate por menor ocupación.

| β | lookahead | decay | colocadas (prom.) | ocupadas (prom.) |
|---|---|---|---|---|
| **2.0** | **4** | **0.6** | **88.33** | 25.53 |
| 1.0 | 4 | 0.8 | 88.22 | 25.44 |
| 0.25 | 16 | 1.0 | 87.97 | 25.53 |
| 0.0 (sin heurística) | – | – | 77.97 | 25.67 |
| 4.0 | 16 | 1.0 (peor) | 70.03 | 25.67 |

Lectura: el término U aporta unas 10 fichas más que usar solo la ocupación (β = 0). Un β demasiado alto con
horizonte largo empeora, porque sacrifica ocupación presente por demanda lejana incierta. Los primeros lugares
están dentro de ±0.5 fichas, así que el óptimo es plano y robusto.

**Alternativa probada y descartada**: exigir huecos *privados*, es decir, que un hueco compartido por dos colores
cuente para uno solo (emparejamiento greedy). Con ancho 16 obtuvo 79–80 fichas contra 84.8 de la heurística
elegida, y es unas 4 veces más lenta por no poder calcularse de forma incremental.

**Comprobación sobre instancias no usadas en el ajuste** (seis configuraciones × semillas 1–3, límite de 3 s):
parámetros iniciales 73.83 fichas, ajustados 73.94. Con tiempo real, el ancho alcanzado compensa la heurística; el
ajuste importa cuando el ancho posible es chico (tableros grandes o límites cortos).

## 6. Evidencia de calidad

* **Contra un resolvedor exacto independiente** (DFS con memoria, en las pruebas): el agente obtiene el óptimo en
  12 instancias diminutas aleatorias (`test_matches_independent_exact_solver_on_tiny_instances`).
* **Tableros 3×3, M = 45**: con una pasada exhaustiva se calculó el óptimo exacto. Con 5 s, el agente lo alcanza en
  3 de 4 instancias medidas (K = 7 semilla 1: 37/37; K = 9: 30/30; K = 11: 13/13; K = 7 semilla 3: 41/45).
* **Régimen fácil**: alcanza la cota D y lo demuestra en milisegundos, incluso en un 20×20 con M = 3000.
* **Régimen difícil** (N ∈ {4,5,6}, K ≈ 0.8–1.0·N², M = 5N², 2 semillas, límite de 5 s): perder es inevitable, y
  el agente coloca entre 1.6 y 3.1 veces más fichas que el mejor de 200 partidas aleatorias (por ejemplo, 6×6 con K = 29:
  121 contra 45).

## 7. Medida de esfuerzo, semilla y determinismo

* **Esfuerzo**: `nodos_expandidos`, es decir, estados cuyos sucesores se generaron, sumados en todas las pasadas.
  También se informan `nodos_generados`, `pasadas`, `ancho_final` y `optimo_demostrado`.
* **Semilla**: rompe empates entre estados con igual f, mediante un número de `random.Random(seed)` asociado a
  cada sucesor. Distintas semillas exploran haces distintos, y eso produce la dispersión entre semillas que pide el informe.
* **Determinismo**: cada pasada es determinista dada la semilla. La única dependencia de la máquina es *cuántas*
  pasadas alcanzan a completarse antes del límite. Para mitigarla, una pasada interrumpida nunca reemplaza a una
  completa, así que el resultado solo puede cambiar en el borde entre dos anchos. Si se alcanza el óptimo
  demostrado, o si se usa `max_width` en experimentos, el resultado es idéntico en cualquier máquina.

## 8. Complejidad

Una pasada de ancho W cuesta O(M · W · N²): por cada uno de los W estados de cada capa se puntúan hasta N² sucesores
en O(1) cada uno, más O(N²) para preparar los huecos del padre. La memoria es O(W · N² + W · M) por capa. Como los anchos
se duplican, el costo total es como mucho el doble del de la última pasada.
