"""Workflow policy & preauthorization (A4, D10).

A preauthorization is an explicit, scoped, time-bounded grant that lets the
Autopilot cross a normally-manual transition WITHOUT a fresh human approval,
*except* for the non-bypassable final export (``deck-review->client-export``),
which can never be preauthorized (D8).

Preauthorizations are append-only records under
``workflow/preauthorization_log.jsonl``; ``workflow/preauthorization.json`` is
the active projection. Natural-language "继续做" never becomes a standing
grant — only an explicit policy record with actor / scope / expiry counts.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from skills.manifest import Registry, load_registry

SCHEMA_VERSION = "deck_workflow_policy.v1"
ACTIVE_FILE = "workflow/preauthorization.json"
LOG_FILE = "workflow/preauthorization_log.jsonl"

# Transition that may NEVER be preauthorized (D8, non-bypassable).
FINAL_EXPORT_TRANSITION = "deck-review->client-export"

MODES = ("interactive", "preauthorized", "quick", "repair", "review-only")
COST_CLASSES = ("none", "low", "medium", "high")


class PolicyError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def transition_key(from_stage: str, to_stage: str | None) -> str:
    return f"{from_stage}->{to_stage or 'none'}"


class Preauthorization:
    """A single preauthorization policy record (immutable snapshot)."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._d = data

    @property
    def data(self) -> dict[str, Any]:
        return dict(self._d)

    @property
    def policy_id(self) -> str:
        return str(self._d.get("policy_id"))

    @property
    def revoked(self) -> bool:
        return bool(self._d.get("revoked", False))

    @property
    def expires_at(self) -> datetime | None:
        v = self._d.get("expires_at")
        if not v:
            return None
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError:
            return None

    @property
    def mode(self) -> str:
        return str(self._d.get("mode"))

    def is_expired(self, *, now: datetime | None = None) -> bool:
        exp = self.expires_at
        if exp is None:
            return False
        return (now or _now()) >= exp

    def is_active(self, *, now: datetime | None = None) -> bool:
        return not self.revoked and not self.is_expired(now=now)

    def covers(self, transition: str) -> bool:
        return transition in (self._d.get("allowed_transitions") or [])


class PreauthorizationRuntime:
    def __init__(self, registry: Registry | None = None, *, now: datetime | None = None) -> None:
        self.registry = registry or load_registry()
        self._now = now  # if None use real clock

    def _clock(self) -> datetime:
        return self._now or _now()

    # --- paths ---
    def _active_path(self, root: Path) -> Path:
        return root / ACTIVE_FILE

    def _log_path(self, root: Path) -> Path:
        return root / LOG_FILE

    # --- create ---
    def create(
        self,
        run_dir: str | Path,
        *,
        run_id: str,
        actor: dict[str, Any],
        mode: str,
        allowed_transitions: list[str],
        material_roots: list[str] | None = None,
        allowed_source_classes: list[str] | None = None,
        max_generated_pages: int | None = None,
        max_cost_class: str = "low",
        baseline_fingerprint: str = "",
        ttl_seconds: int = 3600,
    ) -> Preauthorization:
        if mode not in MODES:
            raise PolicyError(f"unknown mode: {mode}")
        if max_cost_class not in COST_CLASSES:
            raise PolicyError(f"unknown cost class: {max_cost_class}")
        # D8: final export can never be preauthorized.
        if FINAL_EXPORT_TRANSITION in allowed_transitions:
            raise PolicyError(
                "final client export transition is non-bypassable and cannot be preauthorized"
            )

        # validate that allowed transitions are real contract transitions
        valid = self._valid_transitions()
        for t in allowed_transitions:
            if t not in valid:
                raise PolicyError(f"unknown transition: {t}")

        now = self._clock()
        record = {
            "schema_version": SCHEMA_VERSION,
            "policy_id": f"policy_{uuid.uuid4().hex[:12]}",
            "run_id": run_id,
            "mode": mode,
            "actor": dict(actor),
            "allowed_transitions": list(allowed_transitions),
            "protected_transitions": [FINAL_EXPORT_TRANSITION],
            "material_roots": list(material_roots or []),
            "allowed_source_classes": list(allowed_source_classes or []),
            "max_generated_pages": int(max_generated_pages) if max_generated_pages is not None else 0,
            "max_cost_class": max_cost_class,
            "baseline_fingerprint": baseline_fingerprint,
            "created_at": _utc(now),
            "expires_at": _utc(now + timedelta(seconds=ttl_seconds)),
            "revoked": False,
        }
        root = Path(run_dir).expanduser().resolve()
        root.joinpath("workflow").mkdir(parents=True, exist_ok=True)
        # append-only log
        with self._log_path(root).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        # active projection (latest non-revoked)
        self._refresh_active(root)
        return Preauthorization(record)

    # --- revoke ---
    def revoke(self, run_dir: str | Path, policy_id: str, *, by_actor: dict[str, Any]) -> Preauthorization:
        root = Path(run_dir).expanduser().resolve()
        record = self._find(root, policy_id)
        if record is None:
            raise PolicyError(f"unknown policy: {policy_id}")
        record["revoked"] = True
        with self._log_path(root).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._refresh_active(root)
        return Preauthorization(record)

    # --- query ---
    def list(self, run_dir: str | Path) -> list[Preauthorization]:
        root = Path(run_dir).expanduser().resolve()
        out: list[Preauthorization] = []
        log = self._log_path(root)
        if not log.exists():
            return out
        seen: dict[str, dict[str, Any]] = {}
        for line in log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            seen[rec.get("policy_id")] = rec
        for rec in seen.values():
            out.append(Preauthorization(rec))
        return out

    def active_for(self, run_dir: str | Path, transition: str) -> Preauthorization | None:
        now = self._clock()
        for p in self.list(run_dir):
            if p.is_active(now=now) and p.covers(transition):
                return p
        return None

    def _find(self, root: Path, policy_id: str) -> dict[str, Any] | None:
        for p in self.list(root):
            if p.policy_id == policy_id:
                return p.data
        return None

    def _refresh_active(self, root: Path) -> None:
        now = self._clock()
        latest: dict[str, Any] | None = None
        for p in self.list(root):
            if p.is_active(now=now):
                latest = p.data
        proj = self._active_path(root)
        proj.parent.mkdir(parents=True, exist_ok=True)
        tmp = proj.with_suffix(".json.tmp")
        tmp.write_text((json.dumps(latest, ensure_ascii=False, indent=2) + "\n") if latest else "null\n", encoding="utf-8")
        os.replace(tmp, proj)

    def _valid_transitions(self) -> set[str]:
        out: set[str] = set()
        for c in self.registry.ordered_contracts():
            nxt = c.next_stage
            if nxt:
                out.add(transition_key(c.stage_id, nxt))
        # the export gate
        out.add(FINAL_EXPORT_TRANSITION)
        return out


__all__ = [
    "PreauthorizationRuntime",
    "Preauthorization",
    "PolicyError",
    "FINAL_EXPORT_TRANSITION",
    "transition_key",
    "SCHEMA_VERSION",
]
