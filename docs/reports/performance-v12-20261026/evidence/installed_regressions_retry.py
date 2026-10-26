"""Installed-wheel audit using the repository's existing preload convention."""
import json,sys
from pathlib import Path
import deck_master
import deck_master.web
import pytest
package=Path(deck_master.__file__).resolve().parent
assert 'site-packages' in str(package) and not package.is_relative_to(Path('/workspace/Deck-Master/src'))
repo=Path('/workspace/Deck-Master')
names=['test_performance_read_paths.py','test_performance_execution_paths.py','test_performance_successors.py','test_performance_frontend_browser.py','test_performance_overview_browser.py','test_pr187_summary_reuse_browser.py','test_pr189_clear_ownership_browser.py','test_pr189_clear_storage_browser.py','test_pr189_related_clear_backup.py','test_pr189_related_clear_browser.py','test_pr189_clear_capacity.py','test_pr189_clear_capacity_browser.py']
names=json.loads(Path('/workspace/scratch/performance-input/installed-retry-selectors.json').read_text())
result=pytest.main(['-q',*[str(repo/name) for name in names],'--require-browser'])
modules={name:str(Path(m.__file__).resolve()) for name,m in sys.modules.items() if (name=='deck_master' or name.startswith('deck_master.')) and getattr(m,'__file__',None)}
assert all(Path(path).is_relative_to(package) for path in modules.values()),modules
Path('/workspace/scratch/performance-input/installed-origin-retry.json').write_text(json.dumps({'package':str(package),'static':str(deck_master.web._static_dir()),'modules':modules,'pytest_exit':int(result),'selectors':names,'source_commit':'84a3a60efb9721491fd0845ca766caa1244df7d0','synthetic':True,'model_invocations':0},indent=2)+'\n')
sys.exit(int(result))
