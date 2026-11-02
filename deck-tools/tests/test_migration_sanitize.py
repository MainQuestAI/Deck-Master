import json
import subprocess
import sys

import pytest

from legacy_pptx_fixture import PRIVATE_PATH, inspect_pptx, make_pptx


def clean(tmp_path, source, name, **options):
    output = tmp_path / name
    job = tmp_path / (name + ".json")
    job.write_text(json.dumps({"path": str(source), "output": str(output), **options}))
    result = subprocess.run([sys.executable, "-m", "deck_tools", "sanitize", str(job)],
                            capture_output=True, text=True)
    return result, output


def test_migration_cleanup_preserves_historical_notes_and_unnamed_slides(tmp_path):
    source = tmp_path / "old.pptx"
    make_pptx(source)
    original = source.read_bytes()
    before = inspect_pptx(source)
    result, output = clean(tmp_path, source, "clean.pptx", preserve_notes=True)
    assert result.returncode == 0, result.stderr
    after = inspect_pptx(output)
    assert after["slides"] == before["slides"]
    assert after["notes"] == before["notes"]
    assert not after["private"] and not after["atoms"]
    assert source.read_bytes() == original
    result, repeated = clean(tmp_path, output, "again.pptx", preserve_notes=True)
    assert result.returncode == 0, result.stderr
    assert inspect_pptx(repeated) == after
    result, reading = clean(tmp_path, source, "reading.pptx")
    assert result.returncode == 0, result.stderr
    assert all(not row["notes"] for row in inspect_pptx(reading)["notes"])


@pytest.mark.parametrize("variant,field", [("private-notes", "讲稿第 3 段"),
                                           ("private-title", "cNvPr.title")])
def test_cleanup_rejection_names_actual_slide_field_and_rule(tmp_path, variant, field):
    source = tmp_path / "old.pptx"
    make_pptx(source, variant)
    result, output = clean(tmp_path, source, "clean.pptx", preserve_notes=True)
    assert result.returncode == 4, result.stderr
    assert "第 2 页" in result.stderr and field in result.stderr
    assert "本机路径" in result.stderr
    assert PRIVATE_PATH not in result.stderr
    assert "TypeError" not in result.stderr
    assert not output.exists()


def test_damaged_pptx_reports_a_tool_failure_without_a_download_file(tmp_path):
    source = tmp_path / "old.pptx"
    source.write_bytes(b"PK damaged historical package")
    result, output = clean(tmp_path, source, "clean.pptx", preserve_notes=True)
    assert result.returncode == 4, result.stderr
    assert "PPTX" in result.stderr and "Traceback" not in result.stderr
    assert not output.exists()
