# Informe: agentes de búsqueda y evolutivo para TileUp

IC-6200 Inteligencia Artificial, Tarea Corta 1. Este informe resume la formulación de los dos agentes, sus parámetros y el procedimiento de ajuste, y la comparación experimental. El detalle de cada agente está en [`agente_busqueda.md`](agente_busqueda.md) y [`agente_evolutivo.md`](agente_evolutivo.md); el análisis del juego, en [`juego.md`](juego.md).

## 1. El problema en una línea

Se colocan M fichas en orden sobre un tablero N × N; una ficha puesta junto a otras del mismo color se fusiona con ellas y deja una sola. El orden del concurso es: más fichas colocadas, luego menos celdas ocupadas al final, luego menos tiempo. Dos propiedades guían el diseño: la ocupación final nunca baja de D (los colores distintos de la secuencia), y si D ≤ N²/2 se alcanza D siempre (`juego.md`, P5 y P6). Por eso las instancias que separan a los agentes son las de K grande respecto a N²/2, donde perder es inevitable y cuenta cuántas fichas se logran colocar.

## 2. Formulación de los agentes

### 2.1. Agente de búsqueda (`busqueda`)

Beam search informado por capas, con ancho creciente (anytime).

- **Estado:** (índice de la siguiente ficha, color de cada celda); los valores no afectan la dinámica (P2). **Acción:** colocar la ficha en cualquier celda vacía. **Costo:** el cambio de ocupación (2 − |G|), así que minimizar el costo de camino equivale a minimizar la ocupación final.
- **Capas:** cada capa corresponde a una ficha; se conservan los `ancho` estados con menor `f(s) = ocupación(s) + β · U(s)`, donde U(s) suma, para las próximas fichas, un peso decreciente por cada color que no tiene un hueco libre junto a una ficha propia (esa ficha probablemente sumará una celda). La heurística no es admisible y se declara así.
- **Anytime:** los anchos son 1, 2, 4, 8, … y se conserva la mejor solución de todas las pasadas. Una pasada interrumpida por el reloj no reemplaza a una completa. Si ninguna capa descartó estados, la búsqueda fue exhaustiva y el resultado es óptimo; también se demuestra la optimalidad si se alcanza la cota D.
- **Repetidos:** hash Zobrist de 64 bits del tablero de colores, dentro de cada capa.
- **Esfuerzo informado:** `nodos_expandidos`. La semilla rompe empates entre estados con igual `f`.

### 2.2. Agente evolutivo (`evolutivo`)

Algoritmo genético generacional con elitismo.

- **Individuo:** vector de M enteros en 0..N²−1; el gen _i_ decide dónde va la ficha _i_. Cualquier vector produce una partida legal.
- **Decodificador (el que más pesó):** el gen elige entre las celdas vacías junto a una ficha del mismo color, ordenadas de mayor a menor fusión; si no hay ninguna, se interpreta como una celda directa con reparación cíclica. Es una heurística embebida en el decodificador: el algoritmo evolutivo sigue siendo quien busca, pero no malgasta evaluaciones en jugadas que podían fusionarse y no lo hacen.
- **Aptitud:** `(colocadas, −ocupadas, −ocupación promedio durante la partida)`, lexicográfica. Los dos primeros valores son el orden del concurso; el tercero desempata entre partidas que pierden, cuyo tablero siempre termina lleno.
- **Operadores:** selección por torneo, cruce de un punto, mutación por gen a una celda al azar, reemplazo generacional con 2 élites.
- **Paro:** cota alcanzada, tope de evaluaciones o reloj (corte de seguridad). **Esfuerzo informado:** `evaluaciones_aptitud`. Toda la aleatoriedad sale de `random.Random(seed)`.

## 3. Parámetros y procedimiento de ajuste

Ambos agentes se ajustaron sobre las mismas 18 instancias de entrenamiento, del régimen difícil: (N, K, M) ∈ {(4,12,80), (4,14,80), (5,18,125), (5,21,125), (6,26,180), (6,30,180)} con semillas de instancia 101 a 103. La comparación final usa semillas distintas (201 y 202). Criterio de elección en los dos: mayor promedio de fichas colocadas, con desempate por menor ocupación.

