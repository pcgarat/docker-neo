#!/usr/bin/env python3
"""Warmup de Forge Neo para el chatBot: compile al size del último gen.

POST de 1 step con Torch Compile Integrated (guard_filter_fn).
No deja la imagen en output/ y restaura params.txt (Forge lo pisa siempre).
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_STEPS_LINE = re.compile(
    r"Size:\s*(?P<w>\d+)x(?P<h>\d+)",
    re.IGNORECASE,
)
_MODEL = re.compile(r"Model:\s*([^,]+)", re.IGNORECASE)
_DENOISING = re.compile(r"Denoising strength:\s*([0-9.]+)", re.IGNORECASE)
_MODULE = re.compile(r"Module\s+(\d+):\s*([^,]+)", re.IGNORECASE)
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_WARMUP_PROMPT = "compile warmup"
_COMPILE_SCRIPT = "Torch Compile Integrated"
_COMPILE_PRESET = "guard_filter_fn"


class WarmupSkip(RuntimeError):
    """No hay último gen; el contenedor puede seguir, pero no se compiló."""


class WarmupError(RuntimeError):
    """API caída o generación fallida."""


def parse_last_gen(info: str) -> dict[str, Any]:
    """Extrae width/height/checkpoint/modules/denoising del infotext. No inventa defaults."""
    text = info or ""
    out: dict[str, Any] = {}
    size = _STEPS_LINE.search(text)
    if size:
        out["width"] = int(size.group("w"))
        out["height"] = int(size.group("h"))
    model = _MODEL.search(text)
    if model:
        out["sd_model_checkpoint"] = model.group(1).strip()
    den = _DENOISING.search(text)
    if den:
        out["denoising_strength"] = float(den.group(1))
    found = _MODULE.findall(text)
    found.sort(key=lambda t: int(t[0]))
    modules = [name.strip() for _, name in found if name.strip()]
    if modules:
        out["modules"] = modules
    return out


def find_latest_output_image(data_path: str | Path) -> Path | None:
    root = Path(data_path) / "output"
    if not root.is_dir():
        return None
    latest: Path | None = None
    latest_mtime = -1.0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in _IMAGE_SUFFIXES:
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime > latest_mtime:
            latest_mtime = mtime
            latest = path
    return latest


def detect_mode(source_path: str | None, fields: dict[str, Any]) -> str:
    path = (source_path or "").replace("\\", "/").lower()
    if "img2img-images" in path:
        return "img2img"
    if "txt2img-images" in path:
        return "txt2img"
    if "denoising_strength" in fields:
        return "img2img"
    return "txt2img"


def read_params_txt(data_path: str | Path) -> str:
    path = Path(data_path) / "params.txt"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def load_last_gen(data_path: str | Path) -> tuple[dict[str, Any], Path | None, str]:
    """Campos del último gen + ruta de imagen + modo txt2img|img2img."""
    params = read_params_txt(data_path)
    latest = find_latest_output_image(data_path)
    fields = parse_last_gen(params)
    if "width" not in fields or "height" not in fields:
        raise WarmupSkip(
            "No hay Size en params.txt. Genera una imagen en la WebUI y vuelve a lanzar "
            "make chatbot-warmup."
        )
    mode = detect_mode(str(latest) if latest else None, fields)
    return fields, latest, mode


def build_warmup_body(
    fields: dict[str, Any],
    mode: str,
    init_image_b64: str | None = None,
) -> dict[str, Any]:
    """Payload de 1 step al size del último gen. Prompt dummy; no reusa el del infotext."""
    body: dict[str, Any] = {
        "prompt": _WARMUP_PROMPT,
        "steps": 1,
        "width": fields["width"],
        "height": fields["height"],
        "save_images": False,
        "send_images": False,
        "alwayson_scripts": {
            _COMPILE_SCRIPT: {"args": [_COMPILE_PRESET]},
        },
    }
    checkpoint = fields.get("sd_model_checkpoint")
    if checkpoint:
        body["override_settings"] = {"sd_model_checkpoint": checkpoint}
        body["override_settings_restore_afterwards"] = True
    if mode == "img2img":
        if not init_image_b64:
            raise WarmupSkip(
                "Último gen fue img2img pero no hay imagen en output/. "
                "Genera una en la WebUI o usa txt2img."
            )
        body["init_images"] = [init_image_b64]
        if "denoising_strength" in fields:
            body["denoising_strength"] = fields["denoising_strength"]
        else:
            body["denoising_strength"] = 0.3
    return body


def file_to_b64(path: Path) -> str:
    raw = path.read_bytes()
    return base64.b64encode(raw).decode("ascii")


class ParamsTxtGuard:
    """Restaura params.txt tras el POST: Forge lo escribe aunque save_images=false."""

    def __init__(self, data_path: str | Path):
        self.path = Path(data_path) / "params.txt"
        self._backup: bytes | None = None
        self._existed = False

    def __enter__(self) -> ParamsTxtGuard:
        self._existed = self.path.is_file()
        if self._existed:
            self._backup = self.path.read_bytes()
        return self

    def __exit__(self, *exc: object) -> None:
        if self._existed and self._backup is not None:
            self.path.write_bytes(self._backup)
            return
        if not self._existed and self.path.is_file():
            self.path.unlink()


def _http_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float,
) -> tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            body = json.loads(raw.decode("utf-8")) if raw else None
            return resp.status, body
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise WarmupError(f"HTTP {exc.code} {url}: {detail}") from exc
    except json.JSONDecodeError as exc:
        raise WarmupError(f"JSON inválido {url}: {exc}") from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        # ConnectionResetError / timeout: el puerto escucha antes de que Gradio/API esté listo.
        raise WarmupError(f"Red {url}: {exc}") from exc


def wait_for_api(base_url: str, timeout_seconds: float, poll_seconds: float = 2.0) -> None:
    url = f"{base_url.rstrip('/')}/sdapi/v1/options"
    deadline = time.monotonic() + timeout_seconds
    last_err = "sin intento"
    next_log = time.monotonic()
    while time.monotonic() < deadline:
        try:
            status, _ = _http_json("GET", url, timeout=min(10.0, timeout_seconds))
            if status == 200:
                return
        except WarmupError as exc:
            last_err = str(exc)
        now = time.monotonic()
        if now >= next_log:
            left = int(deadline - now)
            print(f"Esperando API Forge ({left}s restantes)…", file=sys.stderr, flush=True)
            next_log = now + 30
        time.sleep(poll_seconds)
    raise WarmupError(f"Forge no respondió en {timeout_seconds:.0f}s: {last_err}")


def run_warmup(
    data_path: str | Path,
    base_url: str,
    *,
    wait_timeout: float = 600.0,
    generate_timeout: float = 600.0,
) -> None:
    fields, latest, mode = load_last_gen(data_path)
    init_b64 = file_to_b64(latest) if mode == "img2img" and latest else None
    body = build_warmup_body(fields, mode, init_b64)
    wait_for_api(base_url, wait_timeout)
    endpoint = "txt2img" if mode == "txt2img" else "img2img"
    url = f"{base_url.rstrip('/')}/sdapi/v1/{endpoint}"
    print(
        f"Warmup {endpoint} {fields['width']}x{fields['height']} "
        f"compile={_COMPILE_PRESET} checkpoint={fields.get('sd_model_checkpoint', '?')}",
        file=sys.stderr,
        flush=True,
    )
    t0 = time.perf_counter()
    with ParamsTxtGuard(data_path):
        _http_json("POST", url, payload=body, timeout=generate_timeout)
    elapsed = time.perf_counter() - t0
    print(f"Warmup ok ({elapsed:.1f}s). params.txt restaurado.", file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-path", default="", help="DATA_PATH del host (params.txt + output/)")
    parser.add_argument("--base-url", default="http://127.0.0.1:7860")
    parser.add_argument("--wait-timeout", type=float, default=600.0)
    parser.add_argument("--generate-timeout", type=float, default=600.0)
    args = parser.parse_args(argv)
    data_path = (args.data_path or "").strip()
    if not data_path:
        print("Falta --data-path (DATA_PATH del .env).", file=sys.stderr)
        return 2
    try:
        run_warmup(
            data_path,
            args.base_url,
            wait_timeout=args.wait_timeout,
            generate_timeout=args.generate_timeout,
        )
    except WarmupSkip as exc:
        print(f"Warmup omitido: {exc}", file=sys.stderr)
        return 0
    except WarmupError as exc:
        print(f"Warmup falló: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
