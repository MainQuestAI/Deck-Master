"""Real invalid SVGs keep structured context through compiler wrappers."""
import hashlib
import sys
from pathlib import Path
import pytest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).parent)]
from native_pptx.api import NativeCompileError,NativeCompileRequest,compile_svg_deck
from high_density.svg import validate_approved_svg,svg_path
from test_high_density_builder_v2 import _prepared_fixture

@pytest.fixture(scope='module')
def sample(tmp_path_factory):
    root,lock,scene=_prepared_fixture(tmp_path_factory.mktemp('error_context'))
    return root,lock,scene,svg_path(root,'P001').read_text()

@pytest.mark.parametrize('element,extra,code',[
 ('bad.image','<image id="bad.image" data-pptx-bounds="1,1,10,10" x="1" y="1" width="10" height="10" href="https://example.invalid/a.png"/>','NDC_ASSET_UNREGISTERED'),
 ('bad.embedded','<image id="bad.embedded" data-pptx-asset="registered" data-pptx-bounds="1,1,10,10" x="1" y="1" width="10" height="10" href="https://example.invalid/a.png"/>','NDC_ASSET_UNREGISTERED'),
 ('bad.script','<script id="bad.script">alert(1)</script>','NDC_SVG_UNSUPPORTED'),
 ('bad.use','<use id="bad.use" href="https://example.invalid/file.svg#x"/>','NDC_COMPILE_FAILED'),
 ('bad.filter','<defs><filter id="bad.filter"><feTurbulence/></filter></defs>','NDC_COMPILE_FAILED'),
])
def test_real_compile_keeps_typed_cause_fields(sample,element,extra,code):
    root,lock,scene,original=sample
    svg=root/f'{element}.svg';pos=original.rfind('</');svg.write_text(original[:pos]+extra+original[pos:])
    digest=hashlib.sha256(svg.read_bytes()).hexdigest()
    with pytest.raises(NativeCompileError) as failure:
        compile_svg_deck(NativeCompileRequest(root=root,scenes=[scene],locks={'P001':lock},svg_paths={'P001':svg},expected_sha256={'P001':digest},validate_approved=validate_approved_svg,output_root=root/'failure-output'/element,canvas_mode='native'))
    error=failure.value
    assert error.element_id==element
    assert error.page_id=='P001'
    assert error.input_sha256==digest
    assert error.code==code
    assert error.recovery


@pytest.mark.parametrize('element,extra,code',[
 ('bad.cli.script','<script id="bad.cli.script">alert(1)</script>','NDC_SVG_UNSUPPORTED'),
 ('bad.cli.image','<image id="bad.cli.image" data-pptx-bounds="1,1,10,10" x="1" y="1" width="10" height="10" href="https://example.invalid/a.png"/>','NDC_ASSET_UNREGISTERED'),
])
def test_real_cli_reports_compile_context_and_valid_failed_result(sample,tmp_path,element,extra,code):
    import json
    import shutil
    import subprocess
    import jsonschema
    source,lock,scene,original=sample
    root=tmp_path/source.name;shutil.copytree(source,root)
    svg=svg_path(root,'P001');pos=original.rfind('</')
    svg.write_text(original[:pos]+extra+original[pos:])
    result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'scripts/deck_master.py'),'build','run','--profile','native','--run-dir',str(root)],capture_output=True,text=True)
    assert result.returncode==2,result.stdout+result.stderr
    assert not result.stderr,result.stderr
    payload=json.loads(result.stdout)
    assert payload['status']=='blocked'
    assert payload['code']==code
    assert payload['page_id']=='P001' and payload['element_id']==element
    assert payload['input_sha256']==hashlib.sha256(svg.read_bytes()).hexdigest()
    schema=json.loads((Path(__file__).resolve().parents[1]/'docs/contracts/native-compile-result.v1.schema.json').read_text())
    failed=json.loads((root/'build/native_compile_result.json').read_text())
    jsonschema.Draft202012Validator(schema).validate(failed)
    assert failed['status']=='failed'
    assert failed['errors'][0]['element_id']==element
