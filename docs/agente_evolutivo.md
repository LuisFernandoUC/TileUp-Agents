# Agente evolutivo: decisiones de diseño

Implementación: [`tileup/agents/evolutivo.py`](../tileup/agents/evolutivo.py). Nombre en la CLI: `evolutivo`.

```bash
python -m tileup solve instances/gen_n4_k9_m50.txt --agent evolutivo --seed 1 --time-limit 10
```

## Resumen

| Componente        | Lo que elegí                                                                                                    |
| ----------------- | --------------------------------------------------------------------------------------------------------------- |
| Familia           | Algoritmo genético generacional con elitismo                                                                    |
| Individuo         | Vector de M genes enteros; el gen _i_ decide dónde va la ficha _i_ (la interpretación la fija el decodificador) |
| Decodificador     | **C (guiado)**: el gen elige entre las celdas donde la ficha se fusiona; si no hay, se comporta como A          |
| Aptitud           | Lexicográfica `(colocadas, −ocupadas, −ocupación promedio)`, a maximizar                                        |
| Selección         | Torneo de tamaño _k_ = 3                                                                                        |
| Cruce             | De un punto, con probabilidad _pc_ = 0.9                                                                        |
| Mutación          | Por gen, reemplazando la celda por otra al azar, con _pm_ = 1.5 / M                                             |
| Reemplazo         | Generacional con 2 élites                                                                                       |
| Población inicial | Aleatoria, _P_ = 200                                                                                            |
| Paro              | El primero que ocurra: cota alcanzada, tope de 10 000 evaluaciones o reloj (corte de seguridad)                 |
| Esfuerzo          | Evaluaciones de aptitud (simulaciones reales de una partida)                                                    |

## 1. Representación y decodificadores

Cada individuo es una partida completa: un vector de M enteros en `0..N²−1`. Para evaluarlo se decodifica jugando la partida con el `GameState` del motor. Hay tres decodificadores con el mismo genoma y los mismos operadores; cualquier genoma produce una partida legal y el genoma nunca se reescribe. Si la partida termina antes (derrota), los genes restantes no se usan.

- **A (gen = celda).** El gen _i_ es la celda donde se intenta colocar la ficha _i_. Si ya está ocupada, se repara probando la siguiente celda en orden cíclico.
- **B (gen = índice entre las vacías).** El gen es un índice sobre las celdas vacías de ese momento. Siempre es legal sin reparar, pero una mutación temprana cambia qué celdas están vacías y hace que cada gen posterior apunte a otra celda.
- **C (guiada, la usada).** Si hay celdas vacías junto a una ficha del mismo color (donde la ficha se fusiona y baja la ocupación), el gen elige entre ellas, ordenadas de mayor a menor tamaño de fusión y luego por celda. Si no hay ninguna, se comporta como A. Por la propiedad P1 de `docs/juego.md` (nunca hay dos fichas vecinas del mismo color), el tamaño de la fusión en una celda vacía es 1 + el número de vecinas del mismo color, así que calcularlo es barato.

El algoritmo evolutivo sigue siendo quien busca: C solo evita gastar evaluaciones en jugadas que no fusionan cuando podían hacerlo. Es una heurística embebida en el decodificador, y conviene decirlo al comparar este agente con el de búsqueda.

**Por qué empecé por A.** Quería que cualquier individuo fuera jugable, que un cambio pequeño en un gen cambiara poco la partida y que al cruzar los genes del otro padre siguieran significando algo. Con celdas absolutas se cumplen las tres.

## 2. Función de aptitud

Se simula el individuo con el motor y se compara la tupla `(colocadas, −ocupadas, −ocupación promedio)`:

1. Más fichas colocadas.
2. Menos celdas ocupadas al final. Estos dos son exactamente el orden del concurso, así que optimizar la aptitud es optimizar el resultado real. El tiempo no entra, porque haría la aptitud dependiente de la máquina.
3. Menor ocupación promedio durante la partida (suma de las celdas ocupadas tras cada jugada, dividida entre las fichas colocadas). Solo desempata: no altera el orden de los dos primeros.

