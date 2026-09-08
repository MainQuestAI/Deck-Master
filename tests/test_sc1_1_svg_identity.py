"""SC-1.1 batch-2.2 tests (failing-first): SVG result identity.

Acceptance mapping (review P1-04 / spec 05 section 5.5):
- The caller's action_id is authoritative — the applied record keeps it.
- The input fingerprint is REAL (page package + lock + page id), recomputed
  at commit: a late result produced against older inputs is rejected, not
  silently overwriting the newer SVG.
- Replay of the same action with the same output is idempotent; the same
  action with a DIFFERENT output is a conflict.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import test_high_density_builder as hd_helpers  # noqa: E402
from build.native_engine import _svg_input_fingerprint, submit_approved_svg  # noqa: E402
from runtime.run_state import write_json  # noqa: E402


def _run(tmp: Path) -> Path:
    run, _ = hd_helpers._make_run(tmp, mode="fixture", page_count=1)
    hd_helpers._blueprint(run, "P001")
    hd_helpers.prepare_high_density(run)
    hd_helpers.run_high_density(run)
    write_json(run / "request.json", {"run_id": run.name, "run_mode": "fixture", "profile": "native", "authoring_mode": "direct_svg"})
    return run


class SvgIdentityTests(unittest.TestCase):
    def test_fingerprint_changes_with_package_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _run(Path(tmp))
            before = _svg_input_fingerprint(run, "P001")
            package = run / "page_packages" / "P001.json"
            package.write_text(package.read_text(encoding="utf-8").replace("P001", "P001-edited"), encoding="utf-8")
            after = _svg_input_fingerprint(run, "P001")
            self.assertNotEqual(before, after, "the fingerprint must bind current package content")

    def test_late_result_rejected_when_inputs_moved_on(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _run(Path(tmp))
            svg_path = run / "high_density_build" / "svg" / "P001.svg"
            original = svg_path.read_text(encoding="utf-8")
            # host result produced against the OLD inputs
            submit_approved_svg(run, "P001", original, action_id="act-svg-1")
            # inputs move on (package edited)
            package = run / "page_packages" / "P001.json"
            old_fingerprint = _svg_input_fingerprint(run, "P001")
            package.write_text(package.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaises(Exception) as ctx:
                submit_approved_svg(run, "P001", "<svg>late</svg>", action_id="act-svg-late", produced_against=old_fingerprint)
            self.assertIn("input", str(ctx.exception).lower() + str(getattr(ctx.exception, "code", "")))

    def test_replay_same_output_idempotent_conflict_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _run(Path(tmp))
            svg_path = run / "high_density_build" / "svg" / "P001.svg"
            original = svg_path.read_text(encoding="utf-8")
            first = submit_approved_svg(run, "P001", original, action_id="act-svg-r")
            self.assertEqual("svg_staged", first["status"])
            self.assertEqual("act-svg-r", first["action_id"], "the caller action id must be preserved")
            replay = submit_approved_svg(run, "P001", original, action_id="act-svg-r")
            self.assertEqual("already_applied", replay["status"])
            from build.native_engine import NativeEngineError

            with self.assertRaises(NativeEngineError) as ctx:
                submit_approved_svg(run, "P001", "<svg>different</svg>", action_id="act-svg-r")
            self.assertEqual("NDC_ACTION_CONFLICT", ctx.exception.code)


if __name__ == "__main__":
    unittest.main()
