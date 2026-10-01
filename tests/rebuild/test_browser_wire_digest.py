"""Client hashes must match the service after the actual JSON wire roundtrip."""
import json
from pathlib import Path
import random
import shutil
import subprocess

import pytest

from deck_master.models import canonical_json_bytes


def test_browser_wire_canonical_matches_python_for_coordinates_and_unicode_keys():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed to check the shipped browser serializer')
    randomizer = random.Random(6)
    values = [0, -0.0, 1e-4, 1e-5, 1e-6, 1e-7, -1e-7, 1e21, 1.2e20,
              {'😀': 1, '\uefff': 2}, {'text': '🙂e\u0301\r\n中', 'point': {'x': .00001, 'y': .999999}}]
    values += [randomizer.random() * 10 ** randomizer.randint(-16, 25) for _ in range(1000)]
    module = Path(__file__).resolve().parents[2] / 'src/deck_master/resources/static/v2/api.js'
    script = (f'import {{wireCanonical}} from {json.dumps(module.as_uri())};'
              f'const values={json.dumps(values)};'
              'console.log(JSON.stringify(values.map(v=>[JSON.stringify(v),wireCanonical(v)])));')
    result = subprocess.run([node, '--input-type=module', '-e', script],
                            capture_output=True, text=True, check=True)
    for wire, browser_canonical in json.loads(result.stdout):
        assert browser_canonical.encode('utf-8') == canonical_json_bytes(json.loads(wire))
