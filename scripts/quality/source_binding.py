"""Verify a quoted span against immutable source bytes, never generated pages."""
import hashlib
import re
from pathlib import Path


def source_quote_matches(source, evidence, *, run_dir=None):
    if any(marker in str(source.get('origin_type') or source.get('source_type') or source.get('kind') or '').lower() for marker in ('generated', 'page_package', 'self_authored')):
        return False
    ref = source.get('origin_ref') or source.get('origin_path') or source.get('path')
    expected = source.get('file_sha256') or source.get('sha256')
    if not ref or not expected:
        return False
    path = Path(ref).expanduser()
    if not path.is_absolute():
        if run_dir is None:
            return False
        path = Path(run_dir) / path
    if any(part in {'page_packages', 'native_outputs', 'page_scenes', 'quality_reports'} for part in path.parts):
        return False
    if run_dir is not None and path.resolve().is_relative_to(Path(run_dir).resolve()):
        from workflow.actions import revision_input_path
        path = revision_input_path(run_dir, path)
    try:
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            return False
        text = data.decode('utf-8')
    except (OSError, UnicodeDecodeError):
        return False
    position = evidence.get('source_position') or {}
    start, end = position.get('start'), position.get('end')
    if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, int) or not isinstance(end, int) or end < start:
        return False
    unit = position.get('unit_type')
    if unit == 'character':
        if not 0 <= start < end <= len(text):
            return False
        quoted = text[start:end]
    elif unit in {'line', 'paragraph'}:
        units = text.splitlines() if unit == 'line' else re.split(r'\n\s*\n', text)
        if not 1 <= start <= end <= len(units):
            return False
        quoted = ('\n' if unit == 'line' else '\n\n').join(units[start-1:end])
    else:
        # Page/slide/image regions require a verified host extraction receipt.
        # Never interpret a made-up locator or a summary as original text.
        return False
    quote = evidence.get('quote')
    return bool(quote) and quote == quoted and hashlib.sha256(quoted.encode()).hexdigest() == evidence.get('quote_sha256')


def evidence_index(context_manifest):
    index = {}
    for source in (context_manifest or {}).get("sources", []):
        if not isinstance(source, dict):
            continue
        for evidence in source.get("evidence_candidates", []):
            if not isinstance(evidence, dict) or not evidence.get("evidence_id"):
                continue
            bare = str(evidence["evidence_id"])
            index.setdefault(bare, []).append((source, evidence))
            if source.get("source_id"):
                index.setdefault(str(source["source_id"]) + "::" + bare, []).append((source, evidence))
    return index


def find_invalid_source_bindings(packages, context_manifest, *, run_dir=None):
    index = evidence_index(context_manifest)
    findings = []
    for package in packages:
        refs = set(str(ref) for ref in package.get("evidence_bindings", []))
        refs.update(str(c.get("evidence_id")) for c in package.get("citations", []) if isinstance(c, dict) and c.get("evidence_id"))
        for ref in sorted(refs):
            candidates = index.get(ref, [])
            if len(candidates) != 1 or not source_quote_matches(*candidates[0], run_dir=run_dir):
                findings.append({"page_id": package.get("page_id", ""), "evidence_ref": ref, "check": "source_span_mismatch", "message": "Evidence reference does not uniquely resolve to the quoted span in verified original source bytes; generated page text and bare source IDs cannot certify support."})
    return findings
