# TileUp-Agents

Agentes de búsqueda y evolutivos para el juego TileUp (IC-6200 Inteligencia Artificial, Tarea Corta 1).
El informe con la formulación de los agentes, el ajuste de parámetros y la comparación experimental está en
[docs/informe.md](docs/informe.md).

> Estado actual: motor, validador independiente, punto de entrada `solve`, agente de búsqueda (`busqueda`),
> agente evolutivo (`evolutivo`), agente de referencia (`aleatorio`), modo de juego manual y pruebas.

## Agentes

| Nombre | Algoritmo | Esfuerzo informado | Documentación |
|---|---|---|---|
| `busqueda` | Beam search informado y anytime, con ancho creciente | `nodos_expandidos` | [docs/agente_busqueda.md](docs/agente_busqueda.md) |
| `evolutivo` | Algoritmo genético generacional con elitismo y decodificador guiado por fusiones | `evaluaciones_aptitud` | [docs/agente_evolutivo.md](docs/agente_evolutivo.md) |
| `aleatorio` | Línea base: celda vacía al azar (no es uno de los dos agentes de la tarea) | `jugadas_evaluadas` | – |

## Requisitos

- Python 3.10 o superior. **No hay dependencias externas**: todo usa la biblioteca estándar.

## Inicio rápido (Makefile)

Un solo comando resuelve una instancia y valida la solución, sin instalar nada:

```bash
make run INSTANCIA=instances/gen_n4_k9_m50.txt AGENTE=busqueda SEMILLA=1 LIMITE=10
make test          # todas las pruebas
make help          # lista el resto de objetivos
```

| Objetivo | Qué hace |
|---|---|
| `make run` | resuelve `INSTANCIA` con `AGENTE`, `SEMILLA` y `LIMITE` (s) y la valida; la solución queda en `solutions/` |
| `make test` | corre las pruebas |
| `make instancias` | regenera en `instances/comparacion/` las 12 instancias de la comparación (6 configuraciones × semillas 201 y 202) |
| `make soluciones` | resuelve esas 12 instancias con los tres agentes (semilla 1) y valida cada solución; quedan en `results/soluciones/` |
| `make validar` | valida con el validador independiente las soluciones guardadas en `results/soluciones/` |
| `make comparar` | repite la comparación experimental y reescribe `results/comparacion_agentes.csv` |

Si `python3` no es el intérprete deseado: `make run PYTHON=.venv/bin/python`.

## Uso

Resolver una instancia con un agente (punto de entrada oficial):

```bash
python -m tileup solve instances/ejemplo.txt --agent aleatorio --seed 1 --time-limit 10
python -m tileup solve instances/gen_n6_k20_m120.txt --agent evolutivo --seed 1 --time-limit 10
```

| Argumento | Significado |
|---|---|
| `instancia` | ruta del archivo de instancia |
| `--agent` | agente a utilizar (`python -m tileup solve -h` lista los disponibles) |
| `--seed` | semilla; la misma semilla produce la misma solución |
| `--time-limit` | límite en segundos; el agente se detiene antes y entrega la mejor solución hallada |
| `--out` | archivo de solución (por defecto `solutions/<instancia>.<agente>.s<semilla>.txt`) |

Al terminar se informa por salida estándar `colocadas`, `ocupadas`, `mayor`, `resultado`, `tiempo` y la
medida de esfuerzo del agente. Códigos de salida: 0 éxito (también en derrota), 1 error de E/S,
2 instancia o argumentos inválidos, 3 el agente propuso una jugada ilegal.

Validar una solución con el validador independiente:

```bash
python -m validator instances/ejemplo.txt solutions/ejemplo.aleatorio.s1.txt [--paso-a-paso]
```

Imprime `VALIDA` o `INVALIDA` (con el motivo) y las métricas reproducidas. Código de salida 0 si es legal,
1 si se rechaza y 2 si no se pudieron leer los archivos. El validador está en `validator/` y **no importa
nada de `tileup/`**: reimplementa la lectura y las reglas por su cuenta.

Jugar una instancia manualmente en la consola:

```bash
python -m tileup play instances/ejemplo.txt --out solucion.txt
```

En cada turno se muestra el tablero (fichas como `color:valor`), la ficha actual y las siguientes cinco.
Se escribe `fila columna` (desde 0) para colocar la ficha; `q` abandona la partida.
Con `--out`, la solución se escribe al terminar, aun en derrota o abandono. `--no-color` desactiva los colores ANSI.

Generar una instancia aleatoria:

```bash
python tools/generate_instance.py N K M --seed S -o instances/mi_instancia.txt
```

## Agente de búsqueda: formulación (resumen)

Detalle y justificación en [docs/agente_busqueda.md](docs/agente_busqueda.md).

