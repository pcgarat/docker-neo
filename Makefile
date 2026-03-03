# sd-webui-forge-neo — objetivos para build y ejecución
# Uso: make [objetivo]; make help

COMPOSE  = docker compose
SERVICE  = forge-neo
PORT     = 7860

# Versiones para install-docker (repo estable de Docker). Vacío = última del repo.
# Para fijar: DOCKER_CE_VERSION=5:29.2.1-1~ubuntu.24.04~noble (ejemplo Ubuntu 24.04).
DOCKER_CE_VERSION ?=
DOCKER_COMPOSE_PLUGIN_VERSION ?=

# Imagen para push a registro. Ej.: make push REGISTRY_IMAGE=ghcr.io/pcgarat/forge-neo:latest
REGISTRY_IMAGE ?= ghcr.io/$(GITHUB_USER)/forge-neo:latest
REGISTRY_IMAGE_CUDA12 ?= ghcr.io/$(GITHUB_USER)/forge-neo:cuda12
GITHUB_USER ?= pcgarat

.PHONY: help build build-no-cache build-cuda12 push push-cuda12 up down restart logs shell workspace ps clean klein9b iib-access install-docker

help:
	@echo "sd-webui-forge-neo — objetivos disponibles:"
	@echo ""
	@echo "  make build         — Construir la imagen (primera vez o tras cambios)"
	@echo "  make build-no-cache — Reconstruir sin caché (entrypoint, fixes config.json, etc.)"
	@echo "  make up            — Arrancar el contenedor en segundo plano"
	@echo "  make down          — Parar y eliminar el contenedor"
	@echo "  make restart       — down + up (recrea el contenedor y recoge cambios de .env)"
	@echo "  make klein9b       — Arrancar optimizado para Flux 2 Klein 9B (detecta VRAM y aplica --fp8/--bf16, --highvram/--normalvram/--lowvram)"
	@echo "  make logs          — Ver logs del servicio (Ctrl+C para salir)"
	@echo "  make shell         — Abrir una shell dentro del contenedor"
	@echo "  make workspace     — Crear /workspace/forge-data y /workspace/forge-extensions (antes del primer up)"
	@echo "  make iib-access   — Crear .env en la extensión IIB con acceso a carpetas de salida (/data/output, /data/Images)"
	@echo "  make ps            — Estado del servicio"
	@echo "  make clean         — down y eliminar imagen local"
	@echo "  make install-docker — Instalar Docker Engine y Docker Compose (plugin) desde repo oficial (Ubuntu/Debian, requiere sudo)"
	@echo "  make push           — Construir imagen, etiquetar y subir a registro (REGISTRY_IMAGE)"
	@echo "  make build-cuda12   — Construir variante CUDA 12.4 (para RunPod con driver < CUDA 13)"
	@echo "  make push-cuda12   — Construir variante CUDA 12, etiquetar y subir (REGISTRY_IMAGE_CUDA12)"
	@echo ""
	@echo "WebUI: http://localhost:$(PORT)   API: http://localhost:$(PORT)/docs"

# Cargar .env y exportar para que compose use DATA_PATH y EXTENSIONS_PATH en los volúmenes
ENV_LOAD = set -a && [ -f .env ] && . ./.env && set +a

build:
	$(COMPOSE) build

# Reconstruir sin caché (para que entren cambios en entrypoint, Dockerfile, etc.)
build-no-cache:
	$(COMPOSE) build --no-cache

# Variante CUDA 12.4: para RunPod (u otros hosts) donde el driver no soporta CUDA 13
build-cuda12:
	docker build -f Dockerfile.cuda12 -t forge-neo:cuda12 .

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

# Construye la imagen, la etiqueta con REGISTRY_IMAGE y la sube. Requiere docker login al registro.
push: build
	docker tag forge-neo:latest $(REGISTRY_IMAGE)
	docker push $(REGISTRY_IMAGE)

# Variante CUDA 12: construir, etiquetar y subir (para RunPod con driver que no soporta CUDA 13)
push-cuda12: build-cuda12
	docker tag forge-neo:cuda12 $(REGISTRY_IMAGE_CUDA12)
	docker push $(REGISTRY_IMAGE_CUDA12)

# Instala Docker Engine y Docker Compose (plugin) desde el repo oficial. Solo Ubuntu/Debian.
# Usa la última versión estable del repo; para fijar: make install-docker DOCKER_CE_VERSION=5:29.2.1-1~ubuntu.24.04~noble
install-docker:
	@. /etc/os-release 2>/dev/null && ([ "$$ID" = "ubuntu" ] || [ "$$ID" = "debian" ]) || (echo "Solo soportado Ubuntu/Debian. Ver https://docs.docker.com/engine/install/" && exit 1)
	@echo "Quitando paquetes que puedan conflictuar..."
	@sudo apt-get remove -y docker.io docker-doc docker-compose docker-compose-v2 podman-docker 2>/dev/null || true
	@sudo apt-get update
	@sudo apt-get install -y ca-certificates curl
	@sudo install -m 0755 -d /etc/apt/keyrings
	@id=$$(. /etc/os-release && echo "$$ID"); \
	suite=$$(. /etc/os-release && echo "$${UBUNTU_CODENAME:-$$VERSION_CODENAME}"); \
	if [ "$$id" = "ubuntu" ]; then \
	  gpg_url="https://download.docker.com/linux/ubuntu/gpg"; \
	  repo_url="https://download.docker.com/linux/ubuntu"; \
	elif [ "$$id" = "debian" ]; then \
	  gpg_url="https://download.docker.com/linux/debian/gpg"; \
	  repo_url="https://download.docker.com/linux/debian"; \
	else exit 1; fi; \
	sudo curl -fsSL "$$gpg_url" -o /etc/apt/keyrings/docker.asc; \
	sudo chmod a+r /etc/apt/keyrings/docker.asc; \
	printf 'Types: deb\nURIs: %s\nSuites: %s\nComponents: stable\nSigned-By: /etc/apt/keyrings/docker.asc\n' "$$repo_url" "$$suite" | sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null
	@sudo apt-get update
	@pkgs="docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin"; \
	if [ -n "$(DOCKER_CE_VERSION)" ]; then \
	  pkgs="docker-ce=$(DOCKER_CE_VERSION) docker-ce-cli=$(DOCKER_CE_VERSION) containerd.io docker-buildx-plugin docker-compose-plugin"; \
	elif [ -n "$(DOCKER_COMPOSE_PLUGIN_VERSION)" ]; then \
	  pkgs="docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin=$(DOCKER_COMPOSE_PLUGIN_VERSION)"; \
	fi; \
	sudo apt-get install -y $$pkgs
	@(sudo systemctl enable docker 2>/dev/null && sudo systemctl start docker 2>/dev/null) || \
	  (sudo service docker start 2>/dev/null) || true
	@if ! sudo docker info >/dev/null 2>&1; then \
	  echo "Docker no está en marcha (entorno sin systemd, p. ej. WSL). Arranca el daemon:"; \
	  echo "  sudo dockerd &"; \
	  echo "  o en WSL2: configura systemd o ejecuta dockerd en segundo plano."; \
	fi
	@echo "---"; sudo docker --version; sudo docker compose version
