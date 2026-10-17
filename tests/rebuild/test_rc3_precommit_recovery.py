"""S03 mechanical tests, with explicitly synthetic legacy-sequence fixtures.

Only installation admission is bypassed. The fixture invokes this Runtime's
real reader/immutable Store writes/model validator in the old create order;
it is not a claim that the current atomic create leaves orphans. The separate
own-managed A0 trace uses actual service.create with no installation seam.
"""
import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "tools/rc3_campaign/precommit_recovery.py"
spec = importlib.util.spec_from_file_location("rc3_s03_test", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
s, c = m.s, m.c


def setup(tmp_path, monkeypatch):
    import deck_master
    from deck_master import service
    from deck_master.sources import read_source_snapshot
    from deck_master.store import Store
    monkeypatch.setattr(c, "installation", lambda *_a, **_k: {"SYNTHETIC_INSTALLATION_ADMISSION_SEAM": True})
    instruction = c.write_once(tmp_path / "instruction.txt", b"SYNTHETIC NONHUMAN ENGINEERING: six neutral reading pages, no speech.")
    sources = [c.write_once(tmp_path / f"source-{i}.txt", f"Synthetic neutral source {i}.\n".encode()) for i in (1, 2)]
    technical = c.save(tmp_path / "technical.json", {"SYNTHETIC_ENGINEERING_ONLY": True})
    exposure = c.save(tmp_path / "exposure.json", {"status": "FROZEN", "excluded_identities": ["/engineering/preparer"]})
    installation = {"python": sys.executable, "module_file": deck_master.__file__, "source_sha": "synthetic-source-env",
        "source_tree": "synthetic", "manifest": technical, "wheel_sha256": "synthetic"}
    row = {"profile": "q3q4", "case": "Q3", "checkpoint": "Q3", "matrix_slot": "05", "whole_run_id": "synthetic-s03",
        "repetition": 1, "arm": "A0", "scope_slot": "flow-05--original-missing-template", "project": str(tmp_path / "project"),
        "project_mode": "new", "page_ids": [], "instruction": instruction, "materials": sources, "technical_supplements": [],
        "limits": {"writer": 2, "review": 2, "sdk": 12, "render": 0},
        "native_limits": {role: 0 for role in s.ROLES}}
    config = {"format": s.FORMAT, "status": s.ENGINEERING, "recorder_sha256": c.digest(s.SOURCE.with_name("supplementary_recorder.py").read_bytes()),
        "ledger_root": str(tmp_path / "campaign"), "common": c.reference(s.SOURCE), "protocol": technical,
        "policy_epoch": technical, "admission_review": technical, "grammar": technical, "exposure_registry": exposure,
        "installations": {"A0": installation}, "scopes": {"q3-original": row}}
    c.save(tmp_path / "config.json", config)
    s.freeze(tmp_path / "config.json", tmp_path / "campaign")
    state = s.init(tmp_path / "campaign", tmp_path / "run", "q3-original")
    args = {"project_dir": state["project"], "brief": Path(instruction["path"]).read_text(),
        "sources": [ref["path"] for ref in sources], "presentation_mode": "read", "page_limit": 6}

    def synthetic_legacy_order():
        store = Store(state["project"])
        store.ensure_layout()
        entries = []
        for i, source in enumerate(sources):
            extract, raw = read_source_snapshot(source["path"])
            entries.append(service._entry_from_extract(store, Path(source["path"]), extract, f"synthetic-{i}", data=raw))
        # Explicit fixture seam reproducing the legacy ordering, not a native
        # operation or the current atomic service.create implementation.
        return service.new_document(project_id="synthetic-s03", task={"title": "Synthetic", "brief": args["brief"],
            "audience": "", "scenario": "", "presentation_mode": "read", "presentation_mode_source": "provided",
            "page_limit": 6, "existing_decisions": []}, design_context={}, sources=entries, operation_id="synthetic-create")

    with pytest.raises(Exception, match="presentation_mode"):
        with s.resource_session(state["root"]) as (journal, _, _):
            s.perform(journal, "service.create", args, synthetic_legacy_order)
    return Path(state["root"]), state, config


def admission(tmp_path, root):
    journal, state, config = s.load(root)
    key = next(iter(journal.unfinished()))
    intent = next(e for e in journal.events() if e["kind"] == "sdk_intent" and e["data"]["operation_key"] == key)
    failure = next(e for e in journal.events() if e["kind"] == "sdk_error" and e["data"]["operation_key"] == key)
    value = {"format": m.FORMAT, "action": m.ACTION, "status": s.ENGINEERING,
        "observer_id": "/engineering/rc3-s03", "assurance": "synthetic_engineering",
        "tool": c.reference(SCRIPT), "scoped_recorder": c.reference(m.SOURCE), "common": c.reference(s.SOURCE),
        "registration": c.reference(Path(state["campaign"]) / "registration.json"), "run_manifest": c.reference(root / "run.json"),
        **{k: state[k] for k in ("root", "slot", "project", "arm", "scope_slot", "whole_run_id")},
        "installation": {k: config["installations"][state["arm"]][k] for k in
            ("python", "module_file", "source_sha", "source_tree", "manifest", "wheel_sha256")},
        "operation_key": key, "intent": m.event_ref(journal, intent), "failure": m.event_ref(journal, failure),
        "create_arguments_sha256": c.digest(c.encoded(intent["data"]["arguments"])),
        "enum_mapping": {"field": "presentation_mode", "original": "read", "public": "read_alone"}}
    return c.save(tmp_path / "admission.json", value)


def objects(state):
    return {p.relative_to(state["project"]).as_posix(): p.read_bytes()
            for p in (Path(state["project"]) / ".deckmaster/objects").rglob("*") if p.is_file()}


def invoke(root, ref, out, *, reconcile=True):
    return m.recover(root, ref["path"], ref["sha256"], out, reconcile=reconcile)


def test_diagnosis_then_normal_reconciliation_preserves_original_and_costs(tmp_path, monkeypatch):
    root, state, _ = setup(tmp_path, monkeypatch)
    original = objects(state)
    original_events = c.Journal(root).events()
    ref = admission(tmp_path, root)
    assert invoke(root, ref, tmp_path / "diagnosis", reconcile=False)["reconciliation_performed"] is False
    assert len(c.Journal(root).unfinished()) == 1
    result = invoke(root, ref, tmp_path / "reconciliation")
    assert result["status"] == "recorded_no_retry" and not c.Journal(root).unfinished()
    assert result["mapped_arguments_for_separate_explicit_call_only"]["presentation_mode"] == "read_alone"
    assert objects(state) == original and len(original) == 4
    assert c.Journal(root).events()[:len(original_events)] == original_events
    assert not (Path(state["project"]) / ".deckmaster/current.json").exists()
    assert s.Resources(state).totals()[0]["sdk"] == 3  # original failure + two real public queries
    record = c.read(result["record"]["path"])
    assert record["actual_public_operation_id"] is None and len(record["runtime_observations"]) == 5
    assert c.Journal(root).events()[-1]["kind"] == "render_accounted"
    with pytest.raises(m.Error, match="one unresolved"):
        invoke(root, ref, tmp_path / "already-settled")


@pytest.mark.parametrize("fault", ["current.json", "operations/receipt.json", "revisions/revision.json", "objects/aa/foreign-task.json", "extra.txt"])
def test_any_commit_task_receipt_or_unknown_file_keeps_original_pending(tmp_path, monkeypatch, fault):
    root, state, _ = setup(tmp_path, monkeypatch)
    ref = admission(tmp_path, root)
    p = Path(state["project"]) / ".deckmaster" / fault
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"unknown_or_committed_or_Task":true}')
    before = p.read_bytes()
    with pytest.raises(m.Error):
        invoke(root, ref, tmp_path / "refused")
    assert c.Journal(root).unfinished() and p.read_bytes() == before
    assert s.Resources(state).totals()[0]["sdk"] == 1  # refused before query


