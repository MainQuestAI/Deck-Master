import json
import pytest
from build.build_route import resolve_build_route, persist_route
from build.run_policy import enforce_origin_mode


@pytest.mark.parametrize('changed', ['dev', 'fixture', 'benchmark'])
def test_persisted_production_mode_rejects_request_downgrade(tmp_path, changed):
    request={'run_mode':'production', 'profile':'native'}
    route=resolve_build_route(request,run_dir=tmp_path)
    persist_route(tmp_path,route)
    for new_request in ({**request,'run_mode':changed}, {**request,'run_mode':changed,'origin_run_mode':changed}):
        with pytest.raises(ValueError,match='RUN_MODE_CONFLICT'):
            resolve_build_route(new_request,run_dir=tmp_path)
    with pytest.raises(ValueError,match='RUN_MODE_CONFLICT'):
        enforce_origin_mode(tmp_path,request,changed)
    assert enforce_origin_mode(tmp_path,request)=='production'


def test_existing_fixture_retains_original_policy(tmp_path):
    request={'run_mode':'fixture'}
    persist_route(tmp_path,resolve_build_route(request,run_dir=tmp_path))
    assert enforce_origin_mode(tmp_path,request)=='fixture'
