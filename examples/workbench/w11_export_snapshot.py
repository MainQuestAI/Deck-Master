"""Export a supplied project without changing its Document; recover only in --out.

No model call or fabricated review. A blocked delivery is recorded as blocked.
The input project may be an explicitly synthetic fixture or a real project;
this script never upgrades its existing quality evidence.
"""

from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

from deck_master.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)

    def cli(label, *command, allowed=(0,)):
        result = subprocess.run([sys.executable, "-m", "deck_master", *map(str, command)], capture_output=True, text=True)
        (out / (label + "-process.json")).write_text(
            json.dumps({"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}, ensure_ascii=False, indent=2)
            + "\n"
        )
        if result.returncode not in allowed:
            raise RuntimeError(label + " failed; inspect its process record")
        return result.returncode, json.loads(result.stdout or result.stderr)

    _, history = cli("history", "history", "list", "--project", args.project)
    revision = history["current"]
    original = Store(args.project).load_document()
    checks = {}
    results = {}
    for purpose in ("review", "delivery", "engineering"):
        code, result = cli(
            purpose,
            "export",
            "--project",
            args.project,
            "--revision",
            revision,
            "--purpose",
            purpose,
            "--out",
            out / purpose,
            allowed=(0, 3),
        )
        results[purpose] = result
        if code:
            assert purpose == "delivery" and result["error"]["code"] in (
                "delivery_blocked",
                "input_reconciliation_pending",
                "export_privacy_blocked",
            )
            checks["delivery_refusal_is_explicit"] = True
            continue
        assert result["revision_id"] == revision
        for item in result["manifest"]["files"]:
            raw = (out / purpose / item["path"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == item["sha256"] and len(raw) == item["size"]
        checks[purpose + "_manifest_verified"] = True
    recovered = out / "engineering" / "project"
    assert Store(recovered).load_document() == original
    _, plan = cli("restore-plan", "history", "plan-restore", "--project", recovered, "--revision", revision, "--base-revision", revision)
    _, commit = cli(
        "restore",
        "history",
        "commit-restore",
        "--project",
        recovered,
        "--plan-id",
        plan["plan_id"],
        "--base-revision",
        revision,
        "--operation-id",
        str(uuid.uuid4()),
    )
    assert commit["operation_result"]["restored_from"] == revision
    checks["engineering_restored_in_isolation"] = True
    checks["source_document_unchanged"] = Store(args.project).load_document() == original
    report = {
        "checks": checks,
        "revision_id": revision,
        "model_calls": 0,
        "evidence": "file/CLI verification only; existing project quality is unchanged",
        "purposes": {k: ({"export_id": v["export_id"]} if "export_id" in v else v) for k, v in results.items()},
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
