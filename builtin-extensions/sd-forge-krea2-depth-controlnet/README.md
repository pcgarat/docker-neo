# Krea 2 Depth / Pose ControlNet-LoRA (Forge)

Vendorado desde [fabiencomte/Krea-2-controlnet](https://github.com/fabiencomte/Krea-2-controlnet)
rama `forge-classic-2.28.1` @ `d0bd94f3b3887faabf0a64034494e4f457d89deb`.

Va en **extensions-builtin** de la imagen Docker (no en el volumen de extensiones),
para que un rebuild o un volumen vacío no la pierda.

## Modelo (no va en la imagen; ~862 MB)

Ruta esperada por la extensión:

```
<models_path>/ControlNet/Krea2/depth-control-lora.safetensors
```

En este setup: `$DATA_PATH/Models/ControlNet/Krea2/depth-control-lora.safetensors`
(mismo SHA que `krea2DepthControlnet_v10.safetensors` / Patil HF).

## Uso

1. Checkpoint Krea 2 Turbo (o Raw).
2. Acordeón **Krea 2 Depth / Pose ControlNet-LoRA** → Enable.
3. Añade foto; preprocessor `depth_anything_v2` (o None si ya es mapa depth).
4. Strength 1.0; Turbo 8 steps / CFG 0–1.

`easy-dwpose` (modo Pose) se hornea en el Dockerfile con `--no-deps`.
