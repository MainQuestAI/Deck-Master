"""Fixed installed-package F9 review; external local pytest is runner-only."""
from pathlib import Path
import json
import sys
import deck_master

OUT=Path(__file__).resolve().parent
SNAPSHOT=Path('/workspace/work/rc3/reviews/rc3-03-code-snapshot-cf61e5e')
INSTALLED=Path(deck_master.__file__).resolve().parent
sys.path.append('/workspace/work/rc3/reviews/env-03-snapshot-cf61e5e/lib/python3.12/site-packages')
import pytest

class Identity:
 def pytest_sessionfinish(self,session,exitstatus):
  modules={name:str(Path(module.__file__).resolve()) for name,module in sys.modules.items()
   if (name=='deck_master' or name.startswith('deck_master.')) and getattr(module,'__file__',None)}
  foreign={name:path for name,path in modules.items() if not Path(path).is_relative_to(INSTALLED)}
  (OUT/'targeted-import-identity.json').write_text(json.dumps({'installed_root':str(INSTALLED),
   'pytest':pytest.__file__,'modules':modules,'foreign_modules':foreign,'pytest_exit_code':int(exitstatus)},indent=2)+'\n')
  if foreign:session.exitstatus=1

nodes=['test_rc3_decision_visual_consumption.py',
 'test_rc3_adopted_design_handoff.py::test_legacy_generation_shape_without_requirements_remains_legacy_at_rc3_floor',
 'test_rc3_adopted_design_handoff.py::test_content_requalification_can_review_changed_page_before_new_visual_production',
 'test_rc3_adopted_design_handoff.py::test_closed_actual_execution_is_not_reauthenticated_by_a_new_reader',
 'test_rc3_adopted_design_handoff.py::test_modern_corrupt_lineage_never_silently_falls_back_to_default',
 'test_rc3_adopted_design_handoff.py::test_formal_adoption_hands_full_immutable_context_to_every_visual_consumer',
 'test_rc3_adopted_design_handoff.py::test_unconsumed_changes_preserve_frozen_writer_context_and_svg_basis',
 'test_rc3_adopted_design_handoff.py::test_relevant_changes_refuse_new_writer_and_late_consumption']
args=['-q','-p','no:cacheprovider','--basetemp='+str(OUT/'pytest-tmp'),'--junitxml='+str(OUT/'targeted-tests.xml')]
args.extend(str(SNAPSHOT/'tests/rebuild'/node) for node in nodes)
(OUT/'targeted-selection.json').write_text(json.dumps(args,indent=2)+'\n')
raise SystemExit(pytest.main(args,plugins=[Identity()]))
