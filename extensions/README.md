# Extensiones custom (semilla)

Código de extensiones **no built-in** que `make up` / `make workspace` copian a `EXTENSIONS_PATH` **solo si falta** esa carpeta en el destino.

## Incluidas

| Carpeta | Descripción |
|---------|-------------|
| `sd-webui-infinite-image-browsing` | Infinite Image Browsing |
| `stable-diffusion-webui-zoomimage` | Zoom de imagen |
| `sd-forge-krea2-moodboard` | Krea2 Moodboard (UI) |
| `sd-forge-krea2-edit` | Krea2 Identity Edit (UI; fix `dynamic_args` aplicado) |

El patch de backend Krea2 va en la **imagen** (`patches/`), no aquí.

## ReActor (no va en la semilla)

Instálalo en `EXTENSIONS_PATH` desde [codeberg.org/Gourieff/sd-webui-reactor](https://codeberg.org/Gourieff/sd-webui-reactor) (no el fork `-sfw` de GitHub). Las deps Python van en la **imagen** (`make build` / `make reactor-fix`); ver README § ReActor.

## Reglas

- Añade aquí solo extensiones custom (una carpeta por extensión).
- No metas builtins de Forge.
- No versionar runtime: `.git/`, `iib.db`, `iib_db_backup/`, `*.log`, `__pycache__/`, `.env` locales.
- Si la extensión ya existe en `EXTENSIONS_PATH`, el seed **no la sobrescribe** (conserva DB, `.env`, etc.).
- Para forzar actualización de Krea2 desde GitHub: `make krea2-ext`.