@pytest.mark.parametrize("fault", ["admission-hash", "tool", "wrong-project", "wrong-runtime", "wrong-failure", "fake-root", "argument-digest", "enum-mapping"])
def test_exact_prospective_identity_failure_and_mapping_are_required(tmp_path, monkeypatch, fault):
    root, state, _ = setup(tmp_path, monkeypatch)
    ref = admission(tmp_path, root)
    if fault != "admission-hash":
        value = c.read(ref["path"])
        if fault == "tool": value["tool"] = c.reference(m.SOURCE)
        if fault == "wrong-project": value["project"] += "-other"
        if fault == "wrong-runtime": value["installation"]["python"] += "-other"
        if fault == "wrong-failure": value["failure"] = value["intent"]
        if fault == "fake-root": value["observer_id"] = "/root"
        if fault == "argument-digest": value["create_arguments_sha256"] = "0" * 64
        if fault == "enum-mapping": value["enum_mapping"]["public"] = "mixed"
        ref = c.save(tmp_path / "wrong-admission.json", value)
    else:
        ref = {**ref, "sha256": "0" * 64}
    with pytest.raises(m.Error):
        invoke(root, ref, tmp_path / "refused")
    assert c.Journal(root).unfinished() and s.Resources(state).totals()[0]["sdk"] == 1


