"""T05 install/package boundary tests (AC-I06 early proof).

Builds a real wheel of the src-layout package and verifies the installed
resources are complete: five schemas, static workbench assets, and the
synced Skill method references. Nothing may be read from the source
checkout at runtime (T16/T20 close the full isolated install).
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_build_hook_syncs_skill_references() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "build_hook.py")],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
    )
    assert b"synced" in result.stdout
    target = REPO / "src" / "deck_master" / "resources" / "skills-references"
    synced = {path.name for path in target.glob("*.md")}
    assert "source-reading.md" in synced
    assert "content-methods.md" in synced


def _ensure_pip() -> None:
    """uv-created venvs ship without pip; bootstrap it so wheel building works."""
    try:
        import pip  # noqa: F401

        return
    except ImportError:
        subprocess.run(
            [sys.executable, "-m", "ensurepip", "--upgrade"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300,
        )


def test_wheel_carries_schema_static_and_methods(tmp_path: Path) -> None:
    subprocess.run(
        [sys.executable, str(REPO / "tools" / "build_hook.py")],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
    )
    _ensure_pip()
    wheel_dir = tmp_path / "wheelhouse"
    result = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-w", str(wheel_dir), str(REPO)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")[-2000:]
    wheels = list(wheel_dir.glob("deck_master-*.whl"))
    assert wheels, "wheel must be produced"
    names = set()
    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())
    for schema in ("document.v1.schema.json", "page.v2.schema.json", "artifact.v1.schema.json", "task.v1.schema.json", "review.v1.schema.json"):
        assert f"deck_master/resources/contracts/{schema}" in names, f"missing schema in wheel: {schema}"
    for static in ("index.html", "app.js", "style.css"):
        assert f"deck_master/resources/static/{static}" in names, f"missing static in wheel: {static}"
    assert "deck_master/resources/skills-references/source-reading.md" in names
    assert "deck_master/resources/skills-references/content-methods.md" in names


def test_resources_resolve_through_importlib() -> None:
    """Schemas and static files load from package resources, not the checkout."""
    import json
    from importlib import resources

    schema_text = resources.files("deck_master").joinpath("resources/contracts/page.v2.schema.json").read_text("utf-8")
    schema = json.loads(schema_text)
    assert schema["required"] == ["schema_version", "page_id", "customer_visible", "visual_spec"]