| Elemento | Definición |
|---|---|
| Estado | índice de la siguiente ficha y color de cada una de las N² celdas (los valores no afectan la legalidad ni la ocupación) |
| Operador de sucesión | colocar la ficha actual en una celda vacía y aplicar la fusión del motor |
| Costo de una acción | 5 − \|G\|, con \|G\| el tamaño de la componente fusionada; el costo del camino equivale a la ocupación final |
| Prueba de meta | se colocaron las M fichas; un tablero lleno con fichas pendientes es derrota |
| Algoritmo | beam search por capas con ancho creciente (anytime); `f = ocupación + β·U`; la heurística **no es admisible**, así que el óptimo solo se garantiza si no se descartó ningún estado o se alcanza la cota inferior |
| Esfuerzo | `nodos_expandidos` |

## Pruebas

```bash
python -m unittest discover -s tests -t . -v
```

| Archivo | Contenido |
|---|---|
| `tests/test_engine.py` | Unitarias del motor: colocación sin fusión, fusión de 2, de 3 y de 5, sin encadenamiento, derrota, victoria, jugadas ilegales, invariantes en partidas aleatorias |
| `tests/test_instance.py` | Lector de instancias: formato válido, comentarios, BOM y 18 variantes mal formadas |
| `tests/test_scenarios.py` | Escenarios completos sobre `instances/` y la CLI (`play`), incluido el ejemplo del enunciado |
| `tests/test_validator.py` | Validador: acepta soluciones legales (victoria, derrota, parciales) y rechaza 11 tipos de error; prueba diferencial motor contra validador en 300 partidas |
| `tests/test_search_agent.py` | Agente de búsqueda: evaluación incremental igual a la completa, óptimo igual al de un resolvedor exacto independiente, límite de tiempo, compleción rápida, determinismo |
| `tests/test_evolutivo_nucleo.py` | Núcleo del agente evolutivo: decodificadores A, B y C (legalidad con genomas aleatorios, preferencia por fusionar), reparación, aptitud y evaluador |
| `tests/test_agente_evolutivo.py` | Agente evolutivo: criterios de paro (cota, tope, estancamiento, reloj), validación de parámetros, determinismo con la semilla |
| `tests/test_integration.py` | Integración: cada agente registrado resuelve instancias pequeñas por la CLI, el validador acepta la solución con las mismas métricas y la semilla fija el resultado |

## Formatos

**Instancia**: las líneas en blanco y el texto desde `#` se ignoran. Luego vienen la línea `N K`, la línea `M`
y M líneas `color valor`. Un archivo mal formado produce un mensaje con el número de línea y código de salida 2.

**Solución**: una línea `indice fila columna` por colocación (todo desde 0) y al final
`# colocadas=X ocupadas=Y mayor=Z`.

## Estructura

```
tileup/
  engine.py      reglas del juego: estado, colocación, fusión, victoria/derrota
  instance.py    lectura y validación de instancias
  solution.py    escritura del archivo de solución
  cli.py         punto de entrada (python -m tileup solve | play)
  agents/
    base.py          contrato común: Agent, AgentResult, Deadline y registro
    beam_search.py   agente de búsqueda (beam search)
    evolutivo.py     agente evolutivo (algoritmo genético)
    random_agent.py  agente de referencia (línea base)
validator/       validador independiente (python -m validator)
tools/
  generate_instance.py   generador de instancias por N, K, M y semilla
  tune_search.py         ajuste por rejilla de los parámetros del agente de búsqueda
  tune_evolutivo.py      barrido, un parámetro por vez, de los parámetros del agente evolutivo
  compare_agents.py      comparación de agentes con varias semillas (results/comparacion_agentes.csv)
results/         resultados de experimentos (tuning_busqueda.csv, tuning_evolutivo_*.csv, comparacion_agentes.csv)
instances/       escenarios de prueba (ver docs/juego.md); instances/comparacion/ tiene las 12 de la comparación
results/soluciones/  soluciones de los tres agentes sobre instances/comparacion/ (semilla 1), validadas
Makefile         objetivos run, test, instancias, soluciones, validar, comparar
docs/juego.md    análisis del juego y propiedades útiles para los agentes
docs/agente_busqueda.md  formulación, heurística y ajuste del agente de búsqueda
docs/agente_evolutivo.md  diseño, parámetros y experimentos del agente evolutivo
docs/informe.md  informe breve: agentes, parámetros, ajuste y comparación experimental
tests/           pruebas unitarias, de escenario y de integración
```

## Agregar un agente

Se crea un módulo en `tileup/agents/` con una subclase de `Agent` decorada con `@register`. Su método
`solve(instance, seed, deadline)` devuelve un `AgentResult` con las colocaciones `(fila, columna)` y la
medida de esfuerzo. Luego se importa el módulo en `tileup/agents/__init__.py`. El programa vuelve a aplicar
las colocaciones sobre el motor, así que un agente no puede saltarse las reglas. Las pruebas de integración
cubren automáticamente a cualquier agente registrado.
