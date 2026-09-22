# sd-webui-forge-neo: imagen ligera con multi-stage (builder + runtime)
# Base build: CUDA devel. Imagen final: CUDA runtime (mucho más pequeña para pull en RunPod).

# -----------------------------------------------------------------------------
# Stage 1: builder — compila e instala todo (necesita devel por compilación)
# -----------------------------------------------------------------------------
FROM nvidia/cuda:13.0.2-devel-ubuntu24.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    git \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    python3.13 \
    python3.13-venv \
    python3.13-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.13 1
RUN python3.13 -m ensurepip --upgrade

# Pin de Forge Neo compatible con patches/krea2-features-backend.patch (ver patches/README.md).
ARG FORGE_NEO_REF=41359cd4b8b89212b3dbad8c9af719160a12ed63
WORKDIR /app
COPY patches/krea2-features-backend.patch patches/qwen35-vision-attention-fix.patch /tmp/
RUN git clone --filter=blob:none --no-checkout https://github.com/Haoming02/sd-webui-forge-classic webui \
    && cd webui \
    && git fetch --depth 1 origin "${FORGE_NEO_REF}" \
    && git checkout FETCH_HEAD \
    && git apply --verbose /tmp/krea2-features-backend.patch \
    && git apply --verbose /tmp/qwen35-vision-attention-fix.patch \
    && rm -f /tmp/krea2-features-backend.patch /tmp/qwen35-vision-attention-fix.patch \
    && rm -rf .git

WORKDIR /app/webui
# BUILD_SLIM=1: sin onnxruntime-gpu ni nunchaku (reduce mucho tamaño para RunPod)
ARG BUILD_SLIM=0
RUN if [ "$BUILD_SLIM" = "1" ]; then \
      export COMMANDLINE_ARGS="--exit --skip-torch-cuda-test --xformers --sage --flash --bnb"; \
    else \
      export COMMANDLINE_ARGS="--exit --skip-torch-cuda-test --xformers --sage --flash --nunchaku --bnb --onnxruntime-gpu"; \
    fi && python launch.py

RUN python -m pip install --no-cache-dir python-dotenv pillow-avif-plugin imageio_ffmpeg hnswlib

# sd-dynamic-prompts: con --skip-install su install.py no corre. Sin los extras
# [attentiongrabber,magicprompt], que arrastran transformers[torch] y pisarían el torch de la imagen.
RUN python -m pip install --no-cache-dir 'dynamicprompts~=0.31.0' 'send2trash~=1.8'

# Forge Classic renombró generation_parameters_copypaste → infotext_utils sin dejar alias.
# Mismo shim que mantiene A1111 upstream; lo necesitan extensiones pre-1.9 (sd-dynamic-prompts).
RUN printf 'from modules.infotext_utils import *  # noqa: F401\n' \
    > /app/webui/modules/generation_parameters_copypaste.py

# ReActor: insightface declara dependencia de onnxruntime (CPU) y pisa el pybind de
# onnxruntime-gpu → solo quedan Azure/CPU providers y el swap falla con CUDA.
# Con --skip-install, install.py de la extensión no corre (y además pincha ORT 1.17.1,
# incompatible con CUDA 13 / Py3.13). Horneamos deps aquí.
# insightface 0.7.3 es sdist sin wheel cp313; 1.0.1 sí tiene wheel y es API-compatible.
RUN python -m pip install --no-cache-dir --no-deps 'insightface==1.0.1' \
    && python -m pip install --no-cache-dir \
      'albumentations==1.4.3' \
      'opencv-python>=4.7.0.72' \
    && python -m pip uninstall -y onnxruntime \
    && if [ "$BUILD_SLIM" != "1" ]; then \
         python -m pip install --no-cache-dir --force-reinstall --no-deps 'onnxruntime-gpu==1.28.0'; \
       fi

# Limpieza agresiva para reducir tamaño (RunPod tiene límite de disco para la imagen)
# No strippear onnxruntime: rompe providers CUDA.
RUN find /usr/local/lib/python3.13 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.13 -name '*.pyc' -delete 2>/dev/null || true \
    && find /usr/local/lib/python3.13 -type d -name tests -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.13 -type d -name 'test' -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.13 -type d -name 'docs' -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.13 -type d -name 'doc' -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.13 -name '*.a' -delete 2>/dev/null || true \
    && find /usr/local/lib/python3.13 -name '*.so' ! -path '*/onnxruntime/*' -exec strip --strip-unneeded {} \; 2>/dev/null || true \
    && rm -rf /usr/local/lib/python3.13/site-packages/torch/share 2>/dev/null || true \
    && find /app/webui -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /app/webui -name '*.pyc' -delete 2>/dev/null || true

# -----------------------------------------------------------------------------
# Stage 2: runtime — solo librerías CUDA runtime + Python + artefactos
# -----------------------------------------------------------------------------
FROM nvidia/cuda:13.0.2-runtime-ubuntu24.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# gcc: Triton (flash/sage JIT) necesita un C compiler en runtime; sin él:
# RuntimeError: Failed to find C compiler. Please specify via CC ...
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    ffmpeg \
    git \
    gcc \
    g++ \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    python3.13 \
    python3.13-venv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.13 1

WORKDIR /app/webui

COPY --from=builder /usr/local/lib/python3.13 /usr/local/lib/python3.13
COPY --from=builder /app/webui /app/webui

ENV COMMANDLINE_ARGS="--listen --port 7860 --data-dir /data --gradio-allowed-path /app/webui --gradio-allowed-path /data --enable-insecure-extension-access --skip-prepare-environment --skip-install --api --sage"
EXPOSE 7860
VOLUME ["/data"]

COPY entrypoint.sh /entrypoint.sh
COPY ensure_config_then_launch.py /app/webui/ensure_config_then_launch.py
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "ensure_config_then_launch.py"]
