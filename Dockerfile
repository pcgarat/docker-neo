# sd-webui-forge-neo: imagen con todas las deps (incl. opcionales)
# Base: CUDA 13 para PyTorch 2.10+cu130
FROM nvidia/cuda:13.0.2-devel-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Python 3.13 + sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    git \
    ffmpeg \
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

# ensurepip para pip
RUN python3.13 -m ensurepip --upgrade

WORKDIR /app

# Clonar repo neo (sin historial para reducir tamaño)
RUN git clone --depth 1 --branch neo https://github.com/Haoming02/sd-webui-forge-classic webui \
    && cd webui && rm -rf .git

WORKDIR /app/webui

# Instalar todas las dependencias (base + opcionales). --exit hace que salga tras prepare_environment.
# --skip-torch-cuda-test permite build sin GPU; en runtime sí se usará GPU.
ENV COMMANDLINE_ARGS="--exit --skip-torch-cuda-test --xformers --sage --flash --nunchaku --bnb --onnxruntime-gpu"
RUN python launch.py

# Dependencias usadas por extensiones (Infinite Image Browsing, AVIF, etc.)
RUN python -m pip install --no-cache-dir python-dotenv pillow-avif-plugin

# Arranque: sin reinstalar, con data-dir en volumen persistente.
# --gradio-allowed-path /app/webui (JS/CSS); /data (carpetas tipo Images, Models). --enable-insecure-extension-access habilita Extensiones
ENV COMMANDLINE_ARGS="--listen --port 7860 --data-dir /data --gradio-allowed-path /app/webui --gradio-allowed-path /data --enable-insecure-extension-access --skip-prepare-environment --skip-install --api"

# Ejecutamos como root para evitar problemas de permisos con el volumen /data montado
EXPOSE 7860

# /data debe montarse como volumen para modelos, output y config
VOLUME ["/data"]

CMD ["python", "launch.py"]
