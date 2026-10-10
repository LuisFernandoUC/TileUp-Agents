# TileUp-Agents

Agentes de búsqueda y evolutivos para el juego TileUp (IC-6200 Inteligencia Artificial, Tarea Corta 1).

> Estado actual: motor, validador independiente, punto de entrada `solve` con un agente de referencia
> (`aleatorio`), modo de juego manual y pruebas. Los agentes de búsqueda y evolutivo están en desarrollo.

## Requisitos

- Python 3.10 o superior. **No hay dependencias externas**: todo usa la biblioteca estándar.

## Uso

Resolver una instancia con un agente (punto de entrada oficial):

```bash
python -m tileup solve instances/ejemplo.txt --agent aleatorio --seed 1 --time-limit 10
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
Se escribe `fila columna` (desde 0) para colocar la ficha
Con `--out`, la solución se escribe al terminar, aun en derrota o abandono. `--no-color` desactiva los colores ANSI.

Generar una instancia aleatoria:

```bash
python tools/generate_instance.py N K M --seed S -o instances/mi_instancia.txt
```

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
    random_agent.py  agente de referencia (línea base)
validator/       validador independiente (python -m validator)
tools/
  generate_instance.py   generador de instancias por N, K, M y semilla
instances/       escenarios de prueba (ver docs/juego.md)
docs/juego.md    análisis del juego y propiedades útiles para los agentes
tests/           pruebas unitarias, de escenario y de integración
```

## Agregar un agente

Se crea un módulo en `tileup/agents/` con una subclase de `Agent` decorada con `@register`. Su método
`solve(instance, seed, deadline)` devuelve un `AgentResult` con las colocaciones `(fila, columna)` y la
medida de esfuerzo. Luego se importa el módulo en `tileup/agents/__init__.py`. El programa vuelve a aplicar
las colocaciones sobre el motor, así que un agente no puede saltarse las reglas. Las pruebas de integración
cubren automáticamente a cualquier agente registrado.
