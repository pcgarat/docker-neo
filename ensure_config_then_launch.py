#!/usr/bin/env python3
"""
Ejecuta antes de launch.py: asegura config.json y ui-config.json en el data_dir
existen y tienen JSON válido (evita JSONDecodeError en verify_version).
Usa la misma lógica que paths_internal para obtener data_dir de COMMANDLINE_ARGS.
"""
import json
import os
import shlex
import sys

def main():
    raw = os.environ.get("COMMANDLINE_ARGS", "")
    argv = shlex.split(raw)
    data_dir = None
    for i, a in enumerate(argv):
        if a == "--data-dir" and i + 1 < len(argv):
            data_dir = argv[i + 1]
            break
    if not data_dir:
        # paths_internal: default --data-dir = dirname(modules_path) = webui dir
        data_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(data_dir, exist_ok=True)
    for name in ("config.json", "ui-config.json"):
        path = os.path.join(data_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                s = f.read()
            if not s.strip():
                raise ValueError("empty")
            json.loads(s)
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            with open(path, "w", encoding="utf-8") as f:
                f.write("{}")
    os.execv(sys.executable, [sys.executable, "launch.py"])

if __name__ == "__main__":
    main()
