"""Default doctor checks: rsvg-convert blocks, an omitted font list only warns."""

from deck_tools import doctor
from deck_tools.render import NeedsTool


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
    names = {item["name"] for item in result["checks"]}
    assert "node" not in names
    assert "pptxgenjs" not in names
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


def test_macos_homebrew_fontconfig_fallback_and_brew_hint(monkeypatch, tmp_path):
    from deck_tools import render

    fake_conf_dir = tmp_path / "homebrew" / "etc" / "fonts"
    fake_conf_dir.mkdir(parents=True)
    fake_conf = fake_conf_dir / "fonts.conf"
    fake_conf.write_text("<fontconfig/>", encoding="utf-8")

    monkeypatch.setattr(render.sys, "platform", "darwin")
    monkeypatch.setattr(doctor.sys, "platform", "darwin")
    monkeypatch.delenv("FONTCONFIG_FILE", raising=False)
    monkeypatch.delenv("FONTCONFIG_PATH", raising=False)
    monkeypatch.setattr(render, "HOMEBREW_FONTCONFIG_CANDIDATES", (fake_conf,))

    def missing_conflist(name):
        if name == "fc-conflist":
            raise NeedsTool("fc-conflist unavailable")
        return f"/opt/homebrew/bin/{name}"

    monkeypatch.setattr(render, "executable", missing_conflist)
    env = render.renderer_environment()
    assert env is not None
    assert env["FONTCONFIG_FILE"] == str(fake_conf)

    # Doctor reports macos_brew_hint when any render tool is missing on macOS.
    def missing_soffice(name):
        if name == "soffice":
            raise NeedsTool("soffice unavailable")
        return f"/opt/homebrew/bin/{name}"

    monkeypatch.setattr(doctor, "executable", missing_soffice)
    monkeypatch.setattr(doctor, "renderer_environment", lambda: env)
    result = doctor.diagnose([])
    assert result["status"] == "needs_tool"
    assert "brew install librsvg poppler fontconfig" in result["macos_brew_hint"]
    fc_check = next(item for item in result["checks"] if item["name"] == "renderer_fontconfig")
    assert fc_check["available"] is True
    assert fc_check["path"] == str(fake_conf)
