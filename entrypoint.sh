#!/bin/sh
set -e
# Por defecto /workspace (RunPod); en Compose se define DATA_DIR=/data para usar el volumen montado en /data
data_dir="${DATA_DIR:-/workspace}"
export COMMANDLINE_ARGS="$(echo "$COMMANDLINE_ARGS" | sed "s|/data|$data_dir|g")"
# Evitar JSONDecodeError en launch: si config.json existe pero está vacío, Forge falla al leerlo
for f in config.json ui-config.json; do
  path="$data_dir/$f"
  if [ -f "$path" ] && [ ! -s "$path" ]; then
    printf '{}' > "$path"
  fi
done
if [ -n "$EXTRA_ARGS" ]; then
  export COMMANDLINE_ARGS="$COMMANDLINE_ARGS $EXTRA_ARGS"
fi
exec "$@"