| Agente    | Parámetro             | Valor                               | Cómo se eligió                                                                                                                       |
| --------- | --------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| búsqueda  | `beta`                | 2.0                                 | Rejilla de 72 combinaciones (β × lookahead × decay), medida con una pasada de ancho fijo (16 y 64) para que no dependa de la máquina |
| búsqueda  | `lookahead`           | 4                                   | ídem                                                                                                                                 |
| búsqueda  | `decay`               | 0.6                                 | ídem                                                                                                                                 |
| búsqueda  | anchos                | 1, 2, 4, 8, …                       | Duplicación: el costo total es a lo sumo el doble de la última pasada                                                                |
| evolutivo | decodificador         | C (guiado)                          | Comparación A, B y C                                                                                                                 |
| evolutivo | población             | 200                                 | Barridos con 30 000 y 100 000 evaluaciones; 200 es el más estable entre presupuestos                                                 |
| evolutivo | mutación              | 1.5 genes por hijo (`pm = 1.5 / M`) | Barrido de 1.0 a 8.0; la zona buena es 1.5 a 2.0                                                                                     |
| evolutivo | cruce, torneo, élites | 0.9, 3, 2                           | Valores razonables; sin evidencia clara para cambiarlos                                                                              |
| evolutivo | tope de evaluaciones  | 10 000                              | Para que el resultado dependa de la semilla y no del reloj                                                                           |

Lo que más movió los resultados de cada agente:

- **Búsqueda:** el término de demanda U aporta unas 10 fichas más que usar solo la ocupación (88.3 contra 78.0 con β = 0). Los primeros lugares de la rejilla están dentro de ±0.5 fichas, así que el óptimo es plano.
- **Evolutivo** (18 instancias de entrenamiento; las variantes se midieron una a una):

| Cambio                                                  | Fichas colocadas (media) |
| ------------------------------------------------------- | ------------------------ |
| Versión inicial (decodificador A, aptitud de 2 valores) | 48.5                     |
| + tercer criterio de aptitud                            | 52.9                     |
| + decodificador guiado C                                | ~96.5                    |

Probé y descarté, sin mejora clara: población inicial sembrada con una heurística voraz, reinicios, mutación concentrada en los genes usados y búsqueda local (memético); ver `agente_evolutivo.md`, sección 6.5. Con el decodificador C los parámetros casi no importan (diferencias de ~2 fichas frente a una desviación de ±35).

## 4. Comparación experimental

**Diseño.** 6 configuraciones difíciles × 2 instancias nuevas (semillas 201 y 202) × 10 semillas por agente = 120 corridas por agente; límite de 10 s (el programa le da al agente 9 s) y 4 corridas en paralelo. Es reproducible con `python tools/compare_agents.py`; las corridas individuales están en `results/comparacion_agentes.csv`. Se incluye el agente `aleatorio` como línea base. Entre paréntesis, la desviación estándar.

| Configuración (N, K, M) | `busqueda`                 | `evolutivo`           | `aleatorio`         |
| ----------------------- | -------------------------- | --------------------- | ------------------- |
| (4, 12, 80)             | **79.6** (±1.2) · 18/20    | 68.7 (±8.4) · 2/20    | 17.6 (±2.2) · 0/20  |
| (4, 14, 80)             | **48.6** (±10.5) · 0/20    | 44.7 (±9.1) · 0/20    | 18.0 (±1.9) · 0/20  |
| (5, 18, 125)            | **124.9** (±0.7) · 19/20   | 114.3 (±8.6) · 6/20   | 27.3 (±1.6) · 0/20  |
| (5, 21, 125)            | **75.2** (±4.8) · 0/20     | 71.0 (±4.3) · 0/20    | 26.9 (±1.5) · 0/20  |
| (6, 26, 180)            | **171.6** (±10.2) · 8/20   | 151.4 (±16.5) · 2/20  | 38.7 (±1.8) · 0/20  |
| (6, 30, 180)            | **110.8** (±7.2) · 0/20    | 105.0 (±6.3) · 0/20   | 37.6 (±1.3) · 0/20  |
| **Total**               | **101.8** (±40.4) · 45/120 | 92.5 (±36.5) · 10/120 | 27.7 (±8.5) · 0/120 |

