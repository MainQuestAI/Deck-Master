import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from build.build_route import resolve_build_route, persist_route
from deck_master import build_parser, _persist_build_options


def test_route_outputs_match_contract():
    schema = json.loads((Path(__file__).parents[1] / 'docs/specs/sc1.1-native-deck-core/contracts/build-route.v1.schema.json').read_text())
    for profile in ('native', 'direct-svg', 'standard', 'legacy-ppt-master', 'high-density'):
        Draft202012Validator(schema).validate(resolve_build_route({'profile': profile}))


def test_old_standard_keeps_legacy(tmp_path):
    (tmp_path / 'build').mkdir()
    (tmp_path / 'build/render_request.json').write_text('{}')
    route = resolve_build_route({'builder_profile': 'standard'}, run_dir=tmp_path)
    assert route['engine_id'] == 'legacy_ppt_master'


@pytest.mark.parametrize('profile', ['native', 'direct-svg', 'legacy-ppt-master'])
def test_cli_records_public_profile(tmp_path, profile):
    (tmp_path / 'request.json').write_text(json.dumps({'run_id': tmp_path.name, 'run_mode': 'fixture'}))
    args = build_parser().parse_args(['build', 'run', '--run-dir', str(tmp_path), '--profile', profile])
    _persist_build_options(tmp_path, args)
    assert json.loads((tmp_path / 'request.json').read_text())['profile'] == profile


def test_cli_conflict_is_not_silent(tmp_path):
    (tmp_path / 'request.json').write_text(json.dumps({'run_id': tmp_path.name, 'run_mode': 'fixture'}))
    persist_route(tmp_path, resolve_build_route({'profile': 'native', 'run_mode': 'fixture'}))
    args = build_parser().parse_args(['build', 'run', '--run-dir', str(tmp_path), '--profile', 'legacy-ppt-master'])
    with pytest.raises(ValueError, match='conflict'):
        _persist_build_options(tmp_path, args)


def test_cli_explicit_native_cannot_skip_legacy_migration(tmp_path):
    import argparse,json
    from deck_master import _persist_build_options
    (tmp_path/'build').mkdir()
    (tmp_path/'request.json').write_text(json.dumps({'run_id':tmp_path.name,'run_mode':'production','builder_profile':'standard'}))
    (tmp_path/'build/render_request.json').write_text('{}')
    with pytest.raises(ValueError,match='migrate'):
        _persist_build_options(tmp_path,argparse.Namespace(profile='native',authoring_mode=None))
    assert not (tmp_path/'build/route.json').exists()

def test_only_persisted_native_file_quality_avoids_legacy_setup(tmp_path):
    from deck_master import _native_file_quality_command
    args = build_parser().parse_args(['prepare-quality-review', '--run-dir', str(tmp_path)])
    assert not _native_file_quality_command(args)
    persist_route(tmp_path, resolve_build_route({'profile':'native'}))
    assert _native_file_quality_command(args)
    args.command = 'export'
    assert not _native_file_quality_command(args)
