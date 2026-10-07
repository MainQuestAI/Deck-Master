"""Exercise recovery boundaries without the source-test conftest borrowing src."""
import argparse
import json
from pathlib import Path
import sys

import deck_master
import deck_master.web
import pytest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    package = Path(deck_master.__file__).resolve().parent
    assert 'site-packages' in str(package), package
    assert not package.is_relative_to(repo / 'src'), package
    assert deck_master.web._static_dir().resolve().is_relative_to(package)
    # Preload the installed parent before conftest inserts src. Every subsequent
    # submodule must resolve through this parent's installed __path__, audited below.
    result = pytest.main(['-q', str(repo / 'tests/rebuild/test_rc_closure_browser.py'),
                         str(repo / 'tests/rebuild/test_workbench_usability_browser.py'),
                         str(repo / 'tests/rebuild/test_pr103_repair_browser.py'),
                         str(repo / 'tests/rebuild/test_pr103_complete_browser.py'),
                         str(repo / 'tests/rebuild/test_ux04_content_annotations_browser.py'),
                         str(repo / 'tests/rebuild/test_ux03_style_candidate_browser.py'),
                         str(repo / 'tests/rebuild/test_ux08_task_walkthrough_browser.py'), '--require-browser'])
    modules = {name: str(Path(module.__file__).resolve()) for name, module in sys.modules.items()
               if (name == 'deck_master' or name.startswith('deck_master.')) and getattr(module, '__file__', None)}
    assert all(Path(path).is_relative_to(package) for path in modules.values()), modules
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({'package': str(package), 'static': str(deck_master.web._static_dir()),
        'modules': modules, 'pytest_exit': int(result), 'fixture': 'synthetic', 'model_invocations': 0,
        'professional_evidence': 'not_evaluated'}, indent=2) + '\n')
    return int(result)


if __name__ == '__main__':
    sys.exit(main())
