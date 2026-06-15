from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from runtime.events import append_event


DEFAULT_PIPELINE = "run_deck_pipeline.py"


def build_init_command(
    *,
    pipeline: str = DEFAULT_PIPELINE,
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


def build_generate_command(
    *,
    command: str,
    run_dir: Path,
    tasks_dir: str = "generation_tasks",
    output_dir: str = "generation_results",
) -> list[str]:
    return [
        command,
        "generate",
        "--task-dir",
        str(run_dir / tasks_dir),
        "--output-dir",
        str(run_dir / output_dir),
    ]


def run_init_project(
    run_dir: str | Path,
    *,
    pages: int,
    pipeline: str = DEFAULT_PIPELINE,
) -> dict[str, Any]:
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


def run_generate_project(
    run_dir: str | Path,
    *,
    command: str,
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    cmd = build_generate_command(command=command, run_dir=root)
    append_event(root, "deck_pro_max.generate.started", target=" ".join(cmd))
    completed = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=False)
    status = "ok" if completed.returncode == 0 else "error"
    append_event(
        root,
        "deck_pro_max.generate.completed",
        status=status,
        error="" if completed.returncode == 0 else completed.stderr.strip() or completed.stdout.strip(),
    )
    return {
        "command": cmd,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
