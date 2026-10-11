# TileUp-Agents: un solo comando para resolver, probar y reproducir los experimentos.
# No hay dependencias que instalar: basta tener Python 3.10 o superior.

PYTHON  ?= $(shell command -v python3 2>/dev/null || command -v python)

# Parámetros de `make run` (se pueden cambiar: make run INSTANCIA=instances/ejemplo.txt AGENTE=busqueda)
INSTANCIA ?= instances/gen_n4_k9_m50.txt
AGENTE    ?= busqueda
SEMILLA   ?= 1
LIMITE    ?= 10

# Configuraciones (N K M) de la comparación experimental y semillas de sus instancias.
CONFIGS    := 4,12,80 4,14,80 5,18,125 5,21,125 6,26,180 6,30,180
SEMILLAS_I := 201 202
DIR_INST   := instances/comparacion
DIR_SOL    := results/soluciones

.PHONY: help run test validar instancias soluciones comparar

help:
	@echo "make run        resuelve INSTANCIA con AGENTE (SEMILLA, LIMITE) y valida la solución"
	@echo "make test       corre todas las pruebas"
	@echo "make validar    valida las soluciones guardadas en $(DIR_SOL)"
	@echo "make instancias regenera las instancias de la comparación en $(DIR_INST)"
	@echo "make soluciones regenera las soluciones de los tres agentes en $(DIR_SOL)"
	@echo "make comparar   repite la comparación experimental (results/comparacion_agentes.csv)"

run:
	@mkdir -p solutions
	@out=solutions/$(notdir $(basename $(INSTANCIA))).$(AGENTE).s$(SEMILLA).txt; \
	$(PYTHON) -m tileup solve $(INSTANCIA) --agent $(AGENTE) --seed $(SEMILLA) --time-limit $(LIMITE) --out $$out \
	&& $(PYTHON) -m validator $(INSTANCIA) $$out

test:
	$(PYTHON) -m unittest discover -s tests -t .

instancias:
	@mkdir -p $(DIR_INST)
	@for c in $(CONFIGS); do \
	  n=$${c%%,*}; r=$${c#*,}; k=$${r%%,*}; m=$${r#*,}; \
	  for s in $(SEMILLAS_I); do \
	    $(PYTHON) tools/generate_instance.py $$n $$k $$m --seed $$s -o $(DIR_INST)/gen_n$${n}_k$${k}_m$${m}_s$$s.txt; \
	  done; \
	done

soluciones: instancias
	@mkdir -p $(DIR_SOL)
	@for f in $(DIR_INST)/*.txt; do \
	  b=$$(basename $$f .txt); \
	  for a in busqueda evolutivo aleatorio; do \
	    $(PYTHON) -m tileup solve $$f --agent $$a --seed 1 --time-limit $(LIMITE) --out $(DIR_SOL)/$$b.$$a.s1.txt > /dev/null || exit 1; \
	  done; \
	done
	@$(MAKE) --no-print-directory validar

validar:
	@bad=0; for f in $(DIR_SOL)/*.txt; do \
	  b=$$(basename $$f .txt); inst=$(DIR_INST)/$${b%%.*}.txt; \
	  $(PYTHON) -m validator $$inst $$f > /dev/null || { echo "INVALIDA: $$f"; bad=1; }; \
	done; \
	if [ $$bad -eq 0 ]; then echo "todas las soluciones de $(DIR_SOL) son válidas"; else exit 1; fi

comparar:
	$(PYTHON) tools/compare_agents.py --workers 4
