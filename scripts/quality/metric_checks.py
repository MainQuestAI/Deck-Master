"""Compare explicitly bound chart/narrative metric scopes; no inferred conversions."""
from typing import Any


def find_metric_scope_conflicts(packages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics = {}
    for package in packages:
        for citation in package.get('citations', []):
            if not isinstance(citation, dict) or not citation.get('metric_id'):
                continue
            if citation.get('representation') not in {'chart', 'narrative'}:
                continue
            metrics.setdefault(citation['metric_id'], []).append((str(package.get('page_id', '')), citation))
    findings = []
    for metric, entries in metrics.items():
        if {c['representation'] for _, c in entries} != {'chart', 'narrative'}:
            continue
        scopes = {(str(c.get('unit', '')).strip(), str(c.get('period', '')).strip()) for _, c in entries}
        if len(scopes) == 1 and all(next(iter(scopes))):
            continue
        findings.append({'check': 'metric_scope_conflict', 'severity': 'P1', 'dimension': 'metric_scope',
                         'metric_id': metric, 'page_id': entries[0][0],
                         'page_ids': sorted({p for p, _ in entries}),
                         'message': f'Metric {metric} has conflicting or incomplete chart/narrative unit or period.',
                         'observed_scopes': [{'page_id': p, 'representation': c['representation'], 'unit': c.get('unit'), 'period': c.get('period'), 'claim_text': c.get('claim_text')} for p,c in entries],
                         'refs': [f'page_packages/{p}.json' for p in sorted({p for p,_ in entries})],
                         'repair_instruction': 'Align the source-backed unit and period in both representations, or use distinct metric identities for genuinely different scopes; do not silently convert values.'})
    return findings
