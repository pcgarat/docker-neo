# Docker para sd-webui-forge-neo

Imagen Docker y Compose para [sd-webui-forge-classic](https://github.com/Haoming02/sd-webui-forge-classic) (rama **neo**), con todas las dependencias opcionales (FFmpeg, xformers, SageAttention, Flash Attention, nunchaku, bitsandbytes, onnxruntime-gpu).

## Requisitos

- Docker con **NVIDIA Container Toolkit** (nvidia-docker2 o nvidia-container-toolkit).
- GPU NVIDIA con driver compatible con CUDA 13 (cu130).
- Recomendado: al menos 12–24 GB VRAM para modelos grandes (Flux, etc.).

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
- **`NVIDIA_VISIBLE_DEVICES`** — por defecto `all`; pon IDs de GPU si quieres limitar.

## Planteamiento detallado

Ver [docs/planteamiento-docker-forge-neo_28-02-2025.md](docs/planteamiento-docker-forge-neo_28-02-2025.md).
