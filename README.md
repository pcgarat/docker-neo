# forge-neo-krea2

Forge Neo ([sd-webui-forge-classic](https://github.com/Haoming02/sd-webui-forge-classic), rama **neo**) preparado para **Krea 2** y flujos afines: toolkit preinstalado, módulos parchados y dependencias Python actualizadas a versiones recientes (CUDA 13 / Python 3.13).

El contenedor (Compose / RunPod) es solo el vehículo; lo relevante es la stack ya integrada.

Imagen: **`ghcr.io/pcgarat/forge-neo`**.

## Qué aporta frente a Forge Neo “vanilla”

| Pieza | Detalle |
|-------|---------|
| **Krea 2 Moodboard + Identity Edit** | Backend patch de [forge-neo-krea2-toolkit](https://github.com/RedNodeAI/forge-neo-krea2-toolkit) + extensiones UI (siembra en el volumen) |
| **Krea2 Depth / Pose** | ControlNet-LoRA vendorizado en la imagen (peso del modelo fuera, en el volumen) |
| **Patches de runtime** | p. ej. fix de atención Qwen3-VL; pin de Forge compatible con los patches |
| **Deps al día** | Paquetes Python subidos a versiones actuales (xformers, SageAttention, Flash Attention, nunchaku, bitsandbytes, onnxruntime-gpu, insightface…) en lugar de pins rotos de extensiones antiguas |
| **Extensiones diarias** | ADetailer, State Manager, CivitAI Browser, Agent Scheduler, Prompt All-in-One, Lama Cleaner, etc. |
| **Perfiles de arranque** | Klein 9B / lowvram / Wan / chatbot con warmup `torch.compile` |

## Requisitos

| Requisito | Detalle |
|-----------|---------|
| Docker + Compose v2 | En Ubuntu/Debian: `make install-docker` |
| NVIDIA Container Toolkit | GPU con `--gpus all` |
| Driver NVIDIA | CUDA **13** (o variante `:cuda12` en hosts antiguos) |
| VRAM | ≥ 12–16 GB para Krea 2 + TE visión; ≥ 20 GB highvram |
| Disco / RAM | Imagen + modelos; ≥ 16 GB RAM de sistema |

```bash
docker run --rm --gpus all nvidia/cuda:13.0.2-base-ubuntu24.04 nvidia-smi
```

## Arranque rápido

```bash
cp .env.example .env          # PUID/PGID y rutas
make build
make up
```

- **WebUI:** http://localhost:7860  
- **API:** http://localhost:7860/docs  
- **Ayuda:** `make help`

## Krea 2 — modelos en el volumen

Los pesos **no** van en la imagen. Colócalos bajo `DATA_PATH`:

| Asset | Carpeta |
|-------|---------|
| Checkpoint Krea 2 | `models/Stable-diffusion/` |
| Text encoder visión (`qwen3vl_4b_bf16` o `fp8_scaled`) | `models/text_encoder/` — [Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2) |
| LoRA identity edit (strength 1.0) | `models/Lora/` |
| Depth ControlNet-LoRA (~862 MB) | `Models/ControlNet/Krea2/depth-control-lora.safetensors` |

En la UI: accordions **Krea2 Moodboard** / **Krea2 Identity Edit**.  
Guía completa: [docs/integracion-krea2-moodboard-identity-edit-forge-neo_23-07-2026.md](docs/integracion-krea2-moodboard-identity-edit-forge-neo_23-07-2026.md).

Actualizar extensiones UI / Depth:

```bash
make krea2-ext          # Moodboard + Identity Edit → volumen
make krea2-depth-ext    # Depth/Pose en imagen → luego make build
make restart
```

## Perfiles de VRAM

| Comando | Uso |
|---------|-----|
| `make klein9b` | Detecta VRAM → high/normal/low + bf16/fp8 |
| `make lowvram` | Perfil 8 GB |
| `make wan` | 8 GB + atención INT8 (vídeo / alta res) |
| `make chatbot` | 8 GB + warmup compile para API repetida |

`EXTRA_ARGS` del `.env` entra en el contenedor; esos `make` lo pisan.

## Datos y `.env`

Árbol único `DATA_PATH` → `/data` (local y RunPod iguales):

```text
forge-data/
├── models/
├── output/
├── extensions/      # custom (IIB, zoomimage, Krea2 UI…)
├── config.json
└── ui-config.json
```

| Variable | Default | Rol |
|----------|---------|-----|
| `PUID` / `PGID` | `1000` | Usuario del proceso (output no root) |
| `DATA_PATH` | `/workspace/forge-data` | Montaje → `/data` |
| `EXTENSIONS_PATH` | `…/extensions` | Extensiones custom |
| `MODELS_SUBDIR` / `CHECKPOINT_SUBDIR` / `TEXT_ENCODER_SUBDIR` | `models` / `Stable-diffusion` / `text_encoder` | Ajusta si tus carpetas usan otra capitalización |
| `EXTRA_ARGS` | — | Flags de arranque |

Tras cambiar `.env`: `make restart`. Local: `DATA_PATH=./forge-data`.

## Otras extensiones

| Objetivo | Qué hace |
|----------|----------|
| `make seed-extensions` | Copia `extensions/` al volumen si faltan |
| `make iib-access` | Permisos IIB a carpetas de salida |
| `make reactor-fix` | Reafirma `onnxruntime-gpu` para ReActor |

**ReActor:** [sd-webui-reactor](https://codeberg.org/Gourieff/sd-webui-reactor) (Codeberg). Evita el fork `sfw` de GitHub: pincha ORT viejo y choca con CUDA 13 / Python 3.13 y `--skip-install`.

## Publicar y RunPod

```bash
docker login ghcr.io -u TU_GITHUB_USER
make push            # ghcr.io/pcgarat/forge-neo:latest
make push-cuda12     # :cuda12
make push-slim       # :slim (sin ort-gpu / nunchaku)
```

En RunPod la imagen *es* el Pod (sin Docker interno):

1. Image: `ghcr.io/pcgarat/forge-neo:latest` (o `:cuda12` / `:slim`)
2. Volume → `/workspace` (datos en `/workspace/forge-data`)
3. HTTP **7860**
4. Opcional: `EXTRA_ARGS="--cuda-malloc --normalvram --bf16-unet"`

| Problema | Solución |
|----------|----------|
| `cuda>=13.0` | Tag `:cuda12` |
| Imagen demasiado grande | Tag `:slim` |
| `JSONDecodeError` en config | Reconstruir imagen con entrypoint actual |

## Documentación

| Doc | Contenido |
|-----|-----------|
| [Krea 2 Moodboard / Identity Edit](docs/integracion-krea2-moodboard-identity-edit-forge-neo_23-07-2026.md) | Cómo está integrado el toolkit |
| [Planteamiento](docs/planteamiento-docker-forge-neo_28-02-2025.md) | Diseño de la imagen |
| [Scripts txt2img](docs/guia-scripts-txt2img_23-09-2026.md) | Acordeones de scripts |
| [models.md](models.md) | Layout de modelos |
| [patches/](patches/) | Patches aplicados en build |

## Upstream

Forge: [Haoming02/sd-webui-forge-classic](https://github.com/Haoming02/sd-webui-forge-classic) (neo).  
Toolkit Krea2: [RedNodeAI/forge-neo-krea2-toolkit](https://github.com/RedNodeAI/forge-neo-krea2-toolkit).  
Respeta las licencias de Forge, extensiones y modelos que uses.
