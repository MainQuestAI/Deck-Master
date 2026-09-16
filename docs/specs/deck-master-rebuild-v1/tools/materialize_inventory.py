#!/usr/bin/env python3
"""Read-only Git inventory for this proposed specification pack.

Reads a fixed commit, never imports/executes repository Python, and writes reports
only to an explicitly requested directory outside the repository. It does not
checkout, reset, modify, stage, delete or migrate any repository or user files.
Classification is a proposed disposition, not a determination of dead code.
"""
from __future__ import annotations
import argparse
import ast
import csv
import json
from pathlib import Path
import re
import subprocess
import sys

DEFAULT_REF = '2a866cf138f6359f853db35e0a926ad79391b691'
PACK = Path(__file__).resolve().parents[1]


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(['git', '-C', str(repo), *args], check=False,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', 'replace').strip())
    return result.stdout


def rows_csv(name: str) -> list[dict[str, str]]:
    with (PACK / 'inventory' / name).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--ref', default=DEFAULT_REF, help='Exact 40-character commit SHA, already local.')
    parser.add_argument('--out', required=True, type=Path, help='Report directory outside the repository.')
    options = parser.parse_args()
    repo = options.repo.expanduser().resolve()
    output = options.out.expanduser().resolve()
    if not re.fullmatch('[a-fA-F0-9]{40}', options.ref):
        parser.error('--ref must be an exact 40-character SHA; this tool does not fetch branches.')
    try:
        actual_root = Path(git(repo, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
        if output == actual_root or output.is_relative_to(actual_root):
            raise ValueError('--out must be outside the repository to keep the code checkout read-only.')
        sha = options.ref.lower()
        git(repo, 'cat-file', '-e', sha + '^{commit}')
        paths = [p.decode('utf-8') for p in git(repo, 'ls-tree', '-r', '-z', '--name-only', sha).split(b'\0') if p]
        exact: dict[str, dict] = {}
        for name in ['old-files.csv', 'old-contracts.csv', 'old-tests.csv', 'skills.csv', 'root-and-config.csv']:
            for item in rows_csv(name):
                exact[item['path']] = item
        rules = sorted(json.loads((PACK / 'inventory/path-rules.json').read_text()),
                       key=lambda r: len(r['prefix']), reverse=True)
        report = []
        for path in paths:
            matched = exact.get(path)
            match_type = 'exact'
            if matched is None:
                matched = next((r for r in rules if path.startswith(r['prefix'])), None)
                match_type = 'prefix' if matched else 'unclassified'
            matched = matched or {}
            report.append({
                'source_commit': sha, 'path': path,
                'action': matched.get('action', 'REVIEW'),
                'target': matched.get('target', ''),
                'detail': matched.get('change_detail', matched.get('detail', matched.get('behavior', ''))),
                'phase': matched.get('work_package', matched.get('phase', matched.get('when', ''))),
                'classification_basis': match_type,
                'verification': 'Proposed disposition only; callers, behavior, deletion conditions need Codex verification.',
            })
        literals = []
        if 'scripts/deck_master.py' in paths:
            source = git(repo, 'show', sha + ':scripts/deck_master.py').decode('utf-8')
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'add_parser' and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)):
                    literals.append({'command_literal': node.args[0].value, 'line': node.lineno,
                                     'note': 'Static add_parser literal; may be nested. Not a live CLI count.',
                                     'disposition': 'Map explicitly per Spec09 or return retirement guidance; never execute old OS for a new project.'})
        output.mkdir(parents=True, exist_ok=True)
        write_csv(output / 'all-tracked-files.csv', report)
        write_csv(output / 'cli-parser-literals.csv', sorted(literals, key=lambda r: r['line']))
        paths_set = set(paths)
        absent = sorted(set(exact) - paths_set)
        summary = {
            'status': 'inventory_generated_not_implementation_verified',
            'commit': sha, 'expected_baseline': DEFAULT_REF, 'baseline_differs': sha != DEFAULT_REF,
            'tracked_files': len(report), 'exact_rules': sum(r['classification_basis'] == 'exact' for r in report),
            'prefix_rules': sum(r['classification_basis'] == 'prefix' for r in report),
            'unclassified': [r['path'] for r in report if r['classification_basis'] == 'unclassified'],
            'planned_or_absent_exact_paths': absent,
            'static_parser_literals': len(literals),
            'writes': ['all-tracked-files.csv', 'cli-parser-literals.csv', 'summary.json'],
            'repo_modified': False,
        }
        (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, SyntaxError) as exc:
        print(f'Inventory not completed: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
