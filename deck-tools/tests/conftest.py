import pytest
from hostenv import resolve_host_font


@pytest.fixture
def resolvable_font_family():
    return resolve_host_font()
