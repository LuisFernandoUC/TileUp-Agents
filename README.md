# TileUp-Agents

Agentes de búsqueda y evolutivos para el juego TileUp (IC-6200 Inteligencia Artificial, Tarea Corta 1).

> Estado actual: motor del juego, lectura de instancias, escritura de soluciones, modo de juego manual y
> pruebas. Los agentes y el validador se agregarán en etapas siguientes.

## Requisitos

- Python 3.10 o superior. **No hay dependencias externas**: todo usa la biblioteca estándar.

## Uso

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
  cli.py         punto de entrada (python -m tileup)
tools/
  generate_instance.py   generador de instancias por N, K, M y semilla
instances/       escenarios de prueba (ver docs/juego.md)
docs/juego.md    análisis del juego y propiedades útiles para los agentes
tests/           pruebas unitarias y de escenario
```
