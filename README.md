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
make up       # crea /workspace/forge-* si no existen y arranca
make logs     # ver logs; make down para parar
```

Sin Make:

```bash
docker compose build
mkdir -p /workspace/forge-data /workspace/forge-extensions
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

### Arranque optimizado para Flux 2 Klein 9B

```bash
make klein9b
```

Detecta la VRAM de la GPU con `nvidia-smi` y arranca con argumentos adecuados:
- **≥ 20 GB:** `--highvram --bf16-unet`
- **≥ 12 GB:** `--normalvram --bf16-unet`
- **< 12 GB:** `--lowvram --fp8_e4m3fn-unet`

Si no hay `nvidia-smi` en el host, se usa `--normalvram --bf16-unet`.

## Volúmenes y archivo .env

Las rutas de los volúmenes se leen del archivo **`.env`**. Si no existe o no defines una variable, se usan por defecto rutas bajo **`/workspace/`** (persistentes en RunPod, etc.).

Copia el ejemplo y ajusta si quieres:

```bash
cp .env.example .env
```

Variables que usa el compose:

| Variable en .env | Por defecto (si no está en .env) | Uso |
|------------------|----------------------------------|-----|
| `DATA_PATH`      | `/workspace/forge-data`          | Montaje → `/data` (modelos, output, config) |
| `EXTENSIONS_PATH`| `/workspace/forge-extensions`    | Montaje → `/data/extensions` |
| `MODELS_SUBDIR`  | `models`                        | Nombre de la subcarpeta de modelos dentro de `/data` (pon `Models` si tu carpeta tiene mayúscula). |
| `CHECKPOINT_SUBDIR` | `Stable-diffusion`           | Carpeta de checkpoints dentro de Models (pon `StableDiffusion` si tu carpeta no lleva guión). |
| `TEXT_ENCODER_SUBDIR` | `text_encoder`             | Carpeta de text encoders (CLIP, etc.) dentro de Models (pon `TextEncoders` si aplica). |

**Importante:** `make up` y `make restart` cargan y exportan el `.env` antes de ejecutar compose, así que se usan tus `DATA_PATH` y `EXTENSIONS_PATH`. Si ejecutas `docker compose up -d` a mano, hazlo desde el directorio del proyecto (donde está el `.env`) para que compose lo lea, o exporta antes las variables. Tras cambiar `.env`, usa `make restart` para recrear el contenedor con las nuevas rutas.

**Antes del primer arranque** crea en el host las carpetas que uses (por defecto o las que pongas en `.env`):

```bash
mkdir -p /workspace/forge-data /workspace/forge-extensions
# o, si usas .env con otras rutas: mkdir -p "$DATA_PATH" "$EXTENSIONS_PATH"
```

Estructura bajo `/data`: `models/`, `output/`, `config.json`, `ui-config.json`; `extensions/` es el volumen de EXTENSIONS_PATH.

**Mayúsculas y minúsculas:** Forge espera `models` y dentro `Stable-diffusion`. Si tus carpetas se llaman `Models` y `StableDiffusion`, en el `.env` define `MODELS_SUBDIR=Models` y `CHECKPOINT_SUBDIR=StableDiffusion`. Así la app usará tus carpetas y no creará otras en minúsculas. Si una carpeta aparece con candado (creada por el contenedor como root), en el host ejecuta: `sudo chown -R $(whoami) "ruta/a/esa/carpeta"`.

**Uso en máquina local** (otras rutas): define en `.env` por ejemplo `DATA_PATH=./forge-data` y `EXTENSIONS_PATH=./forge-extensions`, crea esos directorios y arranca con `make up`.

### Si solo persiste /workspace

- **Datos y extensiones:** ya quedan en `/workspace/forge-data` y `/workspace/forge-extensions`.
- **Código y dependencias Python:** van en la **imagen Docker**. El runtime suele conservar la imagen entre reinicios; si no, cada arranque usará la misma imagen (build o pull) y las deps siguen dentro de la imagen.
- **Si la imagen/caché también se pierde** (p. ej. pod efímero): hace falta un entrypoint que instale el venv y las deps en `/workspace` la primera vez y arranque con ese Python. Ver en el planteamiento la sección RunPod (§5.3 y checklist).

## Variables de entorno

- **`COMMANDLINE_ARGS`** — ya definido en el compose; puedes extenderlo (p. ej. `--gradio-auth user:pass`).
- **`EXTRA_ARGS`** — argumentos que el entrypoint añade al arranque (p. ej. `--cuda-malloc --normalvram --bf16-unet`). Útil en RunPod para ajustar VRAM sin cambiar el start command.
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
   - **Volume Disk:** persistente; se monta en **`/workspace`** por defecto.
   - **Expose HTTP Ports:** `7860` (WebUI y API).
   - **Variables de entorno:** si no defines `DATA_DIR`, el entrypoint usa **`/workspace`** (donde RunPod monta el volume disk). Opcional: `DATA_DIR=/workspace` para dejarlo explícito. Opcional: `EXTRA_ARGS="--cuda-malloc --normalvram --bf16-unet"` para memoria/backend.

3. **Arrancar y acceder:** Tras desplegar, la WebUI queda en:
   `https://[pod-id]-7860.proxy.runpod.net`

Los modelos y la configuración van en `/workspace` dentro del Pod (persisten al parar/reiniciar el Pod; se pierden si borras el Pod salvo que uses Network Volume en `/workspace`).

### Resumen RunPod

| Concepto | En RunPod |
|----------|-----------|
| Docker / Compose | No se instalan ni usan dentro del Pod. |
| Imagen | Esta imagen es la imagen del Pod. |
| Datos persistentes | Volume disk en `/workspace`; por defecto el entrypoint usa `/workspace` si no se define `DATA_DIR`. |
| Argumentos extra | `EXTRA_ARGS="--cuda-malloc --normalvram"` (o los que necesites) para que el Pod arranque con esos flags. |
| Puerto | Exponer **7860**; acceso vía proxy RunPod. |

**Si el Pod falla con `JSONDecodeError` en `verify_version`:** suele deberse a un `config.json` o `ui-config.json` vacío en `/workspace`. La imagen actual corrige esto en el entrypoint (escribe `{}` si el fichero existe pero está vacío). Reconstruye y vuelve a subir la imagen si usas una versión anterior.

**Si el Pod falla con `cuda>=13.0, please update your driver`:** el nodo de RunPod tiene un driver que no soporta CUDA 13. Usa la imagen **CUDA 12** (`make push-cuda12` y en RunPod selecciona la imagen con tag `:cuda12`).

## Planteamiento detallado

Ver [docs/planteamiento-docker-forge-neo_28-02-2025.md](docs/planteamiento-docker-forge-neo_28-02-2025.md).
