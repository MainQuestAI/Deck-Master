"""Read-only installed-package audit; external pytest is only a runner dependency."""
import json
from pathlib import Path
import sys

import deck_master

OUT = Path(__file__).resolve().parent
SNAPSHOT = Path('/workspace/work/rc3/reviews/rc3-03-code-snapshot-5dbdf72')
INSTALLED = Path(deck_master.__file__).resolve().parent
# The candidate is a runtime-only install. Reuse existing local pytest without
# installing anything or changing candidate package resolution.
sys.path.append('/workspace/Deck-Master/.venv/lib/python3.12/site-packages')
import pytest

NODES = {
 'test_rc3_design_requirements.py': [
  'test_complete_raw_requirements_and_basis_are_readonly',
  'test_legacy_no_plan_fidelity_has_honest_null_fields',
  'test_imported_real_mapping_without_roles_returns_honest_nulls',
  'test_unrelated_density_timing_and_audit_do_not_change_consumed_slices'],
 'test_rc3_design_recipes.py': ['test_parameters_execute_and_planning_prose_cannot_override_or_change_page'],
 'test_rc3_design_feasibility.py': ['test_feasibility_recipe_refuses_public_sample_plan_and_pure_production_compile'],
 'test_rc3_design_workflows.py': ['test_authorized_first_two_initial_pages_reverse_arrival_remain_candidates'],
 'test_rc3_restyle_workflows.py': [
  'test_restyle_uses_target_first_then_ordered_original_jpeg_and_png_through_freeze',
  'test_consumed_font_and_page_parameters_alone_control_task_freshness'],
 'test_rc3_adopted_design_handoff.py': ['test_formal_adoption_hands_full_immutable_context_to_every_visual_consumer'],
 'test_rc3_design_native.py': [
  'test_legal_full_page_has_native_editable_atoms_units_notes_and_reading_order',
  'test_identical_table_text_at_wrong_row_is_located_at_cell_atom',
  'test_same_text_reversed_business_arrow_is_located',
  'test_same_page_relations_with_only_real_svg_transform_pass'],
 'test_production.py': ['test_prompt_projects_all_visible_fields_and_excludes_internal_notes',
  'test_only_allowed_assets_enter_prompt', 'test_blueprint_task_exposes_only_allowed_asset_bytes'],
}

class AuditPlugin:
 def pytest_sessionfinish(self, session, exitstatus):
  modules = {name: str(Path(module.__file__).resolve())
             for name, module in sys.modules.items()
             if (name == 'deck_master' or name.startswith('deck_master.')) and getattr(module, '__file__', None)}
  foreign = {name: path for name, path in modules.items() if not Path(path).is_relative_to(INSTALLED)}
  (OUT/'targeted-import-identity.json').write_text(json.dumps({
   'python': sys.executable, 'installed_root': str(INSTALLED),
   'pytest_dependency': pytest.__file__, 'modules': modules,
   'foreign_product_modules': foreign, 'pytest_exit_code': int(exitstatus)}, indent=2)+'\n')
  if foreign:
   session.exitstatus = 1

args = ['-q', '-p', 'no:cacheprovider', '--basetemp='+str(OUT/'pytest-tmp'),
        '--junitxml='+str(OUT/'targeted-tests.xml')]
args.extend(str(SNAPSHOT/'tests/rebuild'/filename)+'::'+node for filename, nodes in NODES.items() for node in nodes)
(OUT/'targeted-selection.json').write_text(json.dumps(args, indent=2)+'\n')
raise SystemExit(pytest.main(args, plugins=[AuditPlugin()]))
