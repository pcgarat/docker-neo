# Última modificación: 2026-07-24

# Checklist — Integración Krea2 Moodboard + Identity Edit (Forge Neo)

Fecha creación: 23-07-2026

Fuente: [docs/integracion-krea2-moodboard-identity-edit-forge-neo_23-07-2026.md](../integracion-krea2-moodboard-identity-edit-forge-neo_23-07-2026.md) · [RedNodeAI/forge-neo-krea2-toolkit](https://github.com/RedNodeAI/forge-neo-krea2-toolkit)

## Implementación en repo

- [x] Vendorizar `patches/krea2-features-backend.patch` (+ original + `patches/README.md`)
- [x] Regenerar patch contra Forge Neo `97ff3a4024be2f0d5316f16e868e5ef822768872` (el original no aplicaba en HEAD)
- [x] Corregir `dynamic_args.pop()` → asignación en backend patch (metaclase Neo)
- [x] Fix `dynamic_args.pop()` en extensión `krea2_edit.py` (hot + `make krea2-ext`)
- [x] Fix `qwen35.py` attention_function (`patches/qwen35-vision-attention-fix.patch`)
- [x] Fix `qwen35.py` fallback CPU-safe (`attention_pytorch`) cuando el encoder visual corre offloaded (lowvram) → mismo patch, 2ª parte. Aplicado en caliente en `forge-neo` + patch actualizado.
- [x] Aplicar ambos patches en `Dockerfile` / `Dockerfile.cuda12`
- [x] Pin `FORGE_NEO_REF` en ambos Dockerfiles
- [x] Target `make krea2-ext` (+ help + SHA completo + fix pop)
- [x] Actualizar README raíz
- [x] Actualizar doc de integración (§8)

## Pendiente en entorno con GPU / datos

- [ ] `make build` (o `make build-cuda12`) — persistir ambos fixes de qwen35 (assignment + fallback CPU) en imagen (hotfix actual se pierde al recrear contenedor sin rebuild)
- [x] `make krea2-ext` — extensiones en `EXTENSIONS_PATH` (hecho; re-run OK tras fix SHA)
- [ ] Smoke test Identity Edit tras restart (face swap / sin Auto face-ref prep primero)
- [ ] Smoke test Moodboard
- [ ] `make push` / `push-cuda12` si se publica la imagen con los patches