El tercer criterio existe porque en una derrota el tablero siempre termina lleno, así que entre quienes pierden el segundo criterio no distingue a nadie. `aptitud_de` devuelve solo los dos primeros valores (el orden del concurso) y `Evaluador.evaluar` agrega el tercero.

La aptitud es determinista, así que no se re-simula a las élites ni a los hijos idénticos a un padre. Como esfuerzo se cuentan solo las simulaciones reales.

## 3. Selección, variación y reemplazo

- **Torneo** de tamaño _k_: se sortean _k_ individuos y gana el mejor. Solo necesita comparar tuplas y _k_ controla la presión selectiva con un único parámetro. Los empates los rompe el generador sembrado.
- **Cruce de un punto** con probabilidad _pc_. Produce dos hijos complementarios (prefijo de un padre y sufijo del otro).
- **Mutación por gen** con probabilidad _pm_ = `pm_factor / M`: es decir, en promedio `pm_factor` genes mutados por hijo, lo que mantiene el mismo significado en instancias de distinto tamaño.
- **Reemplazo generacional con elitismo:** los hijos reemplazan a los padres, salvo las 2 élites, que pasan intactas. Así la mejor aptitud nunca empeora y siempre hay algo válido que entregar.

## 4. Criterio de paro

Paro cuando ocurra primero:

1. **Cota alcanzada:** algún individuo gana con ocupación igual a D, la cantidad de colores distintos de la secuencia. Por la propiedad P5 de `docs/juego.md`, eso es óptimo.
2. **Tope de evaluaciones** (10 000).
3. **Reloj:** corte de seguridad, revisado en cada evaluación; se devuelve el mejor individuo hasta ese momento.

Además existe un paro por estancamiento (`paciencia_fraccion`, fracción del tope sin mejorar la mejor aptitud), pero queda desactivado con el valor 1.0. También se declara estancamiento si una generación completa no produce ningún genoma nuevo (evita un bucle sin fin con `pm = 0` y `pc = 0`).

El agente registra en sus estadísticas cuál criterio lo detuvo (`paro`), cuántas generaciones hizo y cuándo fue la última mejora.

**El tope se eligió para que el resultado no dependa del reloj.** Con 100 000 evaluaciones y el decodificador A, una corrida tardaba 6 a 9 s y, con `--time-limit 3`, el reloj la cortaba en un punto que dependía de la carga del equipo: la misma semilla daba soluciones distintas (la prueba `test_same_seed_same_solution` fallaba de forma intermitente). Como el decodificador C cuesta unas 3 veces más por evaluación, el tope final es de 10 000. En las 18 instancias del barrido, la corrida más larga tardó unos 4 s con 8 000 evaluaciones.

## 5. Parámetros finales

| Parámetro                         | Símbolo     | Valor                   |
| --------------------------------- | ----------- | ----------------------- |
| Decodificador                     |             | C                       |
| Tamaño de población               | _P_         | 200                     |
| Mutación (genes mutados por hijo) | `pm_factor` | 1.5                     |
| Probabilidad de cruce             | _pc_        | 0.9                     |
| Tamaño del torneo                 | _k_         | 3                       |
| Élites                            | _e_         | 2                       |
| Paciencia                         |             | 1.0 (sin estancamiento) |
| Tope de evaluaciones              |             | 10 000                  |

## 6. Resultados de los experimentos

Instancias de ajuste: las de entrenamiento del agente de búsqueda (6 configuraciones × semillas de instancia 101 a 103 = 18 instancias, régimen difícil, ver `docs/agente_busqueda.md`, sección 5), generadas con `tools/generate_instance.py`. Métrica principal: fichas colocadas (media). **Son las mismas instancias con las que se ajustaron los parámetros**, así que las cifras de abajo no son una evaluación independiente. Salvo que se indique otra cosa, un mismo tope de evaluaciones en todas las variantes comparadas.

### 6.1. Decodificador A contra B

En `gen_n4_k9_m50`, con 10 semillas y los valores por defecto de entonces (población 50):

| Decodificador | Victorias | Fichas colocadas (media) |
| ------------- | --------- | ------------------------ |
| A             | 6/10      | 48.0                     |
| B             | 3/10      | 43.2                     |

