from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from runtime.skill_route import route_for_input_type, route_for_stage  # noqa: E402


class SkillRouteTest(unittest.TestCase):
    def test_input_type_routes_to_public_skill(self) -> None:
        self.assertEqual("deck-brief", route_for_input_type("raw_materials")["recommended_skill"])
        self.assertEqual("deck-sourcing", route_for_input_type("historical-slide-search")["recommended_skill"])
        self.assertEqual("deck-quality", route_for_input_type("pptx_package")["recommended_skill"])

    def test_build_stage_routes_to_deck_builder_with_backend(self) -> None:
        route = route_for_stage("needs_build", next_command="deck-master build prepare")

        self.assertEqual("deck-builder", route["recommended_skill"])
        self.assertEqual("ppt-master", route["backend_dependency"])
        self.assertIn("ppt-master", route["compat_skills"])

    def test_missing_builder_backend_routes_to_deck_builder(self) -> None:
        route = route_for_stage("needs_builder_backend", next_command="deck-master suite-status")

        self.assertEqual("deck-builder", route["recommended_skill"])
        self.assertEqual("build", route["skill_stage"])

    def test_upgrade_inputs_route_to_deck_upgrade(self) -> None:
        for input_type in ("upgrade", "rollback", "release-tree"):
            with self.subTest(input_type=input_type):
                self.assertEqual("deck-upgrade", route_for_input_type(input_type)["recommended_skill"])


if __name__ == "__main__":
    unittest.main()
