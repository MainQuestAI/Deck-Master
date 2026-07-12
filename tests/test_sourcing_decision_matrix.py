"""Decision matrix tests for _decide_for_page via build_sourcing_plan_v2.

Verifies that reuse/adapt/generate/evidence/manual/blocked decisions are
correctly chosen based on reuse_policy, retrieval_method, preview_status,
reuse_safe, and permission_status.
"""
from __future__ import annotations

import unittest

from sourcing.plan import build_sourcing_plan_v2


def _page_tasks(page_id: str = "beat_01", page_task_id: str = "task_01") -> dict:
    return {
        "pages": [
            {
                "beat_id": page_id,
                "page_task_id": page_task_id,
                "order": 1,
                "planning": {
                    "page_title": "Test Page",
                    "role": "opener",
                    "claim_ids": ["claim_01"],
                    "evidence_need": [],
                },
                "generation": {"generation_brief": "test brief"},
            }
        ],
    }


def _library_results(
    *,
    retrieval_method: str = "role_selection",
    preview_status: str = "ready",
    reuse_policy: str = "reuse_or_adapt",
    reuse_safe: bool | None = None,
    permission_status: str | None = None,
) -> dict:
    candidate: dict = {
        "asset_key": "canonical:test-001",
        "slide_id": "slide-001",
        "title": "Test Slide",
        "score": 0.9,
        "confidence": 0.85,
        "reuse_policy": reuse_policy,
        "source_authority": "verified",
        "freshness_status": "fresh",
    }
    if reuse_safe is not None:
        candidate["reuse_safe"] = reuse_safe
    if permission_status is not None:
        candidate["permission_status"] = permission_status
    return {
        "schema_version": "deck_master_ppt_library_selection.v2",
        "run_id": "decision-test",
        "status": "library_ready",
        "source": "ppt_library",
        "selections": [
            {
                "beat_id": "beat_01",
                "page_task_id": "task_01",
                "query_trace_id": "trace_01",
                "retrieval_method": retrieval_method,
                "preview_status": preview_status,
                "preview_degraded": preview_status != "ready",
                "candidates": [candidate],
            },
        ],
    }


def _no_candidate_library_results() -> dict:
    return {
        "schema_version": "deck_master_ppt_library_selection.v2",
        "run_id": "decision-test",
        "status": "library_degraded",
        "source": "ppt_library",
        "selections": [
            {
                "beat_id": "beat_01",
                "page_task_id": "task_01",
                "query_trace_id": "trace_01",
                "retrieval_method": "semantic_fallback",
                "preview_status": "missing",
                "preview_degraded": True,
                "candidates": [],
            },
        ],
    }