Cada celda es _fichas colocadas (media)_ y _victorias / corridas_. La desviación total es grande porque mezcla configuraciones de tamaños muy distintos.

**Comparación pareada** (misma instancia y misma semilla, 120 pares):

- La búsqueda coloca más fichas en 95 pares, el evolutivo en 15, y hay 10 empates.
- Diferencia media: 9.3 fichas a favor de la búsqueda (IC 95 % aproximado de 7.2 a 11.4). Por configuración varía de 4 a 20 fichas, y en todas el intervalo queda por encima de cero.
- En los 8 pares en que ambos ganan, la búsqueda deja en promedio 2.9 celdas menos ocupadas.
- **Tiempo** (tercer criterio del concurso): el evolutivo termina en 3.4 s en promedio contra 8.6 s de la búsqueda, porque se detiene por su tope de evaluaciones y no usa el resto del límite.

**Régimen fácil.** En las 12 instancias del directorio `instances/` (una corrida con semilla 1 por agente), ambos agentes obtienen exactamente las mismas fichas colocadas y la misma ocupación, en menos de 0.2 s. En `derrota_inevitable` y `tablero_1x1` ninguno puede ganar y los dos coinciden en el mejor resultado posible. Estas instancias no distinguen a los agentes.

## 5. Discusión y límites

- **En el régimen difícil, la búsqueda es mejor, con claridad:** más fichas colocadas en cada configuración, más victorias (45 contra 10) y menos dispersión entre semillas en las configuraciones de más victorias. Es coherente con la naturaleza del problema: es determinista y totalmente observable, y un beam search con una heurística de ocupación aprovecha mucho esa estructura.
- **El evolutivo es competitivo en forma, no en resultado.** En la comparación final coloca 92.5 fichas de media, el 91 % de las de la búsqueda y más de tres veces las del agente aleatorio, y es más rápido. En las instancias de entrenamiento pasó de unas 48 fichas (primera versión) a unas 96. Lo logró incorporando conocimiento del juego en el decodificador, así que su comparación con la búsqueda no es entre dos algoritmos "ciegos": parte de su ventaja sobre el aleatorio viene de esa heurística.
- **El evolutivo no aprovecha el tiempo.** Se detiene por tope de evaluaciones para ser reproducible. Con más evaluaciones ganaría unas 3 fichas (8 000 contra 20 000 evaluaciones en las instancias de entrenamiento), pero el resultado pasaría a depender del reloj y de la máquina.
- **Límites de la evidencia.** (1) El ajuste del evolutivo y el de la búsqueda usaron las mismas instancias de entrenamiento, aunque la comparación final usa otras. (2) Las 12 instancias de la comparación salen de 6 configuraciones; no se probaron otros tamaños (por ejemplo N ≥ 7). (3) Las cifras de las ablaciones del evolutivo vienen de una o dos semillas por instancia y de scripts temporales, no de archivos de resultados; solo la comparación final y los barridos de `tune_evolutivo.py` están guardados. (4) El agente de búsqueda depende del reloj; con otra máquina podría completar un ancho distinto.
- **Conclusión.** Para el concurso, con este ajuste, `busqueda` es el agente a presentar si lo que cuenta es el resultado en tableros difíciles; `evolutivo` es una alternativa más rápida que iguala al otro en el régimen fácil y queda cerca en el difícil.

## 6. Reproducibilidad

```bash
python -m tileup solve instancia.txt --agent busqueda|evolutivo --seed S --time-limit 10
python tools/tune_search.py          # ajuste del agente de búsqueda
python tools/tune_evolutivo.py       # barridos del agente evolutivo
python tools/compare_agents.py       # comparación de esta sección
python -m unittest discover -s tests -t .
```

Misma instancia y misma semilla dan la misma solución, salvo que el reloj corte la ejecución (relevante para `busqueda`).

## 7. Uso de inteligencia artificial

Usé Claude para discutir alternativas de diseño, ejecutar y resumir los experimentos y redactar la documentación. Los resultados citados salen de las corridas guardadas o descritas en `agente_evolutivo.md`.
