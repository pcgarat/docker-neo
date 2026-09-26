# forge-neo-docker

Imagen Docker y Compose para [sd-webui-forge-classic](https://github.com/Haoming02/sd-webui-forge-classic) (rama **neo**): WebUI + API en un solo contenedor, pensado para máquina local y RunPod.

Registro por defecto: **`ghcr.io/pcgarat/forge-neo`**.

## Qué incluye

- Forge Neo pinneado + patches (Krea 2 Moodboard / Identity Edit, fix Qwen3-VL)
- CUDA **13** / Python **3.13** (variantes CUDA 12 y slim para RunPod)
- Dependencias opcionales: FFmpeg, xformers, SageAttention, Flash Attention, nunchaku, bitsandbytes, onnxruntime-gpu
- Extensiones builtin (ADetailer, State Manager, CivitAI Browser, Agent Scheduler, Prompt All-in-One, Lama Cleaner, Krea2 Depth/Pose)
- Build multi-stage: build con `devel`, imagen final solo `runtime`
- Árbol de datos único (`forge-data/`) compatible local ↔ RunPod

## Requisitos

| Requisito | Detalle |
|-----------|---------|
| Docker + Compose v2 | En Ubuntu/Debian: `make install-docker` |
| NVIDIA Container Toolkit | GPU visible con `--gpus all` |
| Driver NVIDIA | Compatible con **CUDA 13** (o usa la variante `:cuda12`) |
| VRAM | ≥ 12 GB recomendado (Flux / Klein 9B / Krea 2); ≥ 20 GB highvram |
| Disco / RAM | Varios GB para imagen + modelos; ≥ 16 GB RAM de sistema |

Comprobar GPU:

```bash
docker run --rm --gpus all nvidia/cuda:13.0.2-base-ubuntu24.04 nvidia-smi
```

## Arranque rápido

```bash
cp .env.example .env          # ajusta PUID/PGID y rutas si hace falta
make build                    # primera vez (tarda)
make up                       # crea datos, siembra extensions/ si faltan, arranca
```

- **WebUI:** http://localhost:7860  
- **API:** http://localhost:7860/docs  
- **Ayuda:** `make help`

Sin Make:

```bash
docker compose build
mkdir -p /workspace/forge-data/{extensions,models,output}
docker compose up -d
```

## Perfiles de VRAM

| Comando | Uso |
|---------|-----|
| `make klein9b` | Detecta VRAM y elige high/normal/low + bf16/fp8 |
| `make lowvram` | Perfil 8 GB fijo |
| `make wan` | 8 GB + atención INT8 (vídeo / alta res) |
| `make chatbot` | 8 GB + warmup `torch.compile` para API repetida |

`EXTRA_ARGS` del `.env` se inyecta en el contenedor; `make klein9b` / `lowvram` / `chatbot` lo pisan.

## Datos y `.env`

Todo lo mutable vive bajo `DATA_PATH` → `/data` en el contenedor:

```text
forge-data/
├── models/          # Stable-diffusion, text_encoder, Lora, ControlNet…
├── output/
├── extensions/      # custom (IIB, zoomimage, Krea2 UI…)
├── config.json
└── ui-config.json
```

| Variable | Default | Rol |
|----------|---------|-----|
| `PUID` / `PGID` | `1000` | UID/GID del proceso Forge (evita `output/` como root) |
| `DATA_PATH` | `/workspace/forge-data` | Montaje → `/data` |
| `EXTENSIONS_PATH` | `…/extensions` | Extensiones custom |
| `MODELS_SUBDIR` | `models` | Pon `Models` si tu carpeta lleva mayúscula |
| `CHECKPOINT_SUBDIR` | `Stable-diffusion` | Pon `StableDiffusion` si aplica |
| `TEXT_ENCODER_SUBDIR` | `text_encoder` | Idem |
| `EXTRA_ARGS` | — | Flags extras de arranque |

Tras cambiar `.env`: `make restart`.

Local con rutas relativas: `DATA_PATH=./forge-data` y `EXTENSIONS_PATH=./forge-data/extensions`.

## Extensiones y extras

| Objetivo | Qué hace |
|----------|----------|
| `make seed-extensions` | Copia `extensions/` al volumen solo si faltan carpetas |
| `make iib-access` | `.env` de IIB con acceso a salidas |
| `make krea2-ext` | Fuerza update Moodboard + Identity Edit |
| `make krea2-depth-ext` | Refresca Depth/Pose en imagen → luego `make build` |
| `make reactor-fix` | Reafirma `onnxruntime-gpu` para ReActor |

**ReActor:** usa [sd-webui-reactor](https://codeberg.org/Gourieff/sd-webui-reactor) (Codeberg), no el fork `sfw` de GitHub (rompe CUDA 13 / Python 3.13 con `--skip-install`).

**Krea 2:** checkpoint + TE visión en el volumen; Depth ControlNet-LoRA (~862 MB) en  
`$DATA_PATH/Models/ControlNet/Krea2/depth-control-lora.safetensors`.  
Guía: [docs/integracion-krea2-moodboard-identity-edit-forge-neo_23-07-2026.md](docs/integracion-krea2-moodboard-identity-edit-forge-neo_23-07-2026.md).

## Publicar imagen y RunPod

```bash
docker login ghcr.io -u TU_GITHUB_USER   # PAT con write:packages
make push                                # → ghcr.io/pcgarat/forge-neo:latest
make push-cuda12                         # tag :cuda12 (drivers sin CUDA 13)
make push-slim                           # tag :slim (sin ort-gpu / nunchaku)
```

En RunPod **no** hay Docker dentro del Pod: esta imagen *es* el contenedor.

1. Container Image: `ghcr.io/pcgarat/forge-neo:latest` (o `:cuda12` / `:slim`)
2. Volume en `/workspace` → datos en `/workspace/forge-data`
3. Exponer HTTP **7860**
4. Opcional: `EXTRA_ARGS="--cuda-malloc --normalvram --bf16-unet"`

WebUI: `https://[pod-id]-7860.proxy.runpod.net`

| Problema | Solución |
|----------|----------|
| `cuda>=13.0` / driver viejo | Imagen `:cuda12` |
| Imagen demasiado grande | Imagen `:slim` |
| `JSONDecodeError` en config | Entrypoint rellena `{}`; reconstruye imagen antigua |

## Documentación

| Doc | Contenido |
|-----|-----------|
| [planteamiento](docs/planteamiento-docker-forge-neo_28-02-2025.md) | Diseño y arquitectura |
| [Krea 2 Moodboard / Identity Edit](docs/integracion-krea2-moodboard-identity-edit-forge-neo_23-07-2026.md) | Integración del toolkit |
| [Scripts txt2img](docs/guia-scripts-txt2img_23-09-2026.md) | Acordeones de scripts |
| [models.md](models.md) | Layout de modelos |
| [patches/](patches/) | Patches aplicados en build |

## Licencia y upstream

Forge Neo: [Haoming02/sd-webui-forge-classic](https://github.com/Haoming02/sd-webui-forge-classic) (rama neo).  
Este repo empaqueta y opera esa stack; respeta las licencias de Forge, extensiones y modelos que uses.
