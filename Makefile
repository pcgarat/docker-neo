# sd-webui-forge-neo — objetivos para build y ejecución
# Uso: make [objetivo]; make help

COMPOSE  = docker compose
SERVICE  = forge-neo
PORT     = 7860

.PHONY: help build up down restart logs shell workspace ps clean klein9b iib-access

help:
	@echo "sd-webui-forge-neo — objetivos disponibles:"
	@echo ""
	@echo "  make build      — Construir la imagen (primera vez o tras cambios)"
	@echo "  make up         — Arrancar el contenedor en segundo plano"
	@echo "  make down       — Parar y eliminar el contenedor"
	@echo "  make restart    — down + up (recrea el contenedor y recoge cambios de .env)"
	@echo "  make klein9b    — Arrancar optimizado para Flux 2 Klein 9B (detecta VRAM y aplica --fp8/--bf16, --highvram/--normalvram/--lowvram)"
	@echo "  make logs       — Ver logs del servicio (Ctrl+C para salir)"
	@echo "  make shell      — Abrir una shell dentro del contenedor"
	@echo "  make workspace  — Crear /workspace/forge-data y /workspace/forge-extensions (antes del primer up)"
	@echo "  make iib-access — Crear .env en la extensión IIB con acceso a carpetas de salida (/data/output, /data/Images)"
	@echo "  make ps         — Estado del servicio"
	@echo "  make clean      — down y eliminar imagen local"
	@echo ""
	@echo "WebUI: http://localhost:$(PORT)   API: http://localhost:$(PORT)/docs"

# Cargar .env y exportar para que compose use DATA_PATH y EXTENSIONS_PATH en los volúmenes
ENV_LOAD = set -a && [ -f .env ] && . ./.env && set +a

build:
	$(COMPOSE) build

up: workspace
	@$(ENV_LOAD) && $(COMPOSE) up -d

down:
	$(COMPOSE) down

restart: down
	@$(ENV_LOAD) && $(COMPOSE) up -d

# Flux 2 Klein 9B: según VRAM de la GPU se añaden --fp8_e4m3fn-unet/--bf16-unet y --lowvram/--normalvram/--highvram
klein9b: workspace
	@v=$$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1); \
	if [ -z "$$v" ]; then \
	  echo "No se detectó nvidia-smi; usando --cuda-malloc --normalvram --bf16-unet"; \
	  extra="--cuda-malloc --normalvram --bf16-unet"; \
	elif [ "$$v" -ge 20000 ]; then \
	  echo "VRAM $$v MB: usando --highvram --bf16-unet para Klein 9B"; \
	  extra="--cuda-malloc --highvram --bf16-unet"; \
	elif [ "$$v" -ge 12000 ]; then \
	  echo "VRAM $$v MB: usando --normalvram --bf16-unet para Klein 9B"; \
	  extra="--cuda-malloc --normalvram --bf16-unet"; \
	else \
	  echo "VRAM $$v MB: usando --lowvram --fp8_e4m3fn-unet para Klein 9B"; \
	  extra="--cuda-malloc --lowvram --fp8_e4m3fn-unet"; \
	fi; \
	$(ENV_LOAD) && export EXTRA_ARGS="$$extra" && $(COMPOSE) up -d

logs:
	$(COMPOSE) logs -f $(SERVICE)

shell:
	$(COMPOSE) exec $(SERVICE) /bin/bash

workspace:
	@mkdir -p /workspace/forge-data /workspace/forge-extensions
	@echo "Directorios /workspace/forge-data y /workspace/forge-extensions listos."

# Crea .env en la extensión Infinite Image Browsing con acceso a /data/output y /data/Images (carpetas de salida).
# Requiere EXTENSIONS_PATH en .env y que la extensión sd-webui-infinite-image-browsing esté instalada.
iib-access:
	@$(ENV_LOAD); \
	ext_dir="$${EXTENSIONS_PATH:-/workspace/forge-extensions}/sd-webui-infinite-image-browsing"; \
	if [ ! -d "$$ext_dir" ]; then \
	  echo "No existe $$ext_dir. Instala antes la extensión Infinite Image Browsing desde la pestaña Extensiones."; \
	  exit 1; \
	fi; \
	printf '%s\n%s\n' 'IIB_ACCESS_CONTROL=enable' 'IIB_ACCESS_CONTROL_ALLOWED_PATHS=txt2img,img2img,extra,save,/data/output,/data/Images' > "$$ext_dir/.env"; \
	echo "Creado $$ext_dir/.env con acceso a carpetas de salida. Reinicia la WebUI o recarga la extensión.";

ps:
	$(COMPOSE) ps

clean: down
	docker rmi forge-neo:latest 2>/dev/null || true
