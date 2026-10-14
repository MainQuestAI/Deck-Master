"""Actual method loading and honest channel gaps for RC3's early slice."""

from pathlib import Path
import json

from deck_master import capabilities, cli, method_resources


def test_editable_checkout_uses_canonical_method_even_with_stale_packaged_copy(tmp_path, monkeypatch):
    import deck_master

    repo = tmp_path / "checkout"
    module = repo / "src/deck_master/__init__.py"
    module.parent.mkdir(parents=True)
    module.write_text("")
    (repo / "pyproject.toml").write_text('[project]\nname = "deck-master"\n')
    canonical = repo / "skills/deck-master"
    canonical.mkdir(parents=True)
    (canonical / "SKILL.md").write_text("current source")
    packaged = module.parent / "resources/skill"
    packaged.mkdir(parents=True)
    (packaged / "SKILL.md").write_text("stale copy")
    monkeypatch.setattr(deck_master, "__file__", str(module))
    assert method_resources.resolve_root() == canonical


def test_preproduction_work_order_loads_complete_examples_and_calibration():
    resources = method_resources.method_resources("review", intent="preproduction")
    by_id = {r["id"]: r for r in resources}
    assert {"source-reading", "content-methods", "content-examples", "content-calibration"} <= set(by_id)
    content = Path(by_id["content-calibration"]["path"]).read_text()
    assert all(f"## {i}." in content for i in range(1, 7))
    assert "同一作者换 reviewer.id 不算独立" in content


def test_cli_capabilities_cannot_invent_a_reviewer_or_user_identity(capsys):
    assert cli.main(["capabilities"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "ready"
    assert result["review_channel_status"] == "needs_reviewer"
    assert result["verified_user_events"] is False
    assert result["independent_review_receipts"] is False
    assert result["human_review_receipts"] is False
    assert result["evidence_kinds"] == ["host_attested_instruction"]
    assert capabilities.describe()["method_release"]["methods_sha256"]


def test_cli_reads_installed_method_bytes_with_matching_digest(capsys):
    from deck_master.models import sha256_bytes

    assert cli.main(["methods", "--kind", "review", "--intent", "preproduction", "--read"]) == 0
    result = json.loads(capsys.readouterr().out)
    for item in result["methods"]:
        assert sha256_bytes(item["content"].encode("utf-8")) == item["sha256"]