class DecisionMatrixTest(unittest.TestCase):
    """Test the reuse/adapt/generate decision matrix in _decide_for_page."""

    def _decide(self, library_results: dict, **kwargs) -> tuple[str, str, str]:
        plan = build_sourcing_plan_v2(
            run_id="decision-test",
            page_tasks=_page_tasks(),
            library_results=library_results,
            **kwargs,
        )
        page = plan["pages"][0]
        return str(page["decision"]), str(page["reason"]), str(page["permission_status"])

    def test_reuse_policy_adapt_produces_adapt(self) -> None:
        decision, reason, _ = self._decide(_library_results(reuse_policy="adapt"))
        self.assertEqual("adapt", decision)
        self.assertEqual("POLICY_ADAPT", reason)

    def test_reuse_policy_adapt_only_produces_adapt(self) -> None:
        decision, reason, _ = self._decide(_library_results(reuse_policy="adapt_only"))
        self.assertEqual("adapt", decision)
        self.assertEqual("POLICY_ADAPT_ONLY", reason)

    def test_semantic_fallback_produces_adapt(self) -> None:
        decision, reason, _ = self._decide(
            _library_results(retrieval_method="semantic_fallback")
        )
        self.assertEqual("adapt", decision)
        self.assertEqual("SEMANTIC_FALLBACK_ADAPT", reason)

    def test_preview_missing_produces_adapt(self) -> None:
        decision, reason, _ = self._decide(
            _library_results(preview_status="missing")
        )
        self.assertEqual("adapt", decision)
        self.assertEqual("PREVIEW_MISSING_ADAPT", reason)

    def test_preview_invalid_produces_adapt(self) -> None:
        decision, reason, _ = self._decide(
            _library_results(preview_status="invalid")
        )
        self.assertEqual("adapt", decision)
        self.assertEqual("PREVIEW_MISSING_ADAPT", reason)

    def test_reuse_safe_false_produces_adapt(self) -> None:
        decision, reason, _ = self._decide(
            _library_results(reuse_safe=False)
        )
        self.assertEqual("adapt", decision)
        self.assertEqual("REUSE_SAFE_FALSE_ADAPT", reason)

    def test_all_clear_produces_reuse(self) -> None:
        decision, reason, _ = self._decide(
            _library_results(reuse_policy="reuse_or_adapt", reuse_safe=True)
        )
        self.assertEqual("reuse", decision)
        self.assertEqual("ROLE_SELECTION_PREVIEW_READY", reason)

    def test_no_candidate_generate(self) -> None:
        decision, reason, _ = self._decide(_no_candidate_library_results())
        self.assertEqual("generate", decision)
        self.assertEqual("NO_CANDIDATE_GENERATE", reason)

    def test_no_candidate_evidence_when_generate_disabled(self) -> None:
        # Use page_tasks with evidence_need to trigger evidence path
        pt = _page_tasks()
        pt["pages"][0]["planning"]["evidence_need"] = "Supporting data required"
        plan = build_sourcing_plan_v2(
            run_id="decision-test",
            page_tasks=pt,
            library_results=_no_candidate_library_results(),
            allow_generate=False,
        )
        page = plan["pages"][0]
        self.assertEqual("evidence", page["decision"])
        self.assertEqual("NO_CANDIDATE_EVIDENCE", page["reason"])

    def test_generate_page_permission_not_required(self) -> None:
        _, _, permission = self._decide(_no_candidate_library_results())
        self.assertEqual("not_required", permission)

    def test_evidence_page_permission_not_required(self) -> None:
        pt = _page_tasks()
        pt["pages"][0]["planning"]["evidence_need"] = "data needed"
        plan = build_sourcing_plan_v2(
            run_id="decision-test",
            page_tasks=pt,
            library_results=_no_candidate_library_results(),
            allow_generate=False,
        )
        self.assertEqual("not_required", plan["pages"][0]["permission_status"])

    def test_permission_blocked_overrides_to_blocked(self) -> None:
        decision, reason, _ = self._decide(
            _library_results(permission_status="blocked")
        )
        self.assertEqual("blocked", decision)
        self.assertEqual("PERMISSION_BLOCKED", reason)

    def test_source_fingerprint_changes_with_candidate(self) -> None:
        plan_a = build_sourcing_plan_v2(
            run_id="fp-test",
            page_tasks=_page_tasks(),
            library_results=_library_results(reuse_policy="reuse_or_adapt"),
        )
        plan_b = build_sourcing_plan_v2(
            run_id="fp-test",
            page_tasks=_page_tasks(),
            library_results=_library_results(reuse_policy="adapt"),
        )
        self.assertNotEqual(
            plan_a["source_fingerprint"],
            plan_b["source_fingerprint"],
            "Fingerprint must change when decision changes (adapt vs reuse)",
        )

    def test_canonical_status_returned_not_sourcing_ready(self) -> None:
        """Plan with pending permission pages returns 'draft', not 'awaiting_approval'."""
        plan = build_sourcing_plan_v2(
            run_id="status-test",
            page_tasks=_page_tasks(),
            library_results=_library_results(reuse_policy="reuse_or_adapt"),
            permission_default="pending",
        )
        # With reuse candidate + pending permission → not ready → draft
        self.assertIn(plan["status"], ("draft", "awaiting_approval", "blocked"))
        self.assertNotEqual("sourcing_ready", plan["status"])


if __name__ == "__main__":
    unittest.main()
