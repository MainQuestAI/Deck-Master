"""RC3-04/early: actual bytes/installation and actual task dispatch identities."""
import json
from pathlib import Path

import pytest

from deck_master import capabilities, cli, method_resources, service
from deck_master.errors import MethodResourceMissing
from deck_master.models import sha256_bytes
from deck_master.store import Store


def _checkout(tmp_path, monkeypatch):
    import deck_master
    repo = tmp_path / "source"
    module = repo / "src/deck_master/__init__.py"
    module.parent.mkdir(parents=True)
    module.write_text("")
    (repo / "pyproject.toml").write_text('[project]\nname="deck-master"\n')
    canonical = repo / "skills/deck-master"
    canonical.mkdir(parents=True)
    (canonical / "SKILL.md").write_text("canonical")
    packaged = module.parent / "resources/skill"
    packaged.mkdir(parents=True)
    (packaged / "SKILL.md").write_text("stale packaged")
    monkeypatch.setattr(deck_master, "__file__", str(module))
    return canonical, packaged


def test_canonical_first_and_crlf_bytes_are_not_normalized(tmp_path, monkeypatch):
    canonical, packaged = _checkout(tmp_path, monkeypatch)
    raw = "first\r\n第二行\r\n".encode()
    for method_id in method_resources.method_ids_for("compose"):
        relative = method_resources.RELATIVE_PATHS[method_id]
        (canonical / relative).parent.mkdir(exist_ok=True)
        (canonical / relative).write_bytes(raw)
        (packaged / relative).parent.mkdir(exist_ok=True)
        (packaged / relative).write_text("stale")
    items = method_resources.read_methods("compose")
    assert all(item["content"].encode() == raw and item["sha256"] == sha256_bytes(raw) for item in items)
    assert all(Path(item["path"]).is_relative_to(canonical) for item in items)
    (canonical / "SKILL.md").unlink()
    with pytest.raises(MethodResourceMissing, match="do not borrow"):
        method_resources.resolve_root()


def test_missing_declared_method_never_borrows_another_installation(tmp_path, monkeypatch):
    canonical, _ = _checkout(tmp_path, monkeypatch)
    with pytest.raises(MethodResourceMissing, match="declared method file is missing"):
        method_resources.read_methods("review", intent="preproduction")
    assert method_resources.resolve_root() == canonical


def test_non_checkout_package_does_not_borrow_cwd(tmp_path, monkeypatch):
    import deck_master
    import importlib.resources
    root = tmp_path / "site-packages/deck_master"
    packaged = root / "resources/skill"
    packaged.mkdir(parents=True)
    (packaged / "SKILL.md").write_text("installed")
    monkeypatch.setattr(deck_master, "__file__", str(root / "__init__.py"))
    monkeypatch.setattr(importlib.resources, "files", lambda _: root)
    monkeypatch.chdir(tmp_path)
    assert method_resources.resolve_root() == packaged
    (packaged / "SKILL.md").unlink()
    with pytest.raises(MethodResourceMissing):
        method_resources.resolve_root()


def test_real_host_work_order_method_read_and_basis_changed(tmp_path, capsys, monkeypatch):
    project = tmp_path / "project"
    service.create(project, brief="real method consumption", sources=[])
    store = Store(project)
    document = store.load_document()
    task = store.read_object_json(document["tasks"][0])
    before_current = (store.project_root / ".deckmaster/current.json").read_bytes()
    result = method_resources.read_task_methods(project, task["task_id"])
    assert result["status"] == "current"
    assert result["work_order"]["method_release"] == result["current_method_release"]
    for item in result["methods"]:
        assert sha256_bytes(item["content"].encode()) == item["sha256"]
    root = tmp_path / "different-method-version"
    root.mkdir()
    for item in result["methods"]:
        target = root / item["relative_path"]
        target.parent.mkdir(exist_ok=True)
        target.write_text(item["content"] + "\nchanged method\n")
    monkeypatch.setattr(method_resources, "resolve_root", lambda: root)
    assert cli.main(["methods", "--project", str(project), "--task-id", task["task_id"]]) == 0
    changed = json.loads(capsys.readouterr().out)
    assert changed["status"] == "basis_changed"
    assert changed["dispatch_method_release"] == result["dispatch_method_release"]
    assert changed["current_method_release"] != changed["dispatch_method_release"]
    assert (store.project_root / ".deckmaster/current.json").read_bytes() == before_current


def test_preproduction_methods_and_default_capabilities(capsys):
    assert method_resources.method_ids_for("review", intent="preproduction") == (
        "source-reading", "content-methods", "content-examples", "content-calibration", "review-and-repair")
    assert cli.main(["capabilities"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["review_channel_status"] == "needs_reviewer"
    assert all(payload[key] is False for key in ("verified_user_events", "independent_review_receipts", "human_review_receipts"))
    assert payload["providers"] == []
    assert capabilities.describe()["method_release"]["methods_sha256"]
