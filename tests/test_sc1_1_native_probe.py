"""SC-1.1 ND-02 tests: native runtime probe + suite readiness integration.

Acceptance mapping:
- IND-01 (engineering): a clean environment (no backend_bindings, no
  global skills, no ppt-master on PATH) yields a real native probe —
  ready/degraded_ready from kernel evidence, never from a binding or an
  env flag.
- IND-05: probe never fakes readiness from installed/contract_declared.
- GOV-02: public probe summary is redacted (no absolute paths, no
  machine specifics).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from native_pptx import probe as probe_module  # noqa: E402
from native_pptx.probe import native_runtime_ready, probe_native_runtime, public_probe_summary  # noqa: E402


class ProbeTests(unittest.TestCase):
    def test_probe_reports_kernel_evidence_without_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("os.environ", {"DECK_MASTER_NATIVE_FONTS_DIR": ""}, clear=False), mock.patch(
            "shutil.which", return_value=None
        ):
            probe = probe_native_runtime()
        self.assertIn(probe["status"], {"ready", "degraded_ready"})
        self.assertEqual([], probe["required_missing"], "kernel modules import in a clean environment")
        self.assertEqual("unverified", probe["checks"]["fonts"]["status"])
        self.assertFalse(probe["renderer"]["configured"], "renderer must not be faked as configured")

    def test_missing_python_pptx_blocks(self) -> None:
        import builtins

        real_import = builtins.__import__

        def blocked_import(name, *args, **kwargs):
            if name == "pptx":
                raise ImportError("simulated missing python-pptx")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=blocked_import):
            probe = probe_native_runtime()
        self.assertEqual("blocked", probe["status"])
        self.assertTrue(any("python-pptx" in item for item in probe["required_missing"]))

    def test_env_flag_cannot_fake_readiness(self) -> None:
        with mock.patch.dict("os.environ", {"DECK_MASTER_PPT_MASTER_RUNTIME_WIRED": "1"}, clear=False):
            probe = probe_native_runtime()
        self.assertIn(probe["status"], {"ready", "degraded_ready"})
        # the old env flag is simply irrelevant to the native probe
        self.assertTrue(native_runtime_ready(probe) == (probe["status"] in {"ready", "degraded_ready"}))

    def test_public_summary_is_redacted(self) -> None:
        probe = probe_native_runtime()
        public = public_probe_summary(probe)
        self.assertFalse(str(public_probe_summary(probe)).count("/Users/") >= 1)
        self.assertEqual(probe["status"], public["status"])

    def test_engine_fingerprint_changes_break_old_probe_id(self) -> None:
        probe = probe_native_runtime()
        first = probe["probe_id"]
        target = ROOT / "scripts" / "native_pptx" / "probe.py"
        original = target.read_text(encoding="utf-8")
        try:
            target.write_text(original + "\n# fingerprint drift\n", encoding="utf-8")
            probe2 = probe_native_runtime()
        finally:
            target.write_text(original, encoding="utf-8")
        self.assertNotEqual(first, probe2["probe_id"])


if __name__ == "__main__":
    unittest.main()
