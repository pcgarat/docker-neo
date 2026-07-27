# Parches Forge Neo (Krea2)

| Patch | Qué hace |
|-------|----------|
| `krea2-features-backend.patch` | Moodboard + Identity Edit (hooks K2 / Qwen3-VL). Regenerado para Neo `97ff3a4…`. |
| `krea2-features-backend.original.patch` | Original del toolkit (solo referencia; no aplicar en neo actual). |
| `qwen35-vision-attention-fix.patch` | Fix (2 partes): (1) `attention_function(...)` mal llamado en visión Qwen3-VL → `TypeError: attention_flash() missing k,v,heads`; (2) fallback a `attention_pytorch` cuando el encoder visual corre en CPU (lowvram offload) → `NotImplementedError: flash_attn::_flash_attn_forward ... 'CPU' backend`. |

---

# Parche `krea2-features-backend`

## Origen

- Toolkit fuente: [RedNodeAI/forge-neo-krea2-toolkit](https://github.com/RedNodeAI/forge-neo-krea2-toolkit) @ `8aac7a745202` (commit del que se extrajo el patch original).
- Ficheros que toca: `backend/diffusion_engine/krea.py`, `backend/nn/krea.py`, `backend/nn/llm/llama.py`, `backend/text_processing/qwen3vl_engine.py`.
- El patch original vendorizado se conserva como `krea2-features-backend.original.patch` (solo referencia histórica, **no aplicar** contra el `neo` actual).

## Por qué se regeneró

El patch original dejó de aplicar limpio (`git apply --check`) contra Forge Neo (`Haoming02/sd-webui-forge-classic`, rama `neo`) por deriva de contexto:

- El import `from backend.modules.k_prediction import PredictionDiscreteFlow` en `krea.py` fue eliminado en el commit `644450e` ("k_predictor"), que introdujo `ForgeDiffusionEngine._get_predictor()` en `backend/diffusion_engine/base.py` como punto único de selección de predictor para todos los motores (`flux.py`, `qwen.py`, `wan.py`, etc.), no solo Krea2.
- Ese import solo aparecía como contexto en el hunk original (no como línea añadida/eliminada por el propio patch), por lo que el conflicto era puramente de "contexto que ya no existe", no un choque real de lógica.
- Fuera de ese refactor, no se detectaron más cambios estructurales relevantes en los ~50 commits entre la base original del toolkit y el HEAD actual de `neo` para estos 4 ficheros.

## Cómo se regeneró

1. Se clonó `neo` con profundidad suficiente (150 commits) y se identificó el commit `44ae1a4fd0d76d829df9689224b6e59f0711e9cb` ("empty") como la última base donde el patch original aplicaba limpio.
2. Se aplicó el patch original sobre ese commit (`git apply --verbose`, éxito en los 4 ficheros) y se creó un commit temporal con el resultado.
3. Se hizo `git cherry-pick` de ese commit sobre el HEAD actual de `neo`. Esto permite que Git resuelva un merge de 3 vías real (base = `44ae1a4`, ours = HEAD, theirs = patch aplicado) en vez de un simple parcheo por coincidencia de texto/contexto. Los 4 ficheros se fusionaron **sin conflictos**.
4. Se revisó manualmente diff a diff el resultado frente al HEAD original para detectar incompatibilidades silenciosas con el resto del código (ver bug corregido más abajo).
5. Se generó el diff final: `git diff <SHA-original> <SHA-con-features> -- <4 ficheros> > krea2-features-backend.patch`.
6. Se verificó en un `git worktree` limpio e independiente del mismo SHA: `git apply --check --verbose` (éxito) + `git apply --verbose` (aplicado limpio) + `python3 -m py_compile` sobre los 4 ficheros resultantes.

## Bug corregido durante la fusión

El patch original usaba `dynamic_args.pop("ref_boosts", None)` y `dynamic_args.pop("ref_fit", None)` en `backend/diffusion_engine/krea.py`, asumiendo que `dynamic_args` era un `dict` plano. En el `neo` actual (`backend/args.py`), `dynamic_args` es una **clase con metaclase** (`_DynamicArgsMeta`) que emula `__getitem__` / `__setitem__` / `__contains__` / `.get()`, pero **no implementa `.pop()`**.

Esto habría lanzado `AttributeError: type object 'dynamic_args' has no attribute 'pop'` en **cualquier generación normal con Krea2** (esa rama de código se ejecuta siempre que no hay moodboard ni edit armados, es decir, en el caso por defecto — no solo en un edge case). Se reprodujo el fallo de forma aislada con la metaclase real antes de corregir.

Corrección aplicada (comportamiento equivalente, compatible con la metaclase):

```python
dynamic_args["ref_boosts"] = []
dynamic_args["ref_fit"] = []
```

## SHA pinned

- Forge Neo (`neo`) SHA verificado: `97ff3a4024be2f0d5316f16e868e5ef822768872`
- El patch aplica limpio contra ese SHA exacto. Si `neo` avanza, **re-verificar** con `git apply --check --verbose` antes de dar por bueno el build; no asumir compatibilidad indefinida.

## Ficheros que toca el patch regenerado

- `backend/diffusion_engine/krea.py`
- `backend/nn/krea.py`
- `backend/nn/llm/llama.py`
- `backend/text_processing/qwen3vl_engine.py`

## Parche `qwen35-vision-attention-fix`

En `backend/nn/llm/qwen35.py`, el port de ComfyUI hacía:

```python
optimized_attention = attention_function(x.device, mask=False, small_input=True)
```

En Forge Neo, `attention_function` ya es la implementación concreta (`attention_flash` / sage / …) con firma `(q, k, v, heads, …)`, no un factory. Esa llamada disparaba el `TypeError` al usar Moodboard/Identity Edit (ruta visión).

### Parte 1: asignación, no llamada

Fix alineado con `llama.py` / `qwen_vl.py`:

```python
optimized_attention = attention_function
```

### Parte 2: fallback CPU-safe (lowvram)

Con solo la Parte 1, el crash de `TypeError` desaparece, pero `attention_function` sigue siendo una **variable global fijada una vez al importar el módulo** según hardware (`attention_flash` si hay CUDA + flash-attn instalado). Si el encoder visual de Qwen3-VL se ejecuta en CPU (offload por `--lowvram` o por presión de VRAM durante Moodboard/Identity Edit), `attention_flash` llama a un kernel `flash_attn::_flash_attn_forward` que **solo tiene implementación registrada para CUDA** (y `Meta`, para tracing). El resultado es:

```
NotImplementedError: Could not run 'flash_attn::_flash_attn_forward' with arguments from the 'CPU' backend.
```

`attention_flash` en `backend/attention.py` ya captura esta excepción y reintenta con `operations.scaled_dot_product_attention` (fallback interno), pero eso implica: (a) un log de `ERROR` en cada forward de cada bloque visual (ruido, aparenta fallo real), y (b) el coste de lanzar y capturar la excepción de flash-attn en cada capa, en vez de decidir el kernel una sola vez por forward. Se corrige eligiendo el kernel según el device del tensor de entrada, replicando el patrón que ComfyUI usa para encoders visuales que pueden correr offloaded:

```python
from backend.attention import attention_function, attention_pytorch
...
optimized_attention = attention_function if x.device.type == "cuda" else attention_pytorch
```

`attention_pytorch` es CPU/CUDA-safe (usa `torch.nn.functional.scaled_dot_product_attention` sin forzar backend) y tiene la misma firma `(q, k, v, heads, skip_reshape=...)` que consume `Qwen35VisionAttention.forward`, por lo que es un *drop-in* sin tocar el resto de la ruta de visión.

Se descartaron las otras dos opciones evaluadas:

- **Forzar el encoder visual a CUDA en `llama.py` (`preprocess_embed`) y mover el resultado de vuelta**: rompe el propósito del offload por lowvram (el encoder visual es la parte más pesada en VRAM de la ruta Krea2/Moodboard) y es un cambio de gestión de memoria, no de selección de kernel de atención.
- **Parchear `attention_flash` para hacer fallback interno por device**: ya lo hace vía `try/except` genérico, pero de forma reactiva (excepción + log de error en cada capa) en vez de proactiva (decidir una vez por forward), y mezclaría lógica de selección de dispositivo dentro de una función pensada como kernel puro de atención.

Aplica sobre el mismo `FORGE_NEO_REF` que el patch Krea2.

---

## Riesgos funcionales no cubiertos por esta regeneración

La verificación ha sido **estática** (no hay `torch` en el entorno de trabajo para levantar el WebUI real):

- No se ha probado generación real (moodboard, identity edit, ni fallback normal) en runtime.
- El bug de `dynamic_args.pop()` es la única incompatibilidad estructural detectada por inspección manual, pero no descarta regresiones sutiles derivadas de los ~50 commits de diferencia entre la base del toolkit y el HEAD actual (LoRA, cuantización, refactor de attention/convrot, `img2img refactor`) que no tocan directamente estos 4 ficheros pero podrían interactuar en runtime (p.ej. `attention_function`, `UnetPatcher`, paths de cuantización).
- Recomendado: probar en un entorno con GPU/`torch` antes de considerar esto listo para producción.
