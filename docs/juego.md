# Análisis del juego TileUp

Este documento resume las reglas tal como las implementa el motor ([`tileup/engine.py`](../tileup/engine.py))
y las propiedades estructurales del problema que servirán para diseñar los agentes.

## 1. Reglas

| Elemento | Definición |
|---|---|
| Tablero | Cuadrícula N × N; cada celda está vacía o tiene una ficha ⟨c, v⟩ con c ∈ 1..K, v ≥ 1. Empieza vacío. |
| Secuencia | M fichas fijas, conocidas de antemano, consumidas en orden. |
| Acción | Colocar la primera ficha pendiente en **cualquier** celda vacía. Factor de ramificación = celdas vacías. |
| Fusión | G = componente conexa ortogonal del mismo color que contiene la celda p recién ocupada. Si \|G\| ≥ 2, se retiran las fichas de G y en p queda una ficha con la suma de valores. No encadena. |
| Victoria | Se colocaron las M fichas, aunque el tablero quede lleno con la última. |
| Derrota | Queda al menos una ficha pendiente y no hay celdas vacías. |
| Orden del concurso | (1) más fichas colocadas, (2) menos celdas ocupadas, (3) menos tiempo. |

Ejemplo del enunciado (4×4, K=3), reproducido por la prueba `test_statement_example_reproduces_expected_solution`:

```
ficha 2 (1:3) en (0,1)  -> se fusiona con 1:2 en (0,0)          -> (0,1)=1:5
ficha 4 (1:1) en (0,2)  -> se fusiona con 1:5 en (0,1)          -> (0,2)=1:6
ficha 5 (2:4) en (1,2)  -> se fusiona con 2:1 en (1,1)          -> (1,2)=2:5
final: colocadas=6 ocupadas=3 mayor=6
```

## 2. Propiedades útiles

**P1. Nunca hay dos fichas del mismo color adyacentes.** Vale en el tablero vacío, y cada colocación
absorbe la componente maximal completa. Consecuencia: G es siempre p más sus vecinos del mismo color, así que
\|G\| ≤ 5 y la fusión cuesta O(1). El motor implementa de todos modos el recorrido general (DFS) para
apegarse literalmente a la regla; la prueba `RandomPlayInvariantsTest` verifica P1 en 200 partidas aleatorias.

**P2. Los valores no influyen en la dinámica.** La legalidad, la fusión y la ocupación dependen solo de los
colores. El valor solo determina la "ficha mayor", que no entra en el orden del concurso. Un agente puede
identificar estados por `(siguiente_ficha, colores)` e ignorar los valores, lo que reduce el espacio de estados.

**P3. Cada colocación cambia la ocupación en 2 − |G|**, es decir, +1 (sin fusión), 0, −1, −2 o −3.
Colocar junto a una ficha del mismo color nunca aumenta la ocupación.

**P4. La suma de valores es constante** (igual a la suma de las fichas colocadas). También lo verifican las pruebas.

**P5. Cota inferior.** Un color que ya apareció nunca desaparece del tablero, porque la fusión deja una ficha de
ese color. Por lo tanto, en cualquier estado:

> ocupación final ≥ (colores distintos presentes en el tablero) + (colores de las fichas pendientes que aún no están en el tablero)

Esta cota es candidata a heurística **admisible** para un agente informado (nunca sobreestima la ocupación final).

**P6. Régimen fácil: si D ≤ ⌊N²/2⌋, el óptimo es exactamente D**, donde D es la cantidad de colores distintos en
la secuencia. Se parte el tablero en ⌊N²/2⌋ dominós (pares de celdas vecinas) y se asigna uno a cada color.
Cada ficha va a la celda libre del dominó de su color: si el color ya está presente, se fusiona y la ficha
"salta" de una mitad a la otra; si no, ocupa una mitad. La ocupación nunca supera D, nunca hay derrota y se
alcanza la cota P5. Se verificó empíricamente sobre 3000 instancias aleatorias.
Consecuencia: **las instancias interesantes son las que tienen K > N²/2.** Allí no existe esta garantía y el
resultado depende de la planificación. En el concurso, con N y K anunciados, esto dice de antemano en qué régimen se compite.

**P7. Simetrías.** Las 8 simetrías del cuadrado (rotaciones y reflexiones) transforman soluciones en soluciones
equivalentes. Un agente de búsqueda puede usarlas para podar estados.

## 3. Tamaño del espacio de búsqueda

El árbol completo tiene a lo sumo ∏ eᵢ ≤ (N²)^M hojas, donde eᵢ es la cantidad de celdas vacías en el paso i.
Ejemplo: 6×6 con M = 120 da hasta 36¹²⁰ caminos, así que la búsqueda exhaustiva es inviable salvo en
tableros diminutos. El número de **estados distintos** está acotado por (K+1)^(N²) por cada valor de
`siguiente_ficha`, mucho menor que el número de caminos. Detectar estados repetidos (P2, P7) es por lo tanto valioso.

## 4. Escenarios de prueba (`instances/`)

| Archivo | N | K | M | Qué ejercita |
|---|---|---|---|---|
| `ejemplo.txt` (+ `ejemplo_solucion.txt`) | 4 | 3 | 6 | Ejemplo del enunciado; la solución debe coincidir byte a byte |
| `un_color.txt` | 2 | 1 | 8 | Un color: victoria con 1 celda ocupada |
| `derrota_inevitable.txt` | 2 | 4 | 5 | Derrota en cualquiera de los 24 órdenes posibles |
| `tablero_1x1.txt` | 1 | 1 | 3 | Caso límite: derrota tras la primera ficha |
| `fusion_cruz.txt` | 3 | 2 | 6 | Fusión de 5 fichas (el máximo posible, por P1) |
| `colores_alternos.txt` | 3 | 2 | 14 | Un buen plan gana con 2 celdas; colocar en orden de lectura pierde |
| `gen_n4_k3_m30.txt` | 4 | 3 | 30 | Generada, régimen fácil (P6) |
| `gen_n6_k4_m80.txt` | 6 | 4 | 80 | Generada, régimen fácil, más grande |
| `gen_n3_k5_m25.txt` | 3 | 5 | 25 | Generada, régimen difícil (K > N²/2) |
| `gen_n4_k9_m50.txt` | 4 | 9 | 50 | Generada, régimen difícil |
| `gen_n5_k14_m80.txt` | 5 | 14 | 80 | Generada, régimen difícil |
| `gen_n6_k20_m120.txt` | 6 | 20 | 120 | Generada, régimen difícil, la más grande |

Mejor resultado de 200 partidas con jugadas al azar (referencia de dificultad, semilla 0):
`gen_n3_k5` 23/25, `gen_n4_k9` 31/50, `gen_n5_k14` 33/80, `gen_n6_k20` 45/120. En las de régimen fácil, el azar ya gana.
