import pytest
from hostenv import resolve_host_font
from deck_tools.render import NeedsTool, executable


@pytest.fixture(autouse=True)
def require_render_tools(request):
    if request.node.get_closest_marker('render') is None:
        return
    for tool in ('rsvg-convert', 'soffice', 'pdftoppm', 'fc-match'):
        try:
            executable(tool)
        except NeedsTool as exc:
            pytest.skip(str(exc))


@pytest.fixture
def resolvable_font_family():
    return resolve_host_font()
