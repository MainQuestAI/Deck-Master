"""Direct consumers and offline dependency closure are separate contracts."""
import json
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from deck_master import models, native_review


def test_all_contract_mirrors_and_shared_dependency():
    root = Path(__file__).resolve().parents[2]
    contracts = root / 'src/deck_master/resources/contracts'
    for mirror in (root / 'docs').rglob('*.schema.json'):
        active = contracts / mirror.name
        if active.exists():
            assert mirror.read_bytes() == active.read_bytes(), str(mirror)
        if 'shared-contracts.v1.schema.json#/' in mirror.read_text():
            shared = mirror.parent / 'shared-contracts.v1.schema.json'
            assert shared.read_bytes() == (contracts / shared.name).read_bytes(), str(mirror)
            registry = Registry().with_resource(shared.name, Resource.from_contents(json.loads(shared.read_text())))
            def check(value):
                if isinstance(value, dict):
                    if value.get('$ref', '').startswith(shared.name + '#/'):
                        registry.resolver().lookup(value['$ref'])
                    for child in value.values():
                        check(child)
                elif isinstance(value, list):
                    for child in value:
                        check(child)
            check(json.loads(mirror.read_text()))
    assert (root / 'docs/specs/deck-master-rebuild-v1/contracts/shared-contracts.v1.schema.json').read_bytes() == (contracts / 'shared-contracts.v1.schema.json').read_bytes()


def test_native_output_is_standalone_including_replaces():
    schema = native_review._judgment_schema(['argument'])
    Draft202012Validator.check_schema(schema)
    ref = {'path': '.deckmaster/objects/ab/' + 'a' * 64 + '.json', 'sha256': 'a' * 64}
    # A real non-null replacement exercises the subtree copied into the output schema.
    Draft202012Validator(schema).validate({'reviews': [{'kind': 'argument', 'status': 'pass', 'observations': ['checked'], 'findings': [], 'replaces': ref}]})


def test_packaged_contract_dependency_graph_resolves_offline():
    folder = files('deck_master').joinpath('resources/contracts')
    schemas = {p.name: json.loads(p.read_text()) for p in folder.iterdir() if p.name.endswith('.schema.json')}
    registry = Registry().with_resources((name, Resource.from_contents(value)) for name, value in schemas.items())
    def walk(value, resolver):
        if isinstance(value, dict):
            if '$ref' in value:
                resolver.lookup(value['$ref'])
            for child in value.values():
                walk(child, resolver)
        elif isinstance(value, list):
            for child in value:
                walk(child, resolver)
    for name, schema in schemas.items():
        Draft202012Validator.check_schema(schema)
        walk(schema, registry.resolver(name))
    # Production callers continue to receive dictionary-shaped finding items.
    assert 'properties' in models.load_schema('review_v2')['properties']['findings']['items']
