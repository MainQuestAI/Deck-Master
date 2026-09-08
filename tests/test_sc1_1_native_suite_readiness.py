from __future__ import annotations
import sys
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from skills import installer


def test_suite_never_claims_render_from_compile_only_evidence(tmp_path):
    probe={'status':'degraded_ready','checks':{'compile_smoke':{'status':'verified'},'render_smoke':{'status':'blocked'},'fonts':{'status':'unverified'}},'capabilities':{'compile':'verified','render':'blocked','fonts':'unverified'}}
    with mock.patch('native_pptx.probe.probe_native_runtime',return_value=probe) as observed, mock.patch.object(installer,'inspect_library_status',return_value={'status':'ready'}):
        status=installer.inspect_suite_status(targets=['custom'],agent_skill_dir=str(tmp_path))
    assert status['task_readiness']['render']=='blocked'
    assert not status['client_delivery_ready']
    assert observed.call_count==1