Explicación probable (no verificada): con B, cambiar un gen temprano redefine todos los siguientes. Es una sola instancia.

### 6.2. Tercer criterio de aptitud

54 corridas (18 instancias × 3 semillas), decodificador A:

| Aptitud                                       | Fichas colocadas (media) |
| --------------------------------------------- | ------------------------ |
| `(colocadas, −ocupadas)`                      | 48.48                    |
| `(colocadas, −ocupadas, −ocupación promedio)` | **52.94**                |

La mejora aparece en las 6 configuraciones. Ninguna de las dos variantes gana una sola de estas instancias.

### 6.3. Decodificador guiado C

18 instancias, una semilla, mismo número de evaluaciones:

| Decodificador | Evaluaciones | Fichas colocadas | Victorias | Tiempo medio por corrida |
| ------------- | ------------ | ---------------- | --------- | ------------------------ |
| A             | 20 000       | 48.56            | 0/18      | 2.2 s                    |
| C             | 20 000       | 97.67            | 3/18      | 6.5 s                    |
| C             | 8 000        | 94.44            | 1/18      | 2.4 s                    |

Es la mejora que más pesó. Cada evaluación cuesta unas 3 veces más, pero con 8 000 evaluaciones ya casi no se pierde calidad.

### 6.4. Ajuste de parámetros

Con el decodificador A (tope de 100 000 evaluaciones, 3 semillas por instancia, 54 corridas por configuración, desviación de ±10):

| Parámetro          | Valores → fichas colocadas                                                |
| ------------------ | ------------------------------------------------------------------------- |
| población          | 20: 46.76 · 50: 48.52 · 100: 50.00 · 200: 52.13 · 400: 51.63 · 800: 53.19 |
| _k_ (población 50) | 2: 48.46 · 3: 48.52 · 5: 49.46 · 7: 48.61                                 |

Con tope de 30 000 evaluaciones, 200 es la mejor población (49.26) y 800 queda al nivel de 100 y 400: una población grande necesita presupuesto. Por eso se eligió 200.

`pm_factor` se midió en `gen_n4_k9_m50` (población 50, 10 semillas, victorias): 1.0 → 6 · 1.5 → 7 · 2.0 → 7 · 3.0 → 6 · 4.0 → 4 · 8.0 → 0. La zona buena es 1.5 a 2.0; de 4.0 en adelante empeora con claridad.

Con el decodificador C (tope de 10 000, 54 corridas por configuración, desviación de ±35), los parámetros casi no importan:

| Parámetro   | Valores → fichas colocadas                        |
| ----------- | ------------------------------------------------- |
| población   | 20: 92.56 · 50: 95.61 · 100: 95.06 · 200: 95.65   |
| `pm_factor` | 1.0: 95.00 · 1.5: 97.17 · 2.0: 95.65 · 3.0: 97.76 |

Las diferencias están dentro del ruido; se conservaron 200 y 1.5.

**Sin evidencia para _pc_ ni élites.** El barrido de _pc_ (0.5, 0.7, 0.9, 1.0) y élites (1, 2, 5) se hizo por error con población 2000 y no se repitió. Mostró diferencias menores de 1.5 fichas con ±9, así que se dejaron _pc_ = 0.9 y _e_ = 2.

### 6.5. Experimentos que no se adoptaron

Todos con decodificador C y 18 instancias, y ninguno superó a la configuración actual más allá del ruido:

| Variante                                                                                   | Fichas colocadas | Victorias |
| ------------------------------------------------------------------------------------------ | ---------------- | --------- |
| **configuración actual**                                                                   | **96.7–96.8**    | 3/36      |
| población inicial sembrada con una heurística voraz (10 %)                                 | 96.6             | 2/36      |
| otro orden de celdas cuando no hay fusión, sin siembra                                     | 93.8             | 4/36      |
| …con siembra del 10 %                                                                      | 92.0             | 2/36      |
| …con siembra del 30 %                                                                      | 94.1             | 2/36      |
| reinicio con población nueva tras 2 000 evaluaciones sin mejorar (población 200)           | 97.3             | 5/36      |
| mutar solo el prefijo de genes usados                                                      | 96.2             | 2/36      |
| mutar una ventana de 40 genes antes del fallo                                              | 93.6             | 2/36      |
| ventana de 20 genes                                                                        | 87.0             | 2/36      |
| ventana de 10 genes                                                                        | 85.9             | 1/36      |
| búsqueda local (escalada sobre los genes activos del mejor individuo) cada 40 generaciones | 96.75            | 2/36      |
| …cada 20 generaciones                                                                      | 96.56            | 2/36      |
| …cada 10 generaciones                                                                      | 97.47            | 5/36      |
| …cada 10 generaciones, 3 alternativas por gen                                              | 95.72            | 3/36      |
| …cada 10 generaciones, a los 3 mejores                                                     | 95.25            | 4/36      |

