#!/bin/sh
# Repara deps de ReActor en un contenedor forge-neo ya en marcha.
# Causa típica: insightface instala onnxruntime (CPU) y pisa onnxruntime-gpu.
set -eu

echo "Instalando deps ReActor sin tirar de onnxruntime (CPU)…"
# --no-deps: insightface declara onnxruntime (CPU). El resto ya está en la imagen.
python -m pip install --no-cache-dir --no-deps 'insightface==1.0.1'
python -m pip install --no-cache-dir 'albumentations==1.4.3' 'opencv-python>=4.7.0.72'

echo "Eliminando onnxruntime CPU si existe…"
python -m pip uninstall -y onnxruntime 2>/dev/null || true

echo "Reinstalando solo el paquete onnxruntime-gpu (sin tocar numpy/protobuf)…"
python -m pip install --no-cache-dir --force-reinstall --no-deps 'onnxruntime-gpu==1.28.0'

python - <<'PY'
import onnxruntime as ort
from onnxruntime.capi import build_and_package_info as b
providers = ort.get_available_providers()
print(f"ORT {ort.__version__} package={b.package_name}")
print(f"providers={providers}")
if "CUDAExecutionProvider" not in providers:
    raise SystemExit("ERROR: CUDAExecutionProvider no disponible tras el fix")
print("OK: ReActor debería poder usar CUDA")
PY
