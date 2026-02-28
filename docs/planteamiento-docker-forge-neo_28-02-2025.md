# Última modificación: 2025-02-28 (Sage Attention en runtime)

# Planteamiento Docker para sd-webui-forge-classic (Forge Neo)

Documento de análisis y diseño para contenedorizar [sd-webui-forge-classic](https://github.com/Haoming02/sd-webui-forge-classic) (rama **neo**).

---

## 1. Resumen de la aplicación

- **Qué es:** WebUI de Stable Diffusion tipo Forge (fork de A1111), optimizada y actualizada (Flux, Wan 2.2, Qwen-Image, etc.).
- **Entrada:** `launch.py` → prepara entorno → arranca `webui.py` (Gradio + FastAPI).
- **Stack:** Python 3.13.x, PyTorch 2.10+cu130, Gradio 4.40, FastAPI. En este planteamiento se instalan **todas** las dependencias opcionales (FFmpeg, SageAttention, xformers, Flash Attention, nunchaku, bitsandbytes, onnxruntime-gpu).
- **Documentación oficial:** [README Neo](https://github.com/Haoming02/sd-webui-forge-classic) (branch `neo`).

---

## 2. Qué hay que estudiar / verificar antes de implementar

| Área | Qué revisar |
|------|--------------|
| **Arranque** | `launch.py` hace `prepare_environment()` (pip/uv, torch, deps) y luego `start()` → `webui.py`. En Docker conviene **no** instalar en cada arranque: imagen con deps ya instaladas y `--skip-prepare-environment` o equivalente. |
| **Rutas base** | `modules/paths_internal.py`: `data_path` = `--data-dir` (por defecto raíz del repo), `models_path` = `--model-ref` o `{data_path}/models`. Todo lo persistente debe colgar de un único `data_dir` montado como volumen. |
| **Puerto** | `modules/cmd_args.py`: `--port` (default 7860; en `webui.py` fallback 7861 si no se pasa). Un solo puerto HTTP. |
| **API** | `--api` habilita API junto a la UI; `--nowebui` solo API. Mismo puerto. |
| **GPU** | Requiere CUDA (cu130 recomendado). Sin GPU oficialmente solo CPU (muy lento). Hay que exponer GPU al contenedor (nvidia-docker / `runtime: nvidia`). |
| **Opcionales** | Instalar **todas**: `--xformers`, `--sage`, `--flash`, `--nunchaku`, `--bnb`, onnxruntime-gpu; FFmpeg en el sistema. Ver lista en §7. |
| **Listen** | `--listen` hace que Gradio escuche en `0.0.0.0` (necesario en Docker para acceso desde el host). |
| **Configuración** | `config.json` y `ui-config.json` en `data_path`; si no existen se crean. Persistir `data_path` incluye configuración y extensiones. |

---

## 3. Recursos a compartir con el contenedor

### 3.1 GPU (obligatorio para uso real)

- **NVIDIA GPU** con driver compatible con CUDA 13 (cu130).
- Uso de **NVIDIA Container Toolkit** (`nvidia-docker2` o `nvidia-container-toolkit`) y en el compose:
  - `deploy.resources.reservations.devices` (Docker Compose v2/v3) con `driver: nvidia` y `device_ids` (o `all`), **o**
  - `runtime: nvidia` (Docker clásico).
- Variable de entorno típica: `NVIDIA_VISIBLE_DEVICES` (opcional, para limitar GPUs visibles).

### 3.2 Red

- Un único puerto TCP (p. ej. **7860**) para la WebUI y la API.
- Si se usa proxy inverso (subpath), el proyecto soporta `--subpath`.

---

## 4. Puertos a exponer

| Puerto (host/contenedor) | Uso |
|---------------------------|-----|
| **7860** (recomendado) | WebUI Gradio + API FastAPI (mismo proceso). |

No hay puertos adicionales obligatorios. Documentación del repo indica default **7860**; en código hay fallback a 7861 si `cmd_opts.port` no está definido.

---

## 5. Volúmenes (persistencia)

La aplicación usa **dos conceptos** de rutas:

- **`script_path`**: directorio del código (repo). No debe ser persistido como volumen de datos (va en la imagen).
- **`data_path`** (`--data-dir`): base de datos de usuario. **Todo lo persistente debe vivir aquí** (o en rutas que se monten bajo este árbol).

Propuesta: **un único volumen** montado como `data_path` (p. ej. `/data` en el contenedor) y pasar `--data-dir /data` (y opcionalmente `--model-ref /data/models` si se quiere un subdirectorio explícito).

### 5.1 Estructura bajo `data_path` (recomendada como único volumen)

| Ruta relativa a `data_path` | Contenido |
|-----------------------------|-----------|
| `models/` | Modelos (ver siguiente tabla). |
| `models/Stable-diffusion` | Checkpoints (ckpt, safetensors). |
| `models/Lora` | LoRAs. |
| `models/VAE` | VAE. |
| `models/embeddings` | Textual Inversion / embeddings. |
| `models/text_encoder` | Modelos de text encoder (CLIP, etc.). |
| `models/ESRGAN` | Upscalers (ESRGAN, etc.). |
| `models/Codeformer` | CodeFormer (restauración de caras). |
| `models/GFPGAN` | GFPGAN (restauración de caras). |
| `output/` | **Salida por defecto** (txt2img, img2img, grids, extras, videos, “Save” button). |
| `output/txt2img-images` | Imágenes txt2img. |
| `output/img2img-images` | Imágenes img2img. |
| `output/extras-images` | Extras. |
| `output/videos` | Vídeos generados. |
| `output/txt2img-grids`, `output/img2img-grids` | Grids. |
| `output/images` | Guardado manual (“Save”). |
| `output/init-images` | Copias de imágenes init (img2img) si está activada la opción. |
| `tmp/` | Temporales (interrumpidos, etc.); se puede limpiar al inicio. |
| `extensions/` | Extensiones de usuario (se instalan/actualizan aquí). |
| `config.json` | Configuración UI. |
| `ui-config.json` | Configuración de la interfaz. |

Si se usa **un solo volumen** para “datos” (p. ej. `/data`):

- Montar ese volumen en `--data-dir` (ej. `--data-dir /data`).
- No hace falta montar por separado “modelos” e “imágenes”: ya están bajo `data_path` (`models_path` por defecto es `data_path/models`, `default_output_dir` es `data_path/output`).

### 5.2 Volumen único recomendado (Docker Compose)

- **Host → Contenedor:** un directorio del host (p. ej. `./forge-data`) → `/data`.
- **Comando/entrypoint:** asegurar `--data-dir /data` (y opcionalmente `--listen --port 7860`).

Con eso se persisten modelos, salidas, config y extensiones.

### 5.3 Dependencias de Python (venv/pip)

- **Entorno local / Docker Compose clásico:** las dependencias van **dentro de la imagen** (instaladas en el build). No hace falta volumen para ellas; se ejecuta con `--skip-prepare-environment` y `--skip-install`.
- **RunPod (y entornos con almacenamiento volátil del contenedor):** en un Pod el volumen del contenedor es **volátil** y se pierde al parar o reiniciar. Las dependencias (torch, gradio, etc.) son muy pesadas, por lo que:
  - **Deben instalarse en el volumen persistente** (p. ej. **`/workspace`**, que en RunPod es el disk volume o network volume por defecto).
  - El arranque debe **usar siempre** ese sitio: venv en `/workspace/venv` (o similar) y que el comando use explícitamente ese Python (`/workspace/venv/bin/python launch.py`).
  - Instalación **solo la primera vez**: si no existe el venv (o un marcador tipo `workspace/.deps-ready`), ejecutar `prepare_environment()` / pip install **en** `/workspace`; después arrancar con `--skip-prepare-environment` y `--skip-install` para no reinstalar en cada inicio.
  - Así las dependencias **no se pierden** al parar/reiniciar el Pod y **no se reinstalan** en cada arranque.
  - Referencia: [RunPod – Storage types](https://docs.runpod.io/pods/storage/types) (container volume = volátil; disk/network volume en `/workspace` = persistente).

Resumen:

| Entorno        | Dónde instalar deps      | Cómo asegurar que no se pierdan / no se reinstalan                          |
|----------------|--------------------------|-----------------------------------------------------------------------------|
| Imagen Docker  | Dentro de la imagen      | Build con `pip install`; run con `--skip-prepare-environment` / `--skip-install`. |
| RunPod         | Volumen persistente (ej. `/workspace`) | Venv en `/workspace/venv`; entrypoint usa ese Python; instalar solo si no existe. |

---

## 6. Variables de entorno útiles

- **`COMMANDLINE_ARGS`**: el repo ya lo usa (`paths_internal.py`). Ejemplo: `COMMANDLINE_ARGS="--listen --port 7860 --data-dir /data"`.
- **`TORCH_INDEX_URL`** / **`PYTORCH_VERSION`**: para forzar versión de PyTorch en instalaciones (más relevante en build que en run).
- **`GRADIO_ANALYTICS_ENABLED`**: ya se fuerza a `False` en el repo.
- Opcional: **`CUDA_VISIBLE_DEVICES`** para restringir GPUs dentro del contenedor.

---

## 7. Consideraciones adicionales

### 7.1 Dependencias opcionales a instalar (todas)

Instalar **todas** las siguientes para tener la imagen/venv completa:

| Tipo | Dependencia | Cómo instalarla | Uso |
|------|-------------|------------------|-----|
| Sistema | **FFmpeg** | `apt-get install ffmpeg` (o equivalente en la imagen base) | Exportar vídeo (Wan 2.2, etc.). |
| Python | **xformers** | Flag `--xformers` en `launch.py` / prepare_environment | Atención acelerada. |
| Python | **SageAttention** | Flag `--sage` (puede instalar triton) | Atención; prioridad si está disponible. |
| Python | **Flash Attention** | Flag `--flash` | Atención acelerada. |
| Python | **nunchaku** | Flag `--nunchaku` | Modelos SVDQ. |
| Python | **bitsandbytes** | Flag `--bnb` | Inferencia en baja precisión (nf4). |
| Python | **onnxruntime-gpu** | Flag `--onnxruntime-gpu` | Runtime ONNX con soporte GPU (cu130). |

En el build o en el entrypoint (RunPod) hay que ejecutar la instalación pasando estos flags (o invocar `prepare_environment()` con ellos) para que queden todas instaladas.

### 7.2 Otras consideraciones

- **Permisos:** el usuario del contenedor debe poder escribir en `data_path` (output, tmp, config, extensions).
- **Primera ejecución:** si `config.json` no existe, se crea; igual con directorios de salida. No es estrictamente necesario precrear estructura si el entrypoint arranca con `--data-dir` correcto.
- **Referencias externas (opcionales):** `--forge-ref-a1111-home`, `--forge-ref-comfy-home`, `--forge-ref-comfy-yaml` apuntan a instalaciones externas; en Docker normalmente no se usan y todo va en el volumen único.
- **Memoria:** modelos grandes (Flux, etc.) piden bastante VRAM; documentar requisitos mínimos (p. ej. 12–24 GB) en el README del proyecto Docker.

### 7.3 Sage Attention

- **Qué es:** backend de atención optimizado en Forge; si está instalado tiene prioridad sobre otros (xformers, flash). Requiere la dependencia instalada en build (`--sage` en `launch.py`, puede instalar Triton).
- **Uso:** además de instalar en build, hay que pasar `--sage` en **runtime** para activarlo; en este proyecto se incluye en `COMMANDLINE_ARGS` del servicio en docker-compose.
- **Problemas en algunas GPUs:** en arquitecturas recientes (p. ej. RTX 5090) se han reportado imágenes negras; se puede probar `--sage2-function fp16_triton` (añadirlo a `EXTRA_ARGS` en `.env` o en el target que corresponda).

---

## 8. Esquema resumido (Docker Compose)

- **Imagen:** Dockerfile que clona/COPY del repo (rama neo), instala Python 3.13, **todas** las dependencias: requirements.txt, torch+cu130, gradio 4.40, **y todas las opcionales** (xformers, sage, flash, nunchaku, bnb, onnxruntime-gpu) además de **FFmpeg** en el sistema; usuario no root con permisos sobre `/data`.
- **Servicio:** 
  - `runtime: nvidia` (o `deploy.resources.reservations.devices` con GPU).
  - Puerto: `7860:7860`.
  - Volumen: `./forge-data:/data`.
  - Comando/entrypoint: `python launch.py` con `COMMANDLINE_ARGS="--listen --port 7860 --data-dir /data --skip-prepare-environment"` (y `--skip-install` si todo está en la imagen).
- **Red:** solo el puerto 7860; si más adelante se añaden otros servicios (p. ej. proxy), compartir red como indicas.

---

## 9. Checklist de implementación sugerido

- [x] Crear Dockerfile (Python 3.13, CUDA base image adecuada).
- [x] Instalar en imagen **todas** las dependencias:
  - [x] requirements.txt, torch+cu130, gradio 4.40.
  - [x] FFmpeg (apt/system).
  - [x] Opcionales Python: xformers (`--xformers`), SageAttention (`--sage`), Flash Attention (`--flash`), nunchaku (`--nunchaku`), bitsandbytes (`--bnb`), onnxruntime-gpu (`--onnxruntime-gpu`).
- [x] Definir `--data-dir` por defecto (ej. `/data`) y usar `COMMANDLINE_ARGS` o CMD.
- [x] Añadir `--listen` y `--port 7860` para acceso desde el host.
- [x] Usar `--skip-prepare-environment` (y `--skip-install` si aplica) en arranque.
- [x] Docker Compose: servicio con GPU (nvidia), puerto 7860, volumen único (`forge-data` nombrado; opcional `./forge-data:/data`).
- [x] Documentar en README: requisitos GPU, primer arranque, estructura de datos (models, output, config).
- [ ] **Si el destino es RunPod:** entrypoint que instale/use venv en `/workspace` (o variable configurable), instale **todas** las opcionales (ffmpeg + flags anteriores) solo si no existen, y arranque siempre con ese Python para no perder ni reinstalar dependencias pesadas.

---

*Documento generado para el proyecto docker-neo. Repo de referencia: [Haoming02/sd-webui-forge-classic](https://github.com/Haoming02/sd-webui-forge-classic) (branch neo).*
