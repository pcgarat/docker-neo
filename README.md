# Docker para sd-webui-forge-neo

Imagen Docker y Compose para [sd-webui-forge-classic](https://github.com/Haoming02/sd-webui-forge-classic) (rama **neo**), con todas las dependencias opcionales (FFmpeg, xformers, SageAttention, Flash Attention, nunchaku, bitsandbytes, onnxruntime-gpu).

La imagen usa **build multi-stage**: se construye con la base CUDA `devel` y la imagen final solo incluye la base **runtime** (más ligera para descargar en RunPod o en cualquier registro).

## Requisitos del sistema

Para **levantar el contenedor** en el host:

| Requisito | Detalle |
|-----------|---------|
| **Docker** | Docker Engine (o Docker Desktop) instalado. En Ubuntu/Debian: `make install-docker` (instala Engine + Docker Compose plugin desde el repo oficial). |
| **NVIDIA Container Toolkit** | Para exponer la GPU al contenedor (`nvidia-docker2` o `nvidia-container-toolkit`). Tras instalarlo, reiniciar Docker y comprobar con `docker run --rm --gpus all nvidia/cuda:13.0.2-base-ubuntu24.04 nvidia-smi`. |
| **Driver NVIDIA** | Versión del driver que soporte **CUDA 13** (imagen final: `nvidia/cuda:13.0.2-runtime-ubuntu24.04`). Consulta [NVIDIA CUDA Compatibility](https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html). |
| **GPU NVIDIA** | Obligatoria para uso real; sin GPU solo CPU (muy lento). |
| **VRAM** | Recomendado **≥ 12 GB** para modelos medianos/grandes (Flux, Klein 9B). **≥ 20 GB** para highvram sin tantos ajustes. Con **&lt; 12 GB** se usa lowvram + fp8 (ver `make klein9b`). |
| **Disco** | Espacio para: imagen Docker (varios GB), volumen de datos (modelos, output, extensiones). |
| **Memoria RAM** | Depende del modelo; 16 GB de RAM de sistema es un mínimo razonable además de la VRAM. |

Resumen mínimo: **Docker + NVIDIA Container Toolkit + GPU NVIDIA con driver CUDA 13**.

### Instalación de Docker (solo en host propio, no en RunPod)

**En RunPod no hace falta:** RunPod no permite Docker ni Docker Compose dentro del Pod ([docs](https://docs.runpod.io/pods/overview)). El Pod ya es el contenedor; se usa esta imagen como imagen del Pod. Ver [Despliegue en RunPod](#despliegue-en-runpod) más abajo.

En un host **Ubuntu/Debian** (máquina local, VPS, etc.):

```bash
make install-docker
```

Instala Docker Engine, Docker Compose (plugin v2), containerd y Buildx desde el [repo oficial](https://docs.docker.com/engine/install/ubuntu/). Requiere `sudo`. Por defecto usa la **última versión estable** del repo. Para fijar versiones:

```bash
# Listar versiones disponibles y fijar Docker Engine (ej. Ubuntu 24.04 noble)
apt list -a docker-ce
make install-docker DOCKER_CE_VERSION=5:29.2.1-1~ubuntu.24.04~noble

# Fijar solo el plugin Docker Compose
make install-docker DOCKER_COMPOSE_PLUGIN_VERSION=2.24.0-1~ubuntu.24.04~noble
```

## Uso rápido

Con **Make** (recomendado):

```bash
make build    # primera vez o tras cambios (puede tardar bastante)
make up       # crea árbol de datos, siembra extensions/ si faltan, y arranca
make logs     # ver logs; make down para parar
```

En máquina limpia, `make up` copia las extensiones **custom** de [`extensions/`](extensions/) a `EXTENSIONS_PATH` **solo si esa carpeta aún no existe** (IIB, zoomimage, Krea2 UI). No toca builtins de la imagen ni sobrescribe installs ya presentes. Para forzar refresh de Krea2 Moodboard/Edit: `make krea2-ext`. Las extensiones Neo de uso diario (ADetailer, State Manager, CivitAI Browser, Agent Scheduler, Prompt All-in-One, Lama Cleaner, Krea2 Depth/Pose) van en la imagen (`builtin-extensions/`); el Depth/Pose se actualiza con `make krea2-depth-ext` + `make build`.


Sin Make:

```bash
docker compose build
mkdir -p /workspace/forge-data/{extensions,models,output}
# opcional: make seed-extensions
docker compose up -d
```

- **WebUI:** http://localhost:7860  
- **API:** http://localhost:7860/docs (FastAPI)  
- **Todos los objetivos:** `make help`

### Extensión Infinite Image Browsing (IIB) — acceso a carpetas de salida

Si IIB pide permisos para acceder a carpetas, crea su `.env` con acceso a las salidas:

```bash
make iib-access
```

Eso escribe en `<EXTENSIONS_PATH>/sd-webui-infinite-image-browsing/.env` las rutas permitidas: `txt2img`, `img2img`, `extra`, `save`, `/data/output`, `/data/Images`. Luego reinicia la WebUI o recarga la extensión.

### ReActor (face swap)

No uses el fork GitHub `sd-webui-reactor-sfw` con Forge Neo: su `install.py` pincha ORT 1.17.1 (roto en CUDA 13 / Python 3.13) y, además, esta imagen arranca con `--skip-install`. Usa la extensión activa en Codeberg: [sd-webui-reactor](https://codeberg.org/Gourieff/sd-webui-reactor).

La imagen hornea `insightface` + `albumentations` y **reafirma `onnxruntime-gpu`** (si no, `insightface` deja solo providers CPU/Azure y el swap falla). Tras instalar ReActor en una imagen antigua:

```bash
make reactor-fix
make restart
```

Modelo `inswapper_128.onnx` → `Models/insightface/`; buffalo_l se descarga solo a `Models/insightface/models/`.

### Krea 2 Moodboard + Identity Edit

La imagen incluye el **backend patch** de [forge-neo-krea2-toolkit](https://github.com/RedNodeAI/forge-neo-krea2-toolkit) (Forge Neo pin + patch regenerado; ver `patches/README.md`). Las extensiones UI van en el volumen: en máquina limpia las siembra `make up` desde [`extensions/`](extensions/). Para **actualizar** forzando clone desde GitHub:

```bash
make build            # imagen con el patch (obligatorio la primera vez / tras cambiar el patch)
make krea2-ext        # sobrescribe Moodboard + Identity Edit en EXTENSIONS_PATH
make krea2-depth-ext  # refresca el vendor Depth/Pose en builtin-extensions/; luego make build
make restart
```

El peso del Depth ControlNet-LoRA (~862 MB) **no** va en la imagen. Colócalo en:

```text
$DATA_PATH/Models/ControlNet/Krea2/depth-control-lora.safetensors
```

(mismo fichero que `krea2DepthControlnet_v10.safetensors` / [Patil/Krea-2-depth-controlnet](https://huggingface.co/Patil/Krea-2-depth-controlnet)).

Modelos (en `DATA_PATH`, no van en la imagen):

| Asset | Carpeta |
|-------|---------|
| Checkpoint Krea 2 | `models/Stable-diffusion/` |
| Text encoder visión `qwen3vl_4b_bf16` (o `fp8_scaled`) | `models/text_encoder/` — [Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2) |
| LoRA identity edit (solo Identity Edit, strength 1.0) | `models/Lora/` — [Civitai](https://civitai.com/models/2761113) |

En la WebUI: accordions **Krea2 Moodboard** / **Krea2 Identity Edit**; Settings → Krea2 Moodboard. Guía completa: [docs/integracion-krea2-moodboard-identity-edit-forge-neo_23-07-2026.md](docs/integracion-krea2-moodboard-identity-edit-forge-neo_23-07-2026.md).

**VRAM:** el TE visión + K2 es pesado; no asumas que el perfil `make lowvram` (8 GB) baste. Orientativo ≥12–16 GB.

### Arranque optimizado para Flux 2 Klein 9B

```bash
make klein9b
```

Detecta la VRAM de la GPU con `nvidia-smi` y arranca con argumentos adecuados:
- **≥ 20 GB:** `--highvram --bf16-unet`
- **≥ 12 GB:** `--normalvram --bf16-unet`
- **< 12 GB:** `--lowvram --fp8_e4m3fn-unet`

Si no hay `nvidia-smi` en el host, se usa el perfil 8 GB (`--lowvram`).

### Arranque para el chatBot (API, mismo modelo y tamaño)

```bash
make chatbot
```

Pensado para ReplayLastGeneration: N txt2img/img2img seguidos al **mismo** checkpoint y resolución.

- Perfil **8 GB** (`ARGS_8GB`): `--cuda-malloc --lowvram --fp8_e4m3fn-unet …`. **Sin** `--fast-fp8` (rompe Krea 2). **Sin** `--nowebui` (hace falta la UI para afinar estilo).
- Tras levantar, espera a la API y hace un POST de **1 step** al `Size` de `params.txt` con **Torch Compile Integrated → `guard_filter_fn`**. Ese preset recompila si cambias resolución; no usa `max-autotune` porque Forge lo bloquea con `--cuda-malloc`.
- No pisa el último gen: `save_images=false` y restaura `params.txt` (Forge lo escribe igual).
- `make chatbot-warmup` si Forge ya está arriba. `make test-warmup` para los tests del parser.

La primera imagen tras el warmup puede seguir siendo lenta (kernels Triton); las siguientes al mismo size reutilizan el grafo. Tras `make restart` hay que volver a calentar.

Requiere haber generado **al menos una imagen** en la WebUI (para tener `Size` en `params.txt`). Si no, el warmup se omite y el contenedor queda arriba.

**Nota:** `EXTRA_ARGS` del Makefile ahora sí entra en el contenedor (`environment` en compose pisa `env_file`). Antes, `make klein9b` / `make lowvram` no anulaban el `EXTRA_ARGS` del `.env`.

## Volúmenes y archivo .env

Local y RunPod usan el **mismo árbol**: `forge-data/` (modelos, output, config, extensions). En RunPod vive bajo `/workspace/forge-data` (volume disk/network). En Compose, ese árbol del host se monta en `/data` del contenedor.

Copia el ejemplo y ajusta si quieres:

```bash
cp .env.example .env
```

Variables que usa el compose:

| Variable en .env | Por defecto (si no está en .env) | Uso |
|------------------|----------------------------------|-----|
| `DATA_PATH`      | `/workspace/forge-data`          | Montaje → `/data` (modelos, output, config) |
| `EXTENSIONS_PATH`| `/workspace/forge-data/extensions` | Montaje → `/data/extensions` |
| `MODELS_SUBDIR`  | `models`                        | Nombre de la subcarpeta de modelos dentro de `/data` (pon `Models` si tu carpeta tiene mayúscula). |
| `CHECKPOINT_SUBDIR` | `Stable-diffusion`           | Carpeta de checkpoints dentro de Models (pon `StableDiffusion` si tu carpeta no lleva guión). |
| `TEXT_ENCODER_SUBDIR` | `text_encoder`             | Carpeta de text encoders (CLIP, etc.) dentro de Models (pon `TextEncoders` si aplica). |

**Importante:** `make up` y `make restart` cargan y exportan el `.env` antes de ejecutar compose, así que se usan tus `DATA_PATH` y `EXTENSIONS_PATH`. Si ejecutas `docker compose up -d` a mano, hazlo desde el directorio del proyecto (donde está el `.env`) para que compose lo lea, o exporta antes las variables. Tras cambiar `.env`, usa `make restart` para recrear el contenedor con las nuevas rutas.

**Antes del primer arranque** crea en el host las carpetas que uses (por defecto o las que pongas en `.env`):

```bash
mkdir -p /workspace/forge-data/{extensions,models,output}
# o, si usas .env con otras rutas: mkdir -p "$DATA_PATH/extensions" "$DATA_PATH/models" "$DATA_PATH/output"
```

Estructura bajo `/data` (y en el host bajo `DATA_PATH`): `models/`, `output/`, `extensions/`, `config.json`, `ui-config.json`.

**Mayúsculas y minúsculas:** Forge espera `models` y dentro `Stable-diffusion`. Si tus carpetas se llaman `Models` y `StableDiffusion`, en el `.env` define `MODELS_SUBDIR=Models` y `CHECKPOINT_SUBDIR=StableDiffusion`. Así la app usará tus carpetas y no creará otras en minúsculas. Si una carpeta aparece con candado (creada por el contenedor como root), en el host ejecuta: `sudo chown -R $(whoami) "ruta/a/esa/carpeta"`.

**Uso en máquina local** (rutas relativas): `DATA_PATH=./forge-data` y `EXTENSIONS_PATH=./forge-data/extensions` (o deja el default de `.env.example`).

**Migración:** si tenías `/workspace/forge-extensions` aparte, mueve el contenido a `/workspace/forge-data/extensions` o deja `EXTENSIONS_PATH` apuntando a la ruta antigua. Si un Pod viejo tenía datos en la raíz de `/workspace` (sin `forge-data`), pon `DATA_DIR=/workspace` en el Pod o muévelos a `/workspace/forge-data`.

### Persistencia en /workspace (RunPod)

- **Datos mutables:** `/workspace/forge-data` (models, output, extensions, config).
- **Código y dependencias Python:** van en la **imagen**. No hace falta venv en `/workspace` mientras uses `--skip-install` (como en esta imagen).

## Variables de entorno

- **`PUID` / `PGID`** — UID/GID efectivo de Forge (local: `id -u` / `id -g`). El entrypoint arranca como root, ajusta permisos de `/data` y `/app/webui`, y hace `setpriv` a ese usuario para que `output/` no quede `root:root` (rompe miniaturas en Nautilus). También fija `HOME` al home de ese UID, `TRITON_CACHE_DIR` / `TORCHINDUCTOR_CACHE_DIR` bajo `/data/cache/`, y `CC`/`CXX` si hay `gcc`/`g++` (Triton JIT con `--flash`/`--sage`). Opcional: `VIDEO_GID` / `RENDER_GID`.
- **`COMMANDLINE_ARGS`** — ya definido en el compose; puedes extenderlo (p. ej. `--gradio-auth user:pass`).
- **`EXTRA_ARGS`** — argumentos que el entrypoint añade al arranque (p. ej. `--cuda-malloc --normalvram --bf16-unet`). El compose los inyecta en el contenedor; `make klein9b` / `make lowvram` / `make chatbot` pisan el valor del `.env`. Útil también en RunPod para ajustar VRAM sin cambiar el start command.
- **`NVIDIA_VISIBLE_DEVICES`** — por defecto `all`; pon IDs de GPU si quieres limitar.

## Despliegue en RunPod

En RunPod **no se usa Docker ni Docker Compose dentro del Pod**: el Pod es el contenedor. Hay que usar la imagen de este proyecto como imagen del Pod ([Limitaciones RunPod](https://docs.runpod.io/pods/overview#limitations)).

### Pasos

1. **Construir y publicar la imagen** en un registro (Docker Hub, GHCR, etc.):
   ```bash
   make push
   ```
   Por defecto sube a **ghcr.io/pcgarat/forge-neo:latest**. Para otro registro: `make push REGISTRY_IMAGE=tu-usuario/forge-neo:latest` (Docker Hub) o `make push REGISTRY_IMAGE=ghcr.io/tu-usuario/forge-neo:latest`.

   **Si RunPod falla con `unsatisfied condition: cuda>=13.0`** (driver del host no soporta CUDA 13), usa la variante **CUDA 12.4**:
   ```bash
   make push-cuda12
   ```
   Luego en RunPod elige como imagen **ghcr.io/pcgarat/forge-neo:cuda12** (o la URL que hayas usado para `REGISTRY_IMAGE_CUDA12`).

   **Si la imagen excede el límite de tamaño de RunPod**, usa la variante **slim** (sin onnxruntime-gpu ni nunchaku; suficiente para la mayoría de usos):
   ```bash
   make push-slim
   ```
   En RunPod usa la imagen con tag **:slim** (ej. `ghcr.io/pcgarat/forge-neo:slim`).

   **Login:** antes del primer push inicia sesión en el registro:
   - **GitHub Container Registry:** `docker login ghcr.io -u TU_GITHUB_USER` (contraseña = Personal Access Token con `write:packages`).
   - **Docker Hub:** `docker login` (usuario y contraseña o token).
   Si construyes en **Mac (Apple Silicon)** usa `--platform linux/amd64` (RunPod solo soporta amd64):
   ```bash
   docker build --platform linux/amd64 -t tu-usuario/forge-neo:latest .
   ```

2. **Crear el Pod** en [RunPod Console](https://console.runpod.io/pod/create):
   - **Container Image:** la URL de tu imagen (ej. `tu-usuario/forge-neo:latest`).
   - **GPU:** la que necesites (≥ 12 GB VRAM recomendado para Flux/Klein).
   - **Volume Disk** (o Network Volume): persistente; RunPod lo monta en **`/workspace`**.
   - **Expose HTTP Ports:** `7860` (WebUI y API).
   - **Variables de entorno:** por defecto el entrypoint usa **`DATA_DIR=/workspace/forge-data`** (mismo layout que local). No hace falta definirla salvo migración. Opcional: `EXTRA_ARGS="--cuda-malloc --normalvram --bf16-unet"`.

3. **Arrancar y acceder:** Tras desplegar, la WebUI queda en:
   `https://[pod-id]-7860.proxy.runpod.net`

Modelos, extensiones y config van en `/workspace/forge-data` (persisten al stop/restart; se pierden al borrar el Pod salvo Network Volume).

### Resumen RunPod

| Concepto | En RunPod |
|----------|-----------|
| Docker / Compose | No se instalan ni usan dentro del Pod. |
| Imagen | Esta imagen es la imagen del Pod (misma que local). |
| Datos persistentes | `/workspace/forge-data` bajo el volume disk/network (`DATA_DIR` por defecto). |
| Argumentos extra | `EXTRA_ARGS="--cuda-malloc --normalvram"` (o los que necesites). |
| Puerto | Exponer **7860**; acceso vía proxy RunPod. |

**Si el Pod falla con `JSONDecodeError` en `verify_version`:** suele deberse a un `config.json` o `ui-config.json` vacío en el data dir. El entrypoint escribe `{}` si falta o está vacío. Reconstruye y vuelve a subir la imagen si usas una versión anterior.

**Si el Pod falla con `cuda>=13.0, please update your driver`:** el nodo de RunPod tiene un driver que no soporta CUDA 13. Usa la imagen **CUDA 12** (`make push-cuda12` y en RunPod selecciona la imagen con tag `:cuda12`).

**Si la imagen excede el límite de disco de RunPod:** usa la variante **slim** (`make build-slim` y `make push-slim`; en RunPod imagen con tag `:slim`). Omite onnxruntime-gpu y nunchaku y reduce bastante el tamaño.

## Planteamiento detallado

Ver [docs/planteamiento-docker-forge-neo_28-02-2025.md](docs/planteamiento-docker-forge-neo_28-02-2025.md).
