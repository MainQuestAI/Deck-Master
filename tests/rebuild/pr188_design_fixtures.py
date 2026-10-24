import pytest


@pytest.fixture(scope='module')
def manuscript_url(tmp_path_factory):
    from rc3_fixtures import public_project
    from test_rc3_studio_control_browser import manuscript_page
    from deck_master.web import WorkbenchServer
    handle = public_project(tmp_path_factory.mktemp('design-reading'),
        create_input={'brief': '核对范围后继续制作', 'title': '阅读布局验证'},
        manuscript={'pages': [manuscript_page(f'p{i:02}', '先核对范围，再决定行动') for i in range(1, 31)]})
    server = WorkbenchServer(handle['project'])
    try:
        yield server.start()
    finally:
        server.stop()
