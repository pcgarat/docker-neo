#!/bin/sh
set -e
# Misma raíz de datos en local (Compose → /data) y RunPod (volume en /workspace).
# Compose define DATA_DIR=/data; en RunPod el default es /workspace/forge-data.
data_dir="${DATA_DIR:-/workspace/forge-data}"
export COMMANDLINE_ARGS="$(echo "$COMMANDLINE_ARGS" | sed "s|/data|$data_dir|g")"

mkdir -p "$data_dir" "$data_dir/extensions" "$data_dir/models" "$data_dir/output" \
  "$data_dir/cache" "$data_dir/tmp"

# Evitar JSONDecodeError: Forge lee config.json y falla si existe pero está vacío
for f in config.json ui-config.json; do
  path="$data_dir/$f"
  if [ ! -f "$path" ] || [ ! -s "$path" ]; then
    printf '{}' > "$path"
  fi
done

if [ -n "$EXTRA_ARGS" ]; then
  export COMMANDLINE_ARGS="$COMMANDLINE_ARGS $EXTRA_ARGS"
fi

# Bajar a PUID:PGID para que output/cache en el host no queden root:root.
# El entrypoint debe arrancar como root (sin `user:` en compose); Forge escribe
# también bajo /app/webui (p. ej. backend/huggingface).
puid="${PUID:-1000}"
pgid="${PGID:-1000}"
video_gid="${VIDEO_GID:-44}"
render_gid="${RENDER_GID:-992}"

if [ "$(id -u)" -eq 0 ]; then
  # No hacer chown -R de todo DATA_PATH (incluye Models enormes).
  # Solo rutas que Forge escribe en runtime + leftovers root.
  for d in output cache tmp; do
    if [ -e "$data_dir/$d" ]; then
      chown -R "$puid:$pgid" "$data_dir/$d" 2>/dev/null || true
    fi
  done
  for f in config.json ui-config.json params.txt; do
    if [ -e "$data_dir/$f" ]; then
      chown "$puid:$pgid" "$data_dir/$f" 2>/dev/null || true
    fi
  done
  # Necesario: decompress de tokenizers/modelos embebidos bajo la imagen
  if [ -d /app/webui ]; then
    chown -R "$puid:$pgid" /app/webui
  fi
  groups="$pgid,$video_gid,$render_gid"
  exec setpriv --reuid="$puid" --regid="$pgid" --groups="$groups" -- "$@"
fi

exec "$@"
