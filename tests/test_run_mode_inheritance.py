from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from deck_master import command_next_step, command_run_state  # noqa: E402


def _args(run_dir: Path, run_mode: str | None = None) -> Namespace:
    return Namespace(
        run_dir=str(run_dir),
        run_id=None,
        runs_dir=None,
        workspace="",
        run_mode=run_mode,
        dev_allow_unsetup=True,
    )


def test_state_commands_inherit_fixture_mode_from_request(tmp_path: Path) -> None:
    (tmp_path / "request.json").write_text(
        json.dumps({"run_id": tmp_path.name, "run_mode": "fixture"}),
        encoding="utf-8",
    )

    next_step = command_next_step(_args(tmp_path))
    run_state = command_run_state(_args(tmp_path))

    assert next_step["run_mode"] == "fixture"
    assert run_state["run_mode"] == "fixture"


def test_explicit_run_mode_overrides_request(tmp_path: Path) -> None:
    (tmp_path / "request.json").write_text(
        json.dumps({"run_id": tmp_path.name, "run_mode": "fixture"}),
        encoding="utf-8",
    )

    run_state = command_run_state(_args(tmp_path, "production"))

    assert run_state["run_mode"] == "production"