@pytest.mark.parametrize("fault", ["source-changed", "orphan-changed", "orphan-missing", "symlink", "hardlink"])
def test_source_and_orphan_integrity_are_not_caller_proof(tmp_path, monkeypatch, fault):
    root, state, _ = setup(tmp_path, monkeypatch)
    ref = admission(tmp_path, root)
    p = next(p for p in (Path(state["project"]) / ".deckmaster/objects").rglob("*.txt"))
    if fault == "source-changed": Path(state["materials"][0]["path"]).write_text("changed")
    if fault == "orphan-changed": p.write_text("changed")
    if fault == "orphan-missing": p.unlink()
    if fault == "symlink":
        raw = p.read_bytes(); p.unlink(); target = tmp_path / "outside.txt"; target.write_bytes(raw); p.symlink_to(target)
    if fault == "hardlink": (tmp_path / "alias.txt").hardlink_to(p)
    with pytest.raises(m.Error):
        invoke(root, ref, tmp_path / "refused")
    assert c.Journal(root).unfinished()


@pytest.mark.parametrize("reply", ["unknown-error", "inputs-exist", "metadata-race", "lock-replaced", "late-metadata-race"])
def test_real_query_failure_and_mutation_never_settle_pending(tmp_path, monkeypatch, reply):
    root, state, _ = setup(tmp_path, monkeypatch)
    ref = admission(tmp_path, root)
    from deck_master import service
    original = service.inputs_show
    if reply == "late-metadata-race":
        real_bind = m.bind
        count = 0
        def rebind(*args):
            nonlocal count
            result = real_bind(*args); count += 1
            if count == 2: (Path(state["project"]) / ".deckmaster/revisions/late.json").write_text("{}")
            return result
        monkeypatch.setattr(m, "bind", rebind)
    else:
        def observed(project):
            # Explicit synthetic boundary seam: never native proof.
            if reply == "unknown-error": raise OSError("synthetic unavailable")
            if reply == "inputs-exist": return {"status": "ok", "synthetic_current": True}
            if reply == "metadata-race": (Path(project) / ".deckmaster/revisions/late.json").write_text("{}")
            if reply == "lock-replaced":
                lock = Path(project) / ".deckmaster/write.lock"; lock.unlink(); lock.touch()
            return original(project)
        monkeypatch.setattr(service, "inputs_show", observed)
    with pytest.raises(m.Error):
        invoke(root, ref, tmp_path / "refused")
    assert c.Journal(root).unfinished()
    assert s.Resources(state).totals()[0]["sdk"] == 2  # actual attempted query is never refunded
    assert not any(e["kind"] == "sdk_reconciliation" for e in c.Journal(root).events())


def test_current_atomic_public_create_leaves_no_source_orphan_evidence(tmp_path, monkeypatch):
    """Real current Runtime create, not the synthetic legacy fixture above."""
    root, state, _ = setup(tmp_path, monkeypatch)
    from deck_master import service
    other = tmp_path / "atomic-new"
    with pytest.raises(Exception, match="presentation_mode"):
        service.create(other, brief="Synthetic atomic enum check", sources=[state["materials"][0]["path"]],
                       presentation_mode="read", page_limit=6)
    assert not other.exists()
    assert c.Journal(root).unfinished()


def test_runtime_installation_is_verified_before_absence_evidence(tmp_path, monkeypatch):
    root, state, _ = setup(tmp_path, monkeypatch)
    ref = admission(tmp_path, root)
    def wrong(*_a, **_k): raise m.Error("wrong installation interpreter")
    monkeypatch.setattr(c, "installation", wrong)
    with pytest.raises(m.Error, match="wrong installation"):
        invoke(root, ref, tmp_path / "refused")
    assert c.Journal(root).unfinished() and s.Resources(state).totals()[0]["sdk"] == 1


def test_exhausted_shared_sdk_pool_does_not_query_or_erase_failed_call(tmp_path, monkeypatch):
    root, state, _ = setup(tmp_path, monkeypatch)
    ref = admission(tmp_path, root)
    resources = s.Resources(state)
    resources.charge("sdk", 11, "SYNTHETIC_PRIOR_SAME_POOL_COST")
    with pytest.raises(m.Error, match="cap exhausted"):
        invoke(root, ref, tmp_path / "refused")
    assert resources.totals()[0]["sdk"] == 12 and c.Journal(root).unfinished()
    assert not any(e["kind"] == "precommit_absence_query_intent" for e in c.Journal(root).events())
