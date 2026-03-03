#!/bin/sh
set -e
if [ -n "$DATA_DIR" ]; then
  export COMMANDLINE_ARGS="$(echo "$COMMANDLINE_ARGS" | sed "s|/data|$DATA_DIR|g")"
  # Evitar JSONDecodeError en launch: si config.json existe pero está vacío, Forge falla al leerlo
  for f in config.json ui-config.json; do
    path="$DATA_DIR/$f"
    if [ -f "$path" ] && [ ! -s "$path" ]; then
      printf '{}' > "$path"
    fi
  done
fi
if [ -n "$EXTRA_ARGS" ]; then
  export COMMANDLINE_ARGS="$COMMANDLINE_ARGS $EXTRA_ARGS"
fi
exec "$@"
