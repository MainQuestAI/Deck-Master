"""Default doctor checks: rsvg-convert blocks, an omitted font list only warns."""

from deck_tools import doctor
from deck_tools.render import NeedsTool, RendererError
from types import SimpleNamespace
import pytest


@pytest.fixture(autouse=True)
def native_tools(monkeypatch):
    monkeypatch.setattr(doctor, "run", lambda args, **kwargs: SimpleNamespace(stdout=b"v22.0.0\n"))


def test_missing_rsvg_convert_blocks_and_names_the_install(monkeypatch):
    def fake_executable(name):
        if name == "rsvg-convert":
            raise NeedsTool("rsvg-convert unavailable")
        return f"/usr/bin/{name}"

    monkeypatch.setattr(doctor, "executable", fake_executable)
    monkeypatch.setattr(doctor, "renderer_environment", lambda: None)
    result = doctor.diagnose([])
    assert result["status"] == "needs_tool"
    rsvg = next(item for item in result["checks"] if item["name"] == "rsvg-convert")
    assert rsvg["available"] is False
    assert "brew install librsvg" in rsvg["detail"]
    assert "librsvg2-bin" in rsvg["detail"]


def test_omitted_fonts_warn_without_failing_a_ready_toolchain(monkeypatch):
    monkeypatch.setattr(doctor, "executable", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(doctor, "renderer_environment", lambda: None)
    result = doctor.diagnose([])
    assert result["status"] == "ready"
    hint = next(item for item in result["checks"] if item["name"] == "fonts")
    assert hint["level"] == "warn"
    assert hint["available"] is False
    assert "deck doctor --fonts" in hint["detail"]
    assert "fc-list" in hint["detail"]


def test_named_missing_font_still_blocks(monkeypatch):
    monkeypatch.setattr(doctor, "executable", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(doctor, "renderer_environment", lambda: None)

    def missing(_pages):
        raise NeedsTool("font Missing unavailable; explicitly choose an installed font")

    monkeypatch.setattr(doctor, "resolve_fonts", missing)
    result = doctor.diagnose(["Missing"])
    assert result["status"] == "needs_tool"
    font = next(item for item in result["checks"] if item["name"] == "Missing")
    assert font["available"] is False
    assert font.get("level") != "warn"
    assert not any(item["name"] == "fonts" for item in result["checks"])


@pytest.mark.parametrize("failure", ["old_node", "missing_node", "missing_package"])
def test_native_dependencies_block_when_unavailable(monkeypatch, failure):
    monkeypatch.setattr(doctor, "renderer_environment", lambda: None)
    def executable(name):
        if failure == "missing_node" and name == "node":
            raise NeedsTool("缺少 node")
        return f"/usr/bin/{name}"
    def run(args, **kwargs):
        if args[-1] == "--version":
            return SimpleNamespace(stdout=b"v16.0.0" if failure == "old_node" else b"v22.0.0")
        if failure == "missing_package":
            raise RendererError("缺少 pptxgenjs")
        return SimpleNamespace(stdout=b"")
    monkeypatch.setattr(doctor, "executable", executable)
    monkeypatch.setattr(doctor, "run", run)
    result = doctor.diagnose([])
    assert result["status"] == "needs_tool"
    name = "pptxgenjs" if failure == "missing_package" else "node"
    assert next(c for c in result["checks"] if c["name"] == name)["available"] is False
