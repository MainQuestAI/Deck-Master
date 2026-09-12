"""SC-1.1 ND-01 tests: single-implementation extraction + facade integrity.

Acceptance mapping:
- CMP-06 (engineering): extraction identity — the high-density entry and the
  native entry resolve to the SAME implementation objects (no copied
  compiler); no HOME / external PPT Master probing in the kernel.
- CMP-07/GOV-02: the facade refuses to compile without the adapter-injected
  approved-SVG validator (business validation stays with the adapter).
- F-N08 (paired with ND-02): page package written as ready_for_build is
  accepted by the build consumer — status-value consistency.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import high_density.pptx as hd_pptx  # noqa: E402
import native_pptx.pptx as native_pptx_impl  # noqa: E402
from native_pptx import api  # noqa: E402
from native_pptx.svg_pipeline import svg_path as pipeline_svg_path  # noqa: E402


class SingleImplementationTests(unittest.TestCase):
    def test_hd_entry_aliases_native_kernel(self) -> None:
        self.assertTrue(hd_pptx.compile_pptx is native_pptx_impl.compile_pptx)
        self.assertTrue(hd_pptx.readback_pptx is native_pptx_impl.readback_pptx)
        self.assertEqual(str(hd_pptx.__file__), str(native_pptx_impl.__file__))

    def test_kernel_does_not_probe_home_or_external_backend(self) -> None:
        from pathlib import Path

        for module_file in ("native_pptx/pptx.py", "native_pptx/svg_pipeline.py", "native_pptx/svg_native.py", "native_pptx/svg_paint.py"):
            text = (ROOT / "scripts" / module_file).read_text(encoding="utf-8")
            self.assertNotIn("Path.home()", text, module_file)
            self.assertNotIn("ppt-master", text, module_file)

    def test_facade_requires_injected_validator(self) -> None:
        request = api.NativeCompileRequest(root=ROOT / "nonexistent-run", scenes=[{"page_id": "P001"}], locks={})
        with self.assertRaises(api.NativeCompileError) as ctx:
            api.compile_svg_deck(request)
        self.assertEqual("NDC_COMPILE_FAILED", ctx.exception.code)
        self.assertIn("validate_approved", str(ctx.exception))

    def test_hash_mismatch_blocks_compile(self) -> None:
        request = api.NativeCompileRequest(
            root=ROOT / "nonexistent-run",
            scenes=[{"page_id": "P001"}],
            locks={},
            validate_approved=lambda *args: None,
            expected_sha256={"P001": "0" * 64},
        )
        with self.assertRaises(api.NativeCompileError) as ctx:
            api.compile_svg_deck(request)
        self.assertEqual(api.NDC_READBACK_FAILED, ctx.exception.code)
        self.assertEqual("P001", ctx.exception.page_id)

    def test_svg_path_helpers_single_source(self) -> None:
        import high_density.svg as hd_svg

        self.assertTrue(hd_svg.svg_path is pipeline_svg_path)


if __name__ == "__main__":
    unittest.main()
