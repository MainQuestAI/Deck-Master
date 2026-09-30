"""A02 browser-verification fixture: real launcher + mixed project registry.

Creates five synthetic projects (editable sample, readonly sample, v1-format
project, empty project, and one whose directory is later removed to produce a
missing-directory entry), registers them in an isolated registry, and starts
the real launcher service. No model calls.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from deck_master import service
from deck_master.launcher import open_workbench
from deck_master.registry import register
from deck_master.samples import create_sample

V1_PAGE = {"schema_version": "deck_page_package.v2", "page_id": "one",
           "customer_visible": {"title": "旧格式项目页", "body_blocks": []},
           "visual_spec": {"intent": "A02 verification", "reference_mode": "new_design"}}


def main():
    root = Path(tempfile.mkdtemp(prefix='deck-master-a02-'))
    registry_file = root / 'registry.json'
    editable = root / 'editable-project'
    create_sample(editable, page_count=3, readonly=False)
    readonly = root / 'readonly-sample'
    create_sample(readonly, page_count=2, readonly=True)
    v1 = root / 'v1-project'
    service.create(v1, brief='A02 v1 格式验证', draft={'pages': [V1_PAGE]})
    empty = root / 'empty-project'
    service.create(empty, brief='A02 空项目验证：还没有页面')
    missing = root / 'missing-project'
    create_sample(missing, page_count=2, readonly=False)
    for path in (editable, readonly, v1, empty, missing):
        register(registry_file, path)
    shutil.rmtree(missing)  # registered entry whose directory no longer exists
    result = open_workbench(registry_file=registry_file, ui='v2', port=0, open_browser=False)
    print(json.dumps({'url': result['url'], 'registry': str(registry_file), 'root': str(root),
                      'projects': {'editable': str(editable), 'readonly': str(readonly),
                                   'v1': str(v1), 'empty': str(empty)}}))
    try:
        sys.stdin.read()
    finally:
        from deck_master.web import stop_service
        stop_service(registry_file)
        for name in ('editable-project', 'readonly-sample', 'v1-project', 'empty-project'):
            target = root / name
            if target.exists():
                shutil.rmtree(target)


if __name__ == '__main__':
    main()
