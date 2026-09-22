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

  # setpriv no cambia HOME: el proceso hereda HOME=/root y Triton/HF fallan con
  # PermissionError al crear /root/.triton (uid PUID no puede escribir ahí).
  home_dir="$(getent passwd "$puid" 2>/dev/null | cut -d: -f6)"
  if [ -z "$home_dir" ] || [ ! -d "$home_dir" ]; then
    home_dir="$data_dir/home"
    mkdir -p "$home_dir"
    chown "$puid:$pgid" "$home_dir"
  fi
  export HOME="$home_dir"
  mkdir -p "$data_dir/cache/triton" "$data_dir/cache/torchinductor"
  chown -R "$puid:$pgid" "$data_dir/cache/triton" "$data_dir/cache/torchinductor" 2>/dev/null || true
  export TRITON_CACHE_DIR="$data_dir/cache/triton"
  export TORCHINDUCTOR_CACHE_DIR="$data_dir/cache/torchinductor"
  # Triton JIT: si no hay CC explícito busca gcc/cc en PATH.
  if [ -z "${CC:-}" ] && command -v gcc >/dev/null 2>&1; then
    export CC="$(command -v gcc)"
  fi
  if [ -z "${CXX:-}" ] && command -v g++ >/dev/null 2>&1; then
    export CXX="$(command -v g++)"
  fi

  groups="$pgid,$video_gid,$render_gid"
  exec setpriv --reuid="$puid" --regid="$pgid" --groups="$groups" -- "$@"
fi

exec "$@"
