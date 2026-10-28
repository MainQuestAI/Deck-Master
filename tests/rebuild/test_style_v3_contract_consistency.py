"""Embedded style inputs retain the active standalone contract, including guidance."""
import json
from pathlib import Path

import pytest

from deck_master import models


@pytest.mark.parametrize("filename", ["style-proposal.v3.schema.json", "style-recipe.v3.schema.json"])
def test_embedded_style_input_matches_active_contract(filename):
    contracts = Path(models.__file__).parent / "resources" / "contracts"
    standalone = json.loads((contracts / "style-input.v3.schema.json").read_text())
    # A nested object does not declare its own schema dialect or document title.
    standalone.pop("$schema")
    standalone.pop("title")
    embedded = json.loads((contracts / filename).read_text())["properties"]["input"]
    if "$ref" in embedded:
        embedded = models._contract_registry().resolver(filename).lookup(embedded["$ref"]).contents
    assert embedded == standalone
