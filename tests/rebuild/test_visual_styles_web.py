"""HTTP/CLI boundaries, synthetic screenshots; no actual visual acceptance."""
import json
import uuid
import urllib.request
import urllib.error

from test_styles import flow  # noqa: F401
from test_visual_styles import image_bytes
from deck_master.web import WorkbenchServer
from deck_master.cli import main


def request(url, data=None, headers=None):
    req=urllib.request.Request(url,data=data,headers=headers or {})
    try:
        with urllib.request.urlopen(req,timeout=10) as res:return res.status,json.loads(res.read())
    except urllib.error.HTTPError as err:return err.code,json.loads(err.read())


def test_binary_upload_uses_token_and_separate_limit_with_receipt_replay(flow):
    server=WorkbenchServer(flow.project);url=server.start().rstrip('/')
    try:
        token=request(url+'/api/session')[1]['token'];before=flow.store.read_current()
        path='/api/styles/references/import?'+urllib.parse.urlencode({'base_revision':flow.store.current_revision_id(),'operation_id':str(uuid.uuid4())})
        assert request(url+path,image_bytes())[0]==403
        assert flow.store.read_current()==before
        headers={'X-Deck-Token':token,'Origin':url,'Content-Type':'image/png'}
        status,out=request(url+path,image_bytes(),headers);assert status==200
        status,replay=request(url+path,image_bytes(),headers);assert status==200 and replay['operation_result']==out['operation_result']
        row=request(url+'/api/styles/references')[1];assert len(row['references'])==1 and row['fonts']
        id=row['references'][0]['reference']['reference_id']
        body={'reference_ids':[id],'instruction':'Inspect visual hierarchy','base_revision':flow.store.current_revision_id(),'operation_id':str(uuid.uuid4())}
        status,analyzed=request(url+'/api/styles/analyze',json.dumps(body).encode(),headers);assert status==200 and analyzed['operation_result']['max_calls']==0
        assert request(url+'/api/history?limit=bad')[0]>=400
        assert request(url+'/api/history?limit=2&limit=4')[0]>=400
        assert request(url+'/api/history?related_only=invalid')[0]>=400
        assert request(url+'/api/health')[0]==200
    finally:server.stop()


def test_cli_import_list_show_and_analysis(flow,tmp_path,capsys):
    file=tmp_path/'ref.png';file.write_bytes(image_bytes());base=flow.store.current_revision_id()
    assert main(['styles','references','import','--project',str(flow.project),'--file',str(file),'--base-revision',base,'--operation-id',str(uuid.uuid4()),'--json'])==0
    output=json.loads(capsys.readouterr().out);rid=output['operation_result']['reference_id']
    assert main(['styles','references','show','--project',str(flow.project),'--reference-id',rid,'--json'])==0
    assert len(json.loads(capsys.readouterr().out)['references'])==1
    args=tmp_path/'analyze.json';args.write_text(json.dumps({'reference_ids':[rid],'instruction':'Inspect screenshot'}))
    assert main(['styles','analyze','--project',str(flow.project),'--input',str(args),'--base-revision',flow.store.current_revision_id(),'--operation-id',str(uuid.uuid4()),'--json'])==0
    assert json.loads(capsys.readouterr().out)['operation_result']['max_calls']==0


def test_binary_upload_rejects_real_byte_and_pixel_limits_without_publishing(flow):
    """Actual HTTP limits, valid over-pixel PNG; reject before state publication."""
    import http.client
    import io
    from PIL import Image
    from deck_master import visual_styles
    server = WorkbenchServer(flow.project); url = server.start().rstrip('/')
    before = flow.store.read_current()
    try:
        token = request(url + '/api/session')[1]['token']
        headers = {'X-Deck-Token': token, 'Origin': url, 'Content-Type': 'image/png'}
        def path():
            return '/api/styles/references/import?' + urllib.parse.urlencode({
                'base_revision': flow.store.current_revision_id(), 'operation_id': str(uuid.uuid4())})
        endpoint = urllib.parse.urlparse(url)
        connection = http.client.HTTPConnection(endpoint.hostname, endpoint.port, timeout=5)
        try:
            # Sending headers alone must produce rejection, not block waiting for 64 MiB.
            connection.request('POST', path(), body=b'', headers={**headers,
                'Content-Length': str(64 * 1024 * 1024 + 1)})
            response = connection.getresponse(); rejected = json.loads(response.read())
            assert response.status == 422
            assert '64 MiB' in rejected['error']['message']
        finally: connection.close()
        assert flow.store.read_current() == before

        image = Image.new('RGB', (8000, 4001), 'white')
        assert image.width * image.height > 32_000_000
        stream = io.BytesIO(); image.save(stream, format='PNG'); image.close()
        data = stream.getvalue(); assert len(data) < visual_styles.MAX_BYTES
        status, rejected = request(url + path(), data, headers)
        assert status == 422
        assert '32 million pixels' in rejected['error']['message']
        assert flow.store.read_current() == before
        assert request(url + '/api/styles/references')[1]['references'] == []
    finally: server.stop()
