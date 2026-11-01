import pytest

from deck_tools.jobs import compile_job


def test_build_reads_processed_text_and_rejects_stale_svg(tmp_path):
    source = tmp_path / "page.svg"
    source.write_text('<svg viewBox="0 0 1280 720"><text x="64" y="88" font-size="36" data-atom-id="atom:p1:title">535类标签</text></svg>')
    job = {"pages": [{"id": "p1", "content": {"title": "535类标签"}, "svg": str(source)}],
           "canvas": {"slide_width_in": 13.333, "slide_height_in": 7.5},
           "humanizer": True, "output": str(tmp_path / "current")}
    result = compile_job(job)
    assert result["humanizer"]["text_readback"] == "equal"
    job["pages"][0]["content"]["title"] = "536类标签"
    job["output"] = str(tmp_path / "stale")
    with pytest.raises(RuntimeError, match="p1"):
        compile_job(job)
