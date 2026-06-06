from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from runtime.events import append_event


DEFAULT_PIPELINE = Path("/Users/dingcheng/Coding-Project/02-key-project/PPT-Deck-Pro-Max/scripts/run_deck_pipeline.py")


def build_init_command(
    *,
    pipeline: Path = DEFAULT_PIPELINE,
    project_dir: Path,
    pages: int,
    output_mode: str = "pptx+html",
    production_mode: str = "expert",
) -> list[str]:
    return [
        "python3",
        str(pipeline),
        "init",
        "--project-dir",
        str(project_dir),
        "--pages",
        str(pages),
        "--output-mode",
        output_mode,
        "--production-mode",
        production_mode,
    ]


def run_init_project(run_dir: str | Path, *, pages: int, pipeline: Path = DEFAULT_PIPELINE) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    project_dir = root / "deck_pro_max_project"
    cmd = build_init_command(pipeline=pipeline, project_dir=project_dir, pages=pages)
    append_event(root, "deck_pro_max.init.started", target=" ".join(cmd))
    completed = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=False)
    status = "ok" if completed.returncode == 0 else "error"
    append_event(
        root,
        "deck_pro_max.init.completed",
        status=status,
        target=str(project_dir),
        error="" if completed.returncode == 0 else completed.stderr.strip() or completed.stdout.strip(),
    )
    return {
        "command": cmd,
        "project_dir": str(project_dir),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
