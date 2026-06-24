"""Canonical Skill Manifest & Stage Contract registry loader.

Single truth source for Skill identity (``skills/manifest.json``) and Stage
behavior contracts (``skills/stage-contracts.json``). Runtime, Installer,
Route Resolver and Release Builder must read Skill identity from here instead
of maintaining independent skill lists (D4, G-02).

Usage::

    from skills.manifest import load_registry
    registry = load_registry()
    registry.skill("deck-brief")        # -> Skill
    registry.resolve("autoplan")        # -> Skill via alias
    registry.contract("deck-brief")    # -> StageContract
    registry.contracts_hash            # -> sha256 of canonical contracts (release lock)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MANIFEST_NAME = "manifest.json"
STAGE_CONTRACTS_NAME = "stage-contracts.json"
SCHEMA_NAME = "stage-contract.v1.schema.json"
SKILLS_SUBDIR = "skills"
CONTRACTS_DOC_DIR = "docs" / Path("contracts")

PRODUCTION_STAGE_IDS = (
    "deck-init",
    "deck-brief",
    "deck-planner",
    "deck-sourcing",
    "deck-producer",
    "deck-builder",
    "deck-quality",
    "deck-review",
    "deck-learn",
)


class ManifestError(ValueError):
    """Raised when the manifest or stage contracts are inconsistent."""


@dataclass(frozen=True)
class Skill:
    name: str
    path: str
    role: str
    public: bool
    description: str
    compat_aliases: tuple[str, ...] = ()
    input_types: tuple[str, ...] = ()
    exit_artifacts: tuple[str, ...] = ()
    stage_id: str | None = None
    backend_dependency: str = ""
    public_name: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def aliases(self) -> tuple[str, ...]:
        return tuple(self.compat_aliases)


@dataclass(frozen=True)
class StageContract:
    stage_id: str
    skill_name: str
    order: int
    lane: str
    raw: dict[str, Any]

    @property
    def transition_policy(self) -> dict[str, Any]:
        return dict(self.raw.get("transition_policy", {}))

    @property
    def next_stage(self) -> str | None:
        return self.transition_policy.get("next_stage")

    @property
    def approval_required(self) -> bool:
        return bool(self.transition_policy.get("approval_required"))

    @property
    def non_bypassable(self) -> bool:
        return bool(self.transition_policy.get("non_bypassable"))

    @property
    def preauthorizable(self) -> bool:
        return bool(self.transition_policy.get("preauthorizable"))

    @property
    def entry(self) -> dict[str, Any]:
        return dict(self.raw.get("entry", {}))

    @property
    def exit_criteria(self) -> dict[str, Any]:
        return dict(self.raw.get("exit_criteria", {}))

    @property
    def outputs(self) -> list[dict[str, Any]]:
        return list(self.raw.get("outputs", []))

    @property
    def forcing_questions(self) -> list[dict[str, Any]]:
        return list(self.raw.get("forcing_questions", []))

    @property
    def staleness_dependencies(self) -> list[str]:
        return list(self.raw.get("staleness_dependencies", []))


@dataclass(frozen=True)
class Registry:
    skills_by_name: dict[str, Skill]
    contracts_by_stage: dict[str, StageContract]
    manifest_version: str
    suite_version: str
    contracts_hash: str

    # --- skill accessors ---
    def skill(self, name: str) -> Skill:
        if name not in self.skills_by_name:
            raise KeyError(f"unknown skill: {name}")
        return self.skills_by_name[name]

    def has_skill(self, name: str) -> bool:
        return name in self.skills_by_name

    def public_skills(self) -> list[Skill]:
        return [s for s in self.skills_by_name.values() if s.public]

    def production_stages(self) -> list[Skill]:
        return [self.skill(sid) for sid in PRODUCTION_STAGE_IDS if sid in self.skills_by_name]

    def resolve(self, name_or_alias: str) -> Skill:
        """Resolve a public skill name or compat alias to its Skill.

        Resolution priority: (1) public skill by name, (2) alias of a skill,
        (3) any skill by name. This ensures ``ppt-master`` resolves to the
        public ``deck-builder`` (which declares it as a compat alias) rather
        than to the private ``ppt-master`` backend, when both exist.
        """
        # (1) public skill by exact name
        cand = self.skills_by_name.get(name_or_alias)
        if cand is not None and cand.public:
            return cand
        # (2) alias of any skill
        for skill in self.skills_by_name.values():
            if name_or_alias in skill.aliases():
                return skill
        # (3) any skill by name (private backends)
        if cand is not None:
            return cand
        raise KeyError(f"unknown skill or alias: {name_or_alias}")

    def alias_map(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for skill in self.skills_by_name.values():
            for alias in skill.aliases():
                out[alias] = skill.name
        return out

    # --- contract accessors ---
    def contract(self, stage_id: str) -> StageContract:
        if stage_id not in self.contracts_by_stage:
            raise KeyError(f"unknown stage contract: {stage_id}")
        return self.contracts_by_stage[stage_id]

    def ordered_contracts(self) -> list[StageContract]:
        return sorted(self.contracts_by_stage.values(), key=lambda c: c.order)

    def transition(self, from_stage: str) -> tuple[str | None, dict[str, Any]]:
        contract = self.contract(from_stage)
        pol = contract.transition_policy
        return pol.get("next_stage"), pol


def _skills_root(repo_root: Path | None) -> Path:
    if repo_root is not None:
        return Path(repo_root) / SKILLS_SUBDIR
    # Default: walk up from this file (scripts/skills/manifest.py) to repo root.
    here = Path(__file__).resolve()
    # scripts/skills/manifest.py -> repo root is two parents up ... but skills/ lives at repo root.
    for parent in here.parents:
        if (parent / SKILLS_SUBDIR / MANIFEST_NAME).exists():
            return parent / SKILLS_SUBDIR
    # fall back to repo-root/skills assuming this file is under scripts/skills
    return here.parents[2] / SKILLS_SUBDIR


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _parse_skill(raw: dict[str, Any]) -> Skill:
    return Skill(
        name=raw["name"],
        path=raw["path"],
        role=raw.get("role", ""),
        public=bool(raw.get("public", False)),
        description=raw.get("description", ""),
        compat_aliases=tuple(raw.get("compat_aliases") or ()),
        input_types=tuple(raw.get("input_types") or ()),
        exit_artifacts=tuple(raw.get("exit_artifacts") or ()),
        stage_id=raw.get("stage_id"),
        backend_dependency=raw.get("backend_dependency", "") or "",
        public_name=raw.get("public_name"),
        raw=raw,
    )


def _validate_manifest_skills(manifest: dict[str, Any]) -> list[Skill]:
    skills_raw = manifest.get("skills")
    if not isinstance(skills_raw, list) or not skills_raw:
        raise ManifestError("manifest.json: missing non-empty skills[]")

    skills: list[Skill] = []
    names: set[str] = set()
    aliases: dict[str, str] = {}
    public_input_types: dict[str, str] = {}

    for idx, raw in enumerate(skills_raw):
        if not isinstance(raw, dict) or "name" not in raw:
            raise ManifestError(f"manifest.json: skill[{idx}] missing name")
        skill = _parse_skill(raw)
        if skill.name in names:
            raise ManifestError(f"duplicate skill name: {skill.name}")
        names.add(skill.name)
        for alias in skill.aliases():
            if alias in names or alias in aliases:
                raise ManifestError(
                    f"compat alias collision on '{alias}' (skill {skill.name})"
                )
            aliases[alias] = skill.name
        if skill.public:
            # input_types may be legitimately shared across public skills because
            # the route resolver disambiguates by runtime stage, not input_type
            # alone (e.g. ``page_tasks`` feeds both deck-sourcing and
            # deck-producer). We therefore do not hard-fail on shared
            # input_types; duplicate *names* and *aliases* remain hard errors.
            # See spec-deviation-log.md DEV-002.
            pass
        skills.append(skill)

    return skills


def _validate_contracts(
    contracts_doc: dict[str, Any],
    skills_by_name: dict[str, Skill],
    *,
    skip_jsonschema: bool = False,
    schema_path: Path | None = None,
) -> list[StageContract]:
    contracts_raw = contracts_doc.get("contracts")
    if not isinstance(contracts_raw, list) or not contracts_raw:
        raise ManifestError("stage-contracts.json: missing non-empty contracts[]")

    if not skip_jsonschema:
        _run_jsonschema(contracts_doc, contracts_raw, schema_path)

    contracts: list[StageContract] = []
    seen_stage: set[str] = set()
    seen_order: set[int] = set()
    for raw in contracts_raw:
        stage_id = raw.get("stage_id")
        order = raw.get("order")
        if stage_id in seen_stage:
            raise ManifestError(f"duplicate stage_id in contracts: {stage_id}")
        seen_stage.add(stage_id)
        if order in seen_order:
            raise ManifestError(f"duplicate stage order in contracts: {order} ({stage_id})")
        seen_order.add(order)
        # cross-reference: contract must map to a real skill (if it is a public skill)
        if stage_id in skills_by_name:
            skill = skills_by_name[stage_id]
            if skill.stage_id and skill.stage_id != stage_id:
                raise ManifestError(
                    f"manifest stage_id mismatch for {stage_id}: "
                    f"manifest={skill.stage_id} contract={stage_id}"
                )
        contracts.append(
            StageContract(
                stage_id=stage_id,
                skill_name=raw.get("skill_name", stage_id),
                order=order,
                lane=raw.get("lane", "production"),
                raw=raw,
            )
        )

    # 9 production stages must be fully covered, in order.
    expected = list(PRODUCTION_STAGE_IDS)
    got = [c.stage_id for c in sorted(contracts, key=lambda c: c.order)]
    for stage_id in expected:
        if stage_id not in seen_stage:
            raise ManifestError(f"missing production stage contract: {stage_id}")
    if got != expected:
        raise ManifestError(
            f"production stage order mismatch: expected {expected}, got {got}"
        )

    return contracts


def _run_jsonschema(
    contracts_doc: dict[str, Any],
    contracts_raw: list[dict[str, Any]],
    schema_path: Path | None,
) -> None:
    try:
        import jsonschema  # type: ignore
    except ImportError:  # pragma: no cover - jsonschema is a dev dependency
        return
    if schema_path is None or not schema_path.exists():
        return
    schema = _read_json(schema_path)
    validator = jsonschema.Draft202012Validator(schema)
    for raw in contracts_raw:
        errors = sorted(validator.iter_errors(raw), key=lambda e: e.path)
        if errors:
            first = errors[0]
            where = ".".join(str(p) for p in first.absolute_path) or "<root>"
            raise ManifestError(
                f"stage contract '{raw.get('stage_id')}' invalid at {where}: {first.message}"
            )


def _canonical_contracts_hash(contracts_doc: dict[str, Any]) -> str:
    """Stable sha256 of the contracts in canonical (sorted, compact) form.

    Used as a release lock value (A1 must-implement #5). Only the ordered
    contracts list participates, so cosmetic edits to wrapper fields do not
    invalidate the lock.
    """
    ordered = sorted(contracts_doc.get("contracts", []), key=lambda c: c.get("order", 0))
    blob = json.dumps(ordered, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def load_registry(
    repo_root: Path | str | None = None,
    *,
    skip_jsonschema: bool = False,
) -> Registry:
    root = Path(repo_root) if repo_root is not None else None
    skills_dir = _skills_root(root)
    manifest_path = skills_dir / MANIFEST_NAME
    contracts_path = skills_dir / STAGE_CONTRACTS_NAME
    if not manifest_path.exists():
        raise ManifestError(f"manifest not found: {manifest_path}")
    if not contracts_path.exists():
        raise ManifestError(f"stage contracts not found: {contracts_path}")

    manifest = _read_json(manifest_path)
    contracts_doc = _read_json(contracts_path)

    skills = _validate_manifest_skills(manifest)
    skills_by_name = {s.name: s for s in skills}

    # cross-reference: any manifest skill that declares stage_id must have a contract.
    for skill in skills:
        if skill.stage_id and skill.stage_id not in {c.get("stage_id") for c in contracts_doc.get("contracts", [])}:
            raise ManifestError(
                f"skill {skill.name} declares stage_id={skill.stage_id} but no contract exists"
            )

    # locate schema (docs/contracts/stage-contract.v1.schema.json relative to repo root)
    schema_path: Path | None = None
    search_roots = [skills_dir.parent, skills_dir.parent / "docs" / "contracts"]
    if root is not None:
        search_roots.insert(0, Path(root) / "docs" / "contracts")
    for candidate_root in search_roots:
        cand = candidate_root / SCHEMA_NAME if candidate_root.name == "contracts" else candidate_root / "docs" / "contracts" / SCHEMA_NAME
        if cand.exists():
            schema_path = cand
            break
    if schema_path is None:
        # final fallback: <repo>/docs/contracts/<schema>
        for parent in skills_dir.parents:
            cand = parent / "docs" / "contracts" / SCHEMA_NAME
            if cand.exists():
                schema_path = cand
                break

    contracts = _validate_contracts(
        contracts_doc,
        skills_by_name,
        skip_jsonschema=skip_jsonschema,
        schema_path=schema_path,
    )
    contracts_by_stage = {c.stage_id: c for c in contracts}

    return Registry(
        skills_by_name=skills_by_name,
        contracts_by_stage=contracts_by_stage,
        manifest_version=str(manifest.get("version", "")),
        suite_version=str(contracts_doc.get("suite_version", manifest.get("version", ""))),
        contracts_hash=_canonical_contracts_hash(contracts_doc),
    )


__all__ = [
    "Registry",
    "Skill",
    "StageContract",
    "ManifestError",
    "load_registry",
    "PRODUCTION_STAGE_IDS",
]
