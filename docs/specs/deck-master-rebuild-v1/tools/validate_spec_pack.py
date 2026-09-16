#!/usr/bin/env python3
"""Validate this documentation pack and synthetic examples, NOT the product.

Reads files only. Writes JSON to stdout. No product imports, model calls,
PPT compilation, browser startup, installation, or repository changes.
Requires jsonschema. Optional --baseline-zip enables v1.0 regression checks.
"""
from __future__ import annotations
import argparse
import copy
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from zipfile import ZipFile
from jsonschema import Draft202012Validator, FormatChecker


def read(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def nested(value):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from nested(v)
    elif isinstance(value, list):
        for v in value:
            yield from nested(v)


def atoms(page):
    pid = page['page_id']; out = {}
    def add(key, value):
        if isinstance(value, str) and value:
            if key in out: raise AssertionError(f'duplicate atom {key}')
            out[key] = value
    cv=page['customer_visible'];add(f'atom:{pid}:title',cv.get('title'));add(f'atom:{pid}:subtitle',cv.get('subtitle'))
    seen_items=set()
    def items(xs):
        for item in xs:
            assert item['id'] not in seen_items, 'duplicate bullet item ID'
            seen_items.add(item['id']);add(f"atom:{pid}:item:{item['id']}:text",item['text']);items(item.get('children',[]))
    for block in cv['body_blocks']:
        bid=block['id'];typ=block['type']
        if typ=='paragraph':add(f'atom:{pid}:block:{bid}:text',block['text'])
        if typ=='bullets':add(f'atom:{pid}:block:{bid}:heading',block.get('heading'));items(block['items'])
        if typ=='table':
            add(f'atom:{pid}:block:{bid}:title',block.get('title'))
            for c in block['columns']:add(f"atom:{pid}:column:{bid}:{c['id']}:label",c['label'])
            for row in block['rows']:
                for c in row['cells']:add(f"atom:{pid}:cell:{bid}:{row['id']}:{c['column_id']}:display_text",c['display_text'])
    for key,kind in [('labels','label'),('footnotes','footnote'),('callouts','callout')]:
        for x in cv.get(key,[]):add(f"atom:{pid}:{kind}:{x['id']}:text",x['text'])
    return out


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--baseline-zip',type=Path)
    args=ap.parse_args();root=args.pack.resolve();checks=[]
    def check(name,fn):
        try:
            detail=fn();checks.append({'check':name,'result':'pass','detail':detail})
        except Exception as e:
            checks.append({'check':name,'result':'fail','detail':f'{type(e).__name__}: {e}'})
    validators={}
    def schema_examples():
        for p in (root/'contracts').glob('*.json'):
            d=read(p);Draft202012Validator.check_schema(d)
            validators[d['properties']['schema_version']['const']]=Draft202012Validator(d,format_checker=FormatChecker())
        assert len(validators)==5
        count=0
        for p in (root/'examples').rglob('*.json'):
            if p.name.startswith('invalid-'):continue
            for d in nested(read(p)):
                ver=d.get('schema_version')
                if ver in validators:
                    validators[ver].validate(d);count+=1
        return f'5 schema definitions; {count} embedded/standalone synthetic contract objects valid. Not product behavior.'
    check('schema_and_synthetic_objects',schema_examples)
    def refs():
        count=0
        primary=root/'examples/synthetic-project'
        for p in (root/'examples').rglob('*.json'):
            if p.name.startswith('invalid-'):continue
            rel=p.relative_to(root/'examples')
            if 'roundtrips' in rel.parts:
                q=p
                # All round-trip groups with object references carry a local project directory.
                while q!=root/'examples' and not (q/'project').is_dir():q=q.parent
                if (q/'project').is_dir():project=q/'project'
                else:project=primary
            else:project=primary
            # Inside a concrete project, find its root explicitly.
            for parent in p.parents:
                if (parent/'.deckmaster/current.json').is_file():project=parent;break
            for d in nested(read(p)):
                path=d.get('path');h=d.get('sha256')
                if isinstance(path,str) and path.startswith('.deckmaster/objects/') and isinstance(h,str):
                    target=project/path
                    assert target.is_file(), f'missing {p.relative_to(root)} -> {path}'
                    assert sha(target.read_bytes())==h, f'digest mismatch {path}'
                    assert target.stem==h and target.parent.name==h[:2],f'CAS path mismatch {path}'
                    count+=1
        for project in [p.parent.parent for p in (root/'examples').rglob('.deckmaster/current.json')]:
            cur=read(project/'.deckmaster/current.json');doc=read(project/'.deckmaster/revisions'/f"{cur['revision_id']}.json")
            assert doc['revision_id']==cur['revision_id']
        return f'{count} concrete synthetic Ref occurrences resolve to exact local bytes; current pointers resolve. No real project accessed.'
    check('synthetic_file_references',refs)
    def design_crossrefs():
        docs=0
        for p in (root/'examples').rglob('*.json'):
            if p.name.startswith('invalid-'):continue
            d=read(p)
            if not isinstance(d,dict) or d.get('schema_version')!='deck_document.v1':continue
            dc=d['design_context'];fs={x['font_id']:x for x in dc['fonts']};styles={x['style_id']:x for x in dc['styles']};assets={x['asset_id']:x for x in dc['assets']}
            assert len(fs)==len(dc['fonts']);assert len(styles)==len(dc['styles']);assert len(assets)==len(dc['assets'])
            assert dc['default_style_id'] in styles
            assert set(dc['allowed_asset_ids'])<=set(assets)
            for v in styles.values():
                assert v['typography']['body_font_id'] in fs and v['typography']['heading_font_id'] in fs
            def visit(fid,seen):
                assert fid not in seen,'font fallback cycle'
                for nxt in fs[fid]['fallback_font_ids']:
                    assert nxt in fs;visit(nxt,seen|{fid})
            for fid,f in fs.items():
                visit(fid,set())
                if f['asset_id'] is not None:assert f['asset_id'] in assets and assets[f['asset_id']]['kind']=='font'
            docs+=1
        # Sample page relations reference stable atoms, not array pointers.
        p=read(root/'examples/page.v2.json');valid=atoms(p)
        for node in p['visual_spec'].get('nodes',[]):
            assert node['label_ref'] in valid
            assert all(v in valid for v in node.get('responsibility_refs',[]))
        return f'{docs} synthetic Document configurations checked for ID/fallback consistency; sample page atom refs valid. Font availability/rendering NOT tested.'
    check('design_and_atom_reference_examples',design_crossrefs)
    def source_hash():
        v=validators['deck_document.v1'];p=root/'examples/roundtrips/missing-source'
        v.validate(read(p/'project/.deckmaster/revisions/rev_missing_001.json'));v.validate(read(p/'document-hash-omitted.json'))
        assert list(v.iter_errors(read(p/'invalid-zero-hash.json'))),'all-zero original hash should reject'
        d=read(root/'examples/document.v1.json');bad=copy.deepcopy(d);bad['sources'][0]['extract']['sha256']=None
        assert list(v.iter_errors(bad)),'stored Ref cannot have unknown digest'
        if args.baseline_zip:
            with ZipFile(args.baseline_zip) as z:
                name=next(n for n in z.namelist() if n.endswith('/contracts/document.v1.schema.json'))
                old=Draft202012Validator(json.loads(z.read(name)))
                example_name=next(n for n in z.namelist() if n.endswith('/examples/document.v1.json'))
                baseline=json.loads(z.read(example_name));baseline['sources'][0]['original_sha256']=None
                assert list(old.iter_errors(baseline)), 'v1.0 null-source regression not reproduced'
        return 'v1.1 null/omitted original digest accepted; zero placeholder and unknown stored Ref digest rejected. v1.0 null rejection reproduced when baseline provided.'
    check('R1_unknown_original_hash',source_hash)
    def graph():
        tasks=read(root/'inventory/task-list.json');acs=read(root/'inventory/acceptance-matrix.json');by={t['task_id']:t for t in tasks};aid={a['acceptance_id'] for a in acs}
        assert len(by)==25 and len(aid)==90
        deps={k: ([] if t['depends_on']=='—' else t['depends_on'].split(',')) for k,t in by.items()}
        def ancestors(k,stack=()):
            assert k in by,f'unknown {k}';assert k not in stack,'dependency cycle'
            result=set()
            for child in deps[k]:result.add(child);result|=ancestors(child,stack+(k,))
            return result
        for k in by:ancestors(k)
        end=ancestors('T25');assert end==set(by)-{'T25','T23'},f'missing {set(by)-end-{"T25"}}'
        assert next(a for a in acs if a['acceptance_id']=='AC-K01')['task_id']=='T10'
        assert 'T13' in deps['T20']
        assert by['T01']['acceptance_ids']=='AC-L07'
        assert 'AC-L05' in by['T24']['acceptance_ids'].split(',')
        assert 'T03.min' in by['T06']['start_after'] and 'T09.min' in by['T10']['start_after']
        for t in tasks:
            assert set(t['acceptance_ids'].split(','))<=aid
            assert t['start_after'] and t['early_delivery']
        for a in acs:assert a['acceptance_id'] in by[a['task_id']]['acceptance_ids'].split(','),f'unowned {a}'
        return '25-task completion DAG acyclic; T25 engineering delivery covers 23 predecessors including T13; T23 human acceptance remains separate; T01/L07 and T24/L05 separated; early-start fields present. Does not prove implementation done.'
    check('R3_R6_task_graph_and_acceptance',graph)
    def cards():
        tasks=read(root/'task-cards/tasks.json'); originals={t['task_id']:t for t in read(root/'inventory/task-list.json')}
        acs=read(root/'inventory/acceptance-matrix.json'); steps=[]
        for t in tasks:
            for key,value in originals[t['task_id']].items():
                if key!='status': assert t[key]==value,(t['task_id'],key)
            assert t['primary_acceptance_ids']==[a['acceptance_id'] for a in acs if a['task_id']==t['task_id']]
            body=(root/'task-cards'/t['card']).read_text()
            for step in t['subtasks']:
                assert step['execution_unit']=='internal_step'
                assert step['subtask_id']+' '+step['title'] in body
                assert step['work'] in body and step['deliverable_and_check'] in body
                steps.append(step)
        assert len(tasks)==25 and len(steps)==126 and len({s['subtask_id'] for s in steps})==126
        with (root/'task-cards/subtasks.csv').open(encoding='utf-8-sig',newline='') as f: assert list(csv.DictReader(f))==steps
        assert 'T23.04' in (root/'task-cards/T25.md').read_text()
        assert 'AC-K01' not in next(t for t in tasks if t['task_id']=='T08')['acceptance_ids']
        return '25 cards and 126 internal steps match JSON/CSV, task source and unique AC owners; runtime behavior remains unverified.'
    check('task_cards_consistency',cards)
    def inventories():
        for stem in ['task-list','acceptance-matrix','new-files','old-files','root-and-config']:
            with (root/f'inventory/{stem}.csv').open(encoding='utf-8-sig',newline='') as f:c=list(csv.DictReader(f))
            j=read(root/f'inventory/{stem}.json');assert c==j,stem
        assert len(read(root/'inventory/old-files.json'))==177
        assert len(read(root/'inventory/new-files.json'))==75
        for name,expected in [('old-contracts',58),('old-tests',122)]:
            with (root/f'inventory/{name}.csv').open(encoding='utf-8-sig',newline='') as f:assert len(list(csv.DictReader(f)))==expected
        if args.baseline_zip:
            with ZipFile(args.baseline_zip) as z:
                for f in ['inventory/old-files.json','inventory/old-files.csv','inventory/old-contracts.csv','inventory/old-tests.csv',
                          'sources/architecture-audit.md','sources/diagnosis.md','sources/rebuild-plan.md','sources/prior-refactor-decision.md']:
                    name=next(n for n in z.namelist() if n.endswith('/'+f));assert z.read(name)==(root/f).read_bytes(),f'changed historical {f}'
        return 'JSON/CSV tables agree; original 177/58/122 scope and 75 targets preserved. Historical evidence/old path inventories unchanged when baseline provided; NOT a fresh Git path audit.'
    check('inventories_and_source_preservation',inventories)
    def atoms_roundtrip():
        d=read(root/'examples/roundtrips/atom-identity.json');before=atoms(d['before_page']);after=atoms(d['after_page'])
        assert all(k in before and k in after for k in d['expected_stable_ids'])
        assert all(k not in before and k in after for k in d['new_ids'])
        assert before['atom:p09:item:version:text']!=after['atom:p09:item:version:text']
        return 'Synthetic reorder/text change preserves expected atom IDs; new item receives separate ID. Example-level check only.'
    check('stable_atom_roundtrip',atoms_roundtrip)
    def fixed():
        p=root/'examples/roundtrips/review-fixed';r0=read(p/'review-before.json');r1=read(p/'review-after.json');ex=read(p/'expected.json')
        def check_fixed(r):
            assert r['replaces']==ex['old_review'];assert r['review_id']==r0['review_id']
            assert ex['current_svg_artifact'] in r['subjects'];assert r['subjects']!=r0['subjects']
            assert r['observations'] and r['findings'][0]['evidence'];assert r['findings'][0]['resolution']=='fixed'
            assert r['findings'][0]['finding_id']==r0['findings'][0]['finding_id']
        check_fixed(r1)
        for n in ['invalid-only-resolution.json','invalid-no-recheck.json']:
            validators['deck_review.v1'].validate(read(p/n))  # format can be valid while semantic linkage is wrong
            try:check_fixed(read(p/n))
            except AssertionError:pass
            else:raise AssertionError(f'{n} did not fail fixture linkage check')
        return 'Example replaces/new-subject/evidence link valid; two schema-valid negative examples fail fixture linkage checks. No real reviewer execution verified.'
    check('review_fixed_roundtrip',fixed)
    def envelopes():
        p=root/'examples/roundtrips/result-envelope'
        allowed={'kind','files','pages','page_order','artifact_specs','reviews','usage_events','notes'}
        def validate(e):
            assert 'kind' in e and set(e)<=allowed
            assert e['kind'] in {'compose','blueprint','reconstruct','review','repair'}
            files={}
            for f in e.get('files',[]):
                assert f['file_id'] not in files;files[f['file_id']]=f
                path=Path(f['path']);assert not path.is_absolute() and '..' not in path.parts
                assert (p/'staging'/path).is_file()
            for spec in e.get('artifact_specs',[]):
                assert spec['file_id'] in files
                prom=spec['provenance'].get('submitted_prompt_file_id')
                if prom:assert prom in files
        for name in ['compose','blueprint','reconstruct','reconstruct-with-reference','reconstruct-complete','review','repair']:validate(read(p/(name+'.json')))
        for name in ['invalid-path-escape','invalid-type-discriminator']:
            try:validate(read(p/(name+'.json')))
            except AssertionError:pass
            else:raise AssertionError(f'{name} was not rejected')
        mini=read(p/'minimal-page.json');svg=(p/'staging/complete-page.svg').read_text()
        import xml.etree.ElementTree as ET
        tree=ET.fromstring(svg);bound={x.attrib['data-text-ref']:''.join(x.itertext()) for x in tree.iter() if 'data-text-ref' in x.attrib}
        assert atoms(mini)==bound
        return 'Five kind envelope forms, declared fixture files and a complete 3-atom positive reference example checked; invalid discriminator/path rejected. NOT actual task accept or visual production.'
    check('temporary_result_envelopes',envelopes)
    def allowance():
        d=read(root/'examples/roundtrips/call-allowance.json');held={'reserved','in_flight','consumed','unknown'}
        for step in d['sequence']:
            n=sum(v in held for v in step['states'].values());assert n==step['occupied'] and d['limit']-n==step['free']
        states={x['operation']:x['states'] for x in d['sequence']}
        assert states['restore older content']==states['response lost']
        return 'Static allowance sequence arithmetic and non-resetting restore expectation consistent. Parallelism, file locks and external calls NOT executed.'
    check('allowance_state_example',allowance)
    def written_sync():
        assert len(list((root/'specs').glob('*.md')))==15 and len(list((root/'work-packages').glob('*.md')))==5
        assert 'codex/rebuild-mainline-v1' in (root/'specs/01-target-architecture.md').read_text()
        assert '自动调用' in (root/'specs/09-cli-and-host-protocol.md').read_text()
        assert 'editable_shapes_and_text' in (root/'specs/06-native-compiler.md').read_text()
        for fn in ['README.md','MASTER_IMPLEMENTATION_SPEC.md','IMPLEMENTATION_CHECKLIST.md','CHANGELOG-v1.1.md']:
            assert (root/fn).is_file()
        master=(root/'MASTER_IMPLEMENTATION_SPEC.md').read_text()
        for token in ['03.3a','07.9','09.7','T13.min','AC-K16','codex/rebuild-mainline-v1']:
            assert token in master, f'master missing {token}'
        assert not any(p.suffix.lower() in {'.ttf','.otf','.woff','.woff2','.ttc'} for p in root.rglob('*'))
        # Active relative Markdown links; archived evidence is not a current navigation contract.
        failures=[]
        for p in root.rglob('*.md'):
            if 'sources' in p.relative_to(root).parts:continue
            for link in re.findall(r'\]\(([^)]+)\)',p.read_text()):
                if '://' in link or link.startswith(('#','/','sandbox:','<')):continue
                path=link.split('#')[0]
                if not path:continue
                if not (p.parent/path).exists():failures.append(f'{p.relative_to(root)} -> {path}')
        assert not failures, failures[:8]
        return '15 chapters / 5 workbooks / merged handbook and active links present; branch name, early slicing, editability wording synchronized; no font binaries. Completeness of product APIs not asserted.'
    check('document_sync_and_links',written_sync)
    if (root/'FILES.sha256').exists():
        def checksums():
            lines=(root/'FILES.sha256').read_text().splitlines()
            names=set()
            for line in lines:
                h,name=line.split(None,1);name=name.strip();target=(root/name).resolve()
                assert target.is_relative_to(root), f'checksum path outside pack: {name}'
                assert name not in names, f'duplicate checksum entry: {name}'
                names.add(name)
                assert target.is_file() and sha(target.read_bytes())==h,name
            expected={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name!='FILES.sha256'}
            assert names==expected, f'checksum coverage mismatch: {names.symmetric_difference(expected)}'
            return f'{len(lines)} file checksums valid; all pack files except the checksum list itself covered.'
        check('pack_file_checksums',checksums)
    failures=[c for c in checks if c['result']=='fail']
    out={'pack_version':'1.1','validation_scope':'documentation_and_synthetic_examples_only',
      'product_code_implemented':False,'real_repository_reverified':False,'real_host_or_compiler_or_ui_or_install_run':False,
      'business_acceptance_performed':False,'baseline_zip_used':bool(args.baseline_zip),'checks':checks,'failed':len(failures),
      'note':'These checks do not prove concurrency enforcement, source authenticity, font matching, actual rendering, human review or business usefulness. 需要 Codex 在实施后核验。'}
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 1 if failures else 0

if __name__=='__main__':
    raise SystemExit(main())
