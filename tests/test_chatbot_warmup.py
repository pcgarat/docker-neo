#!/usr/bin/env python3
"""Tests del warmup chatBot (parser + payload + params.txt)."""

from __future__ import annotations

import sys
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import chatbot_warmup as w  # noqa: E402


_SAMPLE_TXT2IMG = """a cat sitting on a fence
Negative prompt: blurry
Steps: 8, Sampler: Euler, Schedule type: Simple, CFG scale: 1, Seed: 1, Size: 832x1216, Model: krea2_krea2Int4Convrot_v10Turbo, Module 1: qwen3vl_4b, Module 2: krea2RealVae_v10, Version: neo-2.27
"""

_SAMPLE_IMG2IMG = """a dog
Steps: 12, Sampler: Euler, Schedule type: Simple, CFG scale: 1, Seed: 2, Size: 1024x1024, Model: klein9b, Denoising strength: 0.45, Version: neo-2.27
"""


class ParseLastGenTests(unittest.TestCase):
    def test_parse_txt2img_size_model_modules(self):
        fields = w.parse_last_gen(_SAMPLE_TXT2IMG)
        self.assertEqual(fields["width"], 832)
        self.assertEqual(fields["height"], 1216)
        self.assertEqual(fields["sd_model_checkpoint"], "krea2_krea2Int4Convrot_v10Turbo")
        self.assertEqual(fields["modules"], ["qwen3vl_4b", "krea2RealVae_v10"])
        self.assertNotIn("denoising_strength", fields)

    def test_parse_img2img_denoising(self):
        fields = w.parse_last_gen(_SAMPLE_IMG2IMG)
        self.assertEqual(fields["width"], 1024)
        self.assertEqual(fields["height"], 1024)
        self.assertEqual(fields["denoising_strength"], 0.45)

    def test_parse_empty_does_not_invent(self):
        self.assertEqual(w.parse_last_gen(""), {})

    def test_detect_mode_from_folder(self):
        self.assertEqual(
            w.detect_mode("/data/output/img2img-images/x.png", {}),
            "img2img",
        )
        self.assertEqual(
            w.detect_mode("/data/output/txt2img-images/x.png", {}),
            "txt2img",
        )

    def test_detect_mode_denoising_fallback(self):
        self.assertEqual(
            w.detect_mode(None, {"denoising_strength": 0.4}),
            "img2img",
        )
        self.assertEqual(w.detect_mode(None, {}), "txt2img")


class BuildWarmupBodyTests(unittest.TestCase):
    def test_txt2img_uses_dummy_prompt_and_compile_script(self):
        fields = w.parse_last_gen(_SAMPLE_TXT2IMG)
        body = w.build_warmup_body(fields, "txt2img")
        self.assertEqual(body["prompt"], w._WARMUP_PROMPT)
        self.assertNotIn("cat", body["prompt"])
        self.assertEqual(body["steps"], 1)
        self.assertEqual(body["width"], 832)
        self.assertEqual(body["height"], 1216)
        self.assertFalse(body["save_images"])
        self.assertFalse(body["send_images"])
        self.assertEqual(
            body["alwayson_scripts"][w._COMPILE_SCRIPT]["args"],
            [w._COMPILE_PRESET],
        )
        self.assertEqual(
            body["override_settings"]["sd_model_checkpoint"],
            "krea2_krea2Int4Convrot_v10Turbo",
        )
        self.assertNotIn("init_images", body)

    def test_img2img_requires_init_and_keeps_size(self):
        fields = w.parse_last_gen(_SAMPLE_IMG2IMG)
        with self.assertRaises(w.WarmupSkip):
            w.build_warmup_body(fields, "img2img")
        body = w.build_warmup_body(fields, "img2img", init_image_b64="abc")
        self.assertEqual(body["init_images"], ["abc"])
        self.assertEqual(body["denoising_strength"], 0.45)
        self.assertEqual(body["width"], 1024)

    def test_load_last_gen_skips_without_size(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "params.txt").write_text("no size here\n", encoding="utf-8")
            with self.assertRaises(w.WarmupSkip):
                w.load_last_gen(tmp)


class ParamsTxtGuardTests(unittest.TestCase):
    def test_restores_previous_contents_after_overwrite(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "params.txt"
            path.write_text("ORIGINAL\nSize: 832x1216", encoding="utf-8")
            with w.ParamsTxtGuard(tmp):
                path.write_text("WARMUP OVERWRITE", encoding="utf-8")
            self.assertEqual(path.read_text(encoding="utf-8"), "ORIGINAL\nSize: 832x1216")

    def test_deletes_file_if_it_did_not_exist(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "params.txt"
            with w.ParamsTxtGuard(tmp):
                path.write_text("created by forge", encoding="utf-8")
            self.assertFalse(path.exists())


class LatestImageTests(unittest.TestCase):
    def test_picks_newest_image(self):
        import os
        import tempfile
        import time

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "output" / "txt2img-images"
            out.mkdir(parents=True)
            old = out / "old.png"
            new = out / "new.png"
            old.write_bytes(b"old")
            time.sleep(0.05)
            new.write_bytes(b"new")
            os.utime(old, (1, 1))
            latest = w.find_latest_output_image(tmp)
            self.assertEqual(latest, new)

    def test_missing_output_returns_none(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(w.find_latest_output_image(tmp))


class WaitForApiTests(unittest.TestCase):
    def test_http_json_wraps_connection_reset(self):
        """Forge resetea el socket mientras arranca; no debe escapar ConnectionResetError."""

        def boom(*_args, **_kwargs):
            raise ConnectionResetError(104, "Connection reset by peer")

        with mock.patch("chatbot_warmup.urllib.request.urlopen", side_effect=boom):
            with self.assertRaises(w.WarmupError) as ctx:
                w._http_json("GET", "http://127.0.0.1:7860/sdapi/v1/options", timeout=1.0)
        self.assertIn("Connection reset", str(ctx.exception))

    def test_wait_for_api_retries_after_connection_reset(self):
        calls = {"n": 0}

        def flaky(method, url, *, payload=None, timeout):
            calls["n"] += 1
            if calls["n"] == 1:
                raise w.WarmupError("Red http://x: Connection reset by peer")
            return 200, {}

        with mock.patch("chatbot_warmup._http_json", side_effect=flaky):
            w.wait_for_api("http://127.0.0.1:7860", timeout_seconds=5.0, poll_seconds=0.01)
        self.assertGreaterEqual(calls["n"], 2)


if __name__ == "__main__":
    unittest.main()
