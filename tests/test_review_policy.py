from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from high_density.review_policy import resolve_review_policy
from page_roles import canonical_page_role, page_role_with_warning


def test_default_review_policy_is_producer_only_and_local_traceable() -> None:
    assert resolve_review_policy({}) == {
        "review_depth": "producer_only",
        "receipt_policy": "local_traceable",
        "legacy_review_policy": "local_traceable",
    }


def test_legacy_external_signed_requires_independent_main() -> None:
    assert resolve_review_policy({"review_policy": "external-signed"}) == {
        "review_depth": "independent_main",
        "receipt_policy": "external_signed",
        "legacy_review_policy": "external_signed",
    }


def test_independent_main_can_use_local_receipt() -> None:
    result = resolve_review_policy({"review_depth": "independent-main", "receipt_policy": "local-traceable"})

    assert result["review_depth"] == "independent_main"
    assert result["receipt_policy"] == "local_traceable"


def test_external_receipt_promotes_producer_only_to_independent_main() -> None:
    result = resolve_review_policy({"review_depth": "producer_only", "receipt_policy": "external_signed"})

    assert result["review_depth"] == "independent_main"
    assert result["receipt_policy"] == "external_signed"


def test_standard_page_roles_migrate_aliases_and_unknown_values() -> None:
    assert canonical_page_role("section-intro") == "section"
    assert canonical_page_role("section_handoff") == "section_divider"
    role, warning = page_role_with_warning("unregistered_role")

    assert role == "content"
    assert "defaulted to page_role 'content'" in warning