La mutación concentrada cerca del fallo empeora cuanto más se concentra: la causa de una derrota suele estar lejos del final de la partida.

La búsqueda local (versión memética) usó una pasada de primera mejora sobre los genes activos, con un valor alternativo al azar por gen, y sus evaluaciones cuentan dentro del mismo tope de 10 000. La mejor variante gana 0.75 fichas, dentro del ruido; las que gastan más evaluaciones en ella empeoran.

### 6.6. Comparación con los otros agentes

CLI, semilla 1, `--time-limit 10`, sobre las 18 instancias de ajuste (una sola semilla por instancia):

| Agente                                | Fichas colocadas (media) | Victorias |
| ------------------------------------- | ------------------------ | --------- |
| `aleatorio`                           | 28.56                    | 0/18      |
| `evolutivo` (A, antes de las mejoras) | 52.56                    | 0/18      |
| `evolutivo` (actual)                  | 96.50                    | 2/18      |
| `busqueda`                            | 105.67                   | 6/18      |

El evolutivo actual queda cerca de la búsqueda, pero por debajo. Para comparar con rigor hacen falta más semillas e instancias distintas de las de ajuste.

En `gen_n4_k9_m50` las 10 semillas llegan al óptimo (9 celdas ocupadas, parada por cota) con entre 1 y 12 evaluaciones: con el decodificador C esa instancia es trivial y ya no sirve para distinguir configuraciones.

## 7. Reproducibilidad

Toda la aleatoriedad sale de un único `random.Random(seed)` que se pasa por todo el agente; no se usa el generador global. Misma instancia y misma semilla dan la misma solución mientras el agente termine por cota o por tope, que es lo normal con `--time-limit 10`. Si el reloj corta la ejecución (instancias muy grandes o un equipo mucho más lento), el resultado puede depender de la velocidad de la máquina.

## 8. Script de ajuste y resultados

`tools/tune_evolutivo.py` hace un barrido de un parámetro por vez desde un punto de partida (`BASE`):

```bash
python tools/tune_evolutivo.py --solo poblacion pm_factor --tope 10000 --workers 8 --out results/tuning_evolutivo_guiado.csv
```

| Archivo                               | Contenido                                                                |
| ------------------------------------- | ------------------------------------------------------------------------ |
| `results/tuning_evolutivo_guiado.csv` | población y `pm_factor` con el decodificador C (tope 10 000)             |
| `results/tuning_evolutivo_30k.csv`    | población con el decodificador A, tope 30 000                            |
| `results/tuning_evolutivo.csv`        | _pc_ y élites con población 2000 (**configuración incorrecta, no usar**) |
| `results/comparacion_agentes.csv`     | comparación final con el agente de búsqueda (ver `docs/informe.md`)      |

El barrido de población y _k_ con tope 100 000 (decodificador A) y los demás experimentos de las secciones 6.2, 6.3 y 6.5 se hicieron con scripts temporales y no tienen CSV.

## 9. Ideas no probadas

- Una búsqueda local más cara pero más informada (por ejemplo, recorrer todas las alternativas de cada gen o reevaluar solo desde el gen cambiado). La versión simple de 6.5 no mejoró.
- Un decodificador que mire más adelante en la secuencia de fichas (por ejemplo, cuántas fichas de cada color vienen después). Se parecería más al agente de búsqueda.

## 10. Uso de inteligencia artificial

Usé Claude para discutir y comparar alternativas de diseño, tamien para ejecutar y resumir los experimentos de esta sección.
