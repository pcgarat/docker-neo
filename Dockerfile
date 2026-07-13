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

WORKDIR /app
RUN git clone --depth 1 --branch neo https://github.com/Haoming02/sd-webui-forge-classic webui \
    && cd webui && rm -rf .git

WORKDIR /app/webui
# BUILD_SLIM=1: sin onnxruntime-gpu ni nunchaku (reduce mucho tamaño para RunPod)
ARG BUILD_SLIM=0
RUN if [ "$BUILD_SLIM" = "1" ]; then \
      export COMMANDLINE_ARGS="--exit --skip-torch-cuda-test --xformers --sage --flash --bnb"; \
    else \
      export COMMANDLINE_ARGS="--exit --skip-torch-cuda-test --xformers --sage --flash --nunchaku --bnb --onnxruntime-gpu"; \
    fi && python launch.py

RUN python -m pip install --no-cache-dir python-dotenv pillow-avif-plugin imageio_ffmpeg hnswlib

# Limpieza agresiva para reducir tamaño (RunPod tiene límite de disco para la imagen)
RUN find /usr/local/lib/python3.13 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.13 -name '*.pyc' -delete 2>/dev/null || true \
    && find /usr/local/lib/python3.13 -type d -name tests -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.13 -type d -name 'test' -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.13 -type d -name 'docs' -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.13 -type d -name 'doc' -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.13 -name '*.a' -delete 2>/dev/null || true \
    && find /usr/local/lib/python3.13 -name '*.so' -exec strip --strip-unneeded {} \; 2>/dev/null || true \
    && rm -rf /usr/local/lib/python3.13/site-packages/torch/share 2>/dev/null || true \
    && find /app/webui -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /app/webui -name '*.pyc' -delete 2>/dev/null || true

# -----------------------------------------------------------------------------
# Stage 2: runtime — solo librerías CUDA runtime + Python + artefactos
# -----------------------------------------------------------------------------
FROM nvidia/cuda:13.0.2-runtime-ubuntu24.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    ffmpeg \
    git \
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
