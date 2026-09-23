# Extensiones horneadas en la imagen (extensions-builtin)

A diferencia de [`extensions/`](../extensions/) (semilla → volumen `/data/extensions`),
lo que vive aquí se copia a `/app/webui/extensions-builtin/` en el **Dockerfile**.

Forge carga ambos directorios. Usa esta carpeta solo cuando la extensión debe
sobrevivir a un volumen vacío (RunPod nuevo, `DATA_PATH` limpio) sin pasos manuales.

| Carpeta | Descripción |
|---------|-------------|
| `sd-forge-krea2-depth-controlnet` | Panel Depth/Pose ControlNet-LoRA para Krea 2 ([fabiencomte fork](https://github.com/fabiencomte/Krea-2-controlnet)) |

**No** metas aquí pesos de modelo (~862 MB): van en `DATA_PATH/Models/…`.
**No** dupliques la misma carpeta en `extensions/` ni en `EXTENSIONS_PATH` (Forge la cargaría dos veces).

Actualizar desde upstream: `make krea2-depth-ext` y luego `make build`.
