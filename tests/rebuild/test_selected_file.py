"""Selected local files are bounded; HTTP cannot select local paths."""
import os
import urllib.error
import urllib.request
import json

import pytest

from deck_master.models import ModelError
from deck_master.store import ConflictError
from deck_master.selected_file import read_selected_file


def test_regular_and_mismatched_lengths(tmp_path):
    path = tmp_path / 'output.pptx'
    path.write_bytes(b'output')
    assert read_selected_file(path, sizes={6})[0] == b'output'
    with pytest.raises(ConflictError):
        read_selected_file(path, sizes={5})


def test_selected_size_conflict_has_machine_code(tmp_path):
    from deck_master.collaboration_api import error_response
    path = tmp_path / 'output.pptx'
    path.write_bytes(b'output')
    with pytest.raises(ConflictError) as caught:
        read_selected_file(path, sizes={5})
    response, status, exit_code = error_response(caught.value)
    assert (status, exit_code) == (409, 5)
    assert response['error']['code'] == 'candidate_not_selected_output'


@pytest.mark.parametrize('kind', ['directory', 'missing', 'symlink', 'fifo'])
def test_nonregular_paths_never_read(tmp_path, kind, monkeypatch):
    path = tmp_path / 'candidate'
    if kind == 'directory':
        path.mkdir()
    elif kind == 'symlink':
        target = tmp_path / 'target'
        target.write_bytes(b'x')
        path.symlink_to(target)
    elif kind == 'fifo':
        os.mkfifo(path)
    monkeypatch.setattr(os, 'read', lambda *args: pytest.fail('nonregular file must not be read'))
    with pytest.raises(ModelError):
        read_selected_file(path, sizes={1})


def test_file_growth_is_bounded(tmp_path, monkeypatch):
    path = tmp_path / 'candidate'
    path.write_bytes(b'x')
    original = os.read
    calls = []
    def growing(fd, count):
        calls.append(count)
        data = original(fd, count)
        if len(calls) == 1:
            with path.open('ab') as output:
                output.write(b'y' * 100)
        return data
    monkeypatch.setattr(os, 'read', growing)
    with pytest.raises(ConflictError):
        read_selected_file(path, sizes={1})
    assert calls == [1, 1]


def test_http_path_rejected_before_delivery_dispatch(tmp_path, monkeypatch):
    from deck_master.samples import create_gallery_sample
    from deck_master.web import WorkbenchServer
    from deck_master import delivery_eligibility
    from deck_master.store import Store
    project = tmp_path / 'project'
    create_gallery_sample(project, page_count=24)
    ident = Store(project).load_document()['project_id']
    monkeypatch.setattr(delivery_eligibility, 'describe', lambda *a, **k: pytest.fail('must reject before delivery/file access'))
    server = WorkbenchServer(project)
    try:
        url = server.start().rstrip('/') + f'/api/projects/{ident}/delivery-eligibility?file_path=/private/nonexistent'
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(url)
        assert caught.value.code == 400
        assert json.load(caught.value)['error']['path'] == 'file_path'
    finally:
        server.stop()


def test_permission_error_is_structured(tmp_path, monkeypatch):
    from deck_master.collaboration_api import error_response
    def denied(*args, **kwargs):
        raise PermissionError('synthetic denied')
    monkeypatch.setattr(os, 'open', denied)
    with pytest.raises(ModelError) as caught:
        read_selected_file(tmp_path / 'candidate', sizes={1})
    response, status, exit_code = error_response(caught.value)
    assert (status, exit_code) == (400, 2)
    assert response['error']['code'] == 'selected_file_unreadable'


def test_path_replacement_detected(tmp_path, monkeypatch):
    path = tmp_path / 'candidate'
    path.write_bytes(b'x')
    original = os.read
    def replacing(fd, count):
        data = original(fd, count)
        replacement = tmp_path / 'new'
        replacement.write_bytes(b'x')
        replacement.replace(path)
        return data
    monkeypatch.setattr(os, 'read', replacing)
    with pytest.raises(ConflictError, match='file changed'):
        read_selected_file(path, sizes={1})
