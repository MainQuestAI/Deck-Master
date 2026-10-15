"""T04 slice 2: the entry inventory is machine-checked (AC-R04).

The test enumerates the real entry surface — service.py's public functions,
every ``operations.public`` wrapper, the CLI subcommand tree and the ``/api``
route literals — and requires each entry to be classified in
``eligibility_entries``: either it consumes a registered eligibility action, or
it carries an explicit exemption reason. A newly added route, command or public
operation therefore fails here instead of shipping as an unguarded bypass.
"""
import pytest

from deck_master import eligibility, eligibility_entries as entries

SURFACE_MINIMUMS = {"service": 15, "operations": 40, "collaboration": 14,
                    "cli": 60, "http": 80, "public": 19}


def test_no_unclassified_entry_on_any_surface():
    assert entries.uncovered() == {}


def test_inventory_matches_the_codebase():
    """No dead rows: every classification still names a real entry."""
    assert entries.stale() == {}


def test_surface_discovery_finds_the_real_entries():
    """Guards the guard: a broken discovery must fail loudly instead of
    silently reporting an empty (and trivially passing) surface."""
    surfaces = {
        "service": entries.service_surface(),
        "operations": entries.operations_surface(),
        "collaboration": entries.collaboration_surface(),
        "cli": entries.cli_surface(),
        "http": entries.http_surface(),
        "public": entries.public_surface(),
    }
    for surface, discovered in surfaces.items():
        assert len(discovered) >= SURFACE_MINIMUMS[surface], (surface, len(discovered))
    assert {"create", "accept_result", "inputs_update", "open_blueprint_task"} <= surfaces["service"]
    assert "changes.commit" in surfaces["operations"]
    assert "collaboration.grant" in surfaces["collaboration"]
    assert "task call begin" in surfaces["cli"]
    assert "/api/changes/commit" in surfaces["http"]
    assert {'legacy.import_legacy', 'registry.create_project', 'samples.create_sample',
            'samples.create_gallery_sample'} <= surfaces['public']


def test_every_classification_is_either_gated_or_explicitly_exempt():
    for row in entries.inventory():
        assert bool(row.action) != bool(row.exempt), row
        if row.gated:
            assert row.action in eligibility.ACTIONS, row
            assert row.gate and row.gate != "-", row
        else:
            assert row.exempt in set(entries.READ_REASONS.values()), row
            assert row.gate == "-", row


def test_write_surfaces_are_gated_not_exempt():
    """The high-risk write boundaries from CONTRACTS §6.2 must consume a real
    action: creation/routing, fees, adoption, change, local production and
    delivery — never an exemption."""
    required = {
        ("service", "create"): "create",
        ("service", "continue_project"): "continue_project",
        ("service", "open_compose_task"): "dispatch.compose",
        ("service", "open_host_task"): "dispatch.host_task",
        ("service", "open_blueprint_task"): "dispatch.blueprint",
        ("service", "import_draft"): "import_draft",
        ("service", "import_asset"): "asset.import",
        ("service", "update_design"): "design.update",
        ("service", "inputs_update"): "content.inputs_update",
        ("service", "task_start"): "task.start",
        ("service", "accept_result"): "task.accept",
        ("operations", "changes.commit"): "change.commit",
        ("operations", "candidates.adopt"): "candidate.adopt",
        ("operations", "styles.propose"): "style.propose",
        ("operations", "styles.confirm"): "design.update",
        ("operations", "content_ops.commit"): "content.operation",
        ("operations", "exports.create"): "export.delivery",
        ("operations", "restoration.commit"): "restore",
        ("operations", "stages.assemble"): "stage.assemble",
        ("cli", "task call begin"): "call.begin",
        ("cli", "task call allocate"): "allowance.allocate",
        ("cli", "export"): "export.delivery",
        ("cli", "handoff-check"): "handoff.delivery",
        ("cli", "build"): "compile.ppt",
        ("cli", "edit"): "page.edit",
        ("http", "/api/changes/commit"): "change.commit",
        ("http", "/api/candidates/adopt"): "candidate.adopt",
        ("http", "/api/exports"): "export.delivery",
        ("http", "/api/inputs/update"): "content.inputs_update",
        ("http", "/api/feedback"): "dispatch.host_task",
        ("http", "/api/cancel"): "task.cancel",
    }
    for (surface, name), action in required.items():
        row = entries.classify(surface, name)
        assert row is not None, (surface, name)
        assert row.action == action, (surface, name, row)
        assert row.exempt is None


def test_a_new_unclassified_entry_fails_the_check(monkeypatch):
    """The mechanism itself: a new write route with no row is reported."""
    real = entries.SURFACES["http"]
    monkeypatch.setitem(entries.SURFACES, "http",
                        (lambda: {"/api/changes/commit", "/api/brand-new-write"}, real[1]))
    assert entries.uncovered() == {"http": ["/api/brand-new-write"]}
    # Registering an explicit exemption clears it again.
    monkeypatch.setitem(entries.HTTP_ENTRIES, "/api/brand-new-write",
                        (None, "-", entries.READ_REASONS["ui_state"]))
    assert entries.uncovered() == {}


def test_exempt_reasons_are_a_closed_vocabulary():
    reasons = {row.exempt for row in entries.inventory() if row.exempt}
    assert reasons <= set(entries.READ_REASONS.values())
    # Every registered reason is actually used somewhere (no orphan labels).
    assert set(entries.READ_REASONS.values()) <= reasons


def test_inventory_actions_cover_the_contract_boundary_table():
    """Every CONTRACTS §6.2 boundary action is either consumed by a classified
    entry directly or explicitly mapped to the entries that carry it."""
    direct = {row.action for row in entries.inventory() if row.gated}
    boundary = ("create", "import_draft", "continue_project", "dispatch.compose",
                "dispatch.host_task", "dispatch.blueprint", "task.start",
                "allowance.allocate", "allowance.repair", "call.begin",
                "generation.dispatch", "task.accept", "page.edit", "asset.import",
                "design.update", "change.plan", "change.commit", "candidate.select",
                "candidate.adopt", "style.trial", "style.expand", "content.operation",
                "compile.svg", "render.preview", "compile.ppt", "compile.repair",
                "export.delivery", "handoff.delivery", "readiness.final", "restore",
                "policy.update", "authority.update", "delivery.historical")
    for action in boundary:
        assert action in eligibility.ACTIONS or action in eligibility.ROUTING_ACTIONS, action
        assert action in direct or action in entries.BOUNDARY_VIA, action
    # The via-mapping names real classifications.
    rows = {f"{row.surface}.{row.entry}" for row in entries.inventory()}
    for action, carriers in entries.BOUNDARY_VIA.items():
        assert carriers, action
        for carrier in carriers:
            assert carrier in rows, carrier


def test_coverage_stats_are_reported():
    stats = entries.coverage_stats()
    assert stats["total"] == stats["gated"] + stats["exempt"]
    assert stats["gated"] >= 90
    assert stats["by_surface"]["http"] >= 80
    for action in stats["actions"]:
        assert action in eligibility.ACTIONS


def test_each_runtime_http_action_has_a_method_specific_classification():
    from deck_master.collaboration_api import HTTP_ROUTES, http_action
    discovered = entries.http_surface()
    for (method, template), action in HTTP_ROUTES.items():
        canonical = method + ' ' + template
        assert canonical in discovered
        row = entries.classify('http', canonical)
        assert row is not None, canonical
        dispatch = entries.classify('collaboration', f'collaboration_api.invoke[{action}]')
        assert dispatch is not None
        assert (row.action, row.exempt) == (dispatch.action, dispatch.exempt), canonical
        concrete = template.format(project_id='fixed-project', authorization_id='fixed-authorization')
        bound = http_action(method, concrete)
        assert bound is not None and bound[1] == action
        actual = entries.classify('http', method + ' ' + concrete)
        assert actual is not None and (actual.action, actual.exempt) == (row.action, row.exempt)
    assert entries.classify('http', 'GET /api/projects/fixed/collaboration/migration').exempt
    assert entries.classify('http', 'POST /api/projects/fixed/collaboration/migration').action == 'migration.apply'
    assert entries.classify('http', '/api/projects/fixed/collaboration/migration') is None


def test_actual_cli_dispatch_actions_match_their_registered_gates():
    actual = entries.cli_adapter_actions()
    assert {'collaboration grant', 'collaboration pause', 'collaboration resume', 'collaboration revoke',
            'eligibility', 'review evaluate', 'review import'} <= set(actual)
    for command, action in actual.items():
        cli = entries.classify('cli', command)
        dispatch = entries.classify('collaboration', f'collaboration_api.invoke[{action}]')
        assert cli is not None and dispatch is not None
        assert (cli.action, cli.exempt) == (dispatch.action, dispatch.exempt), (command, action)
    assert entries.classify('cli', 'import legacy').action == 'create'


def test_new_core_public_creation_and_import_are_gated():
    for name in ('legacy.import_legacy', 'registry.create_project', 'samples.create_sample', 'samples.create_gallery_sample'):
        row = entries.classify('public', name)
        assert row.action == 'create' and row.exempt is None
    assert entries.classify('public', 'project_initialization.adopt_manuscript').action == 'import_draft'
    for name in ('collaboration_region', 'instruction', 'request_defaults', 'imported_plan', 'prepare_manuscript'):
        row = entries.classify('public', 'project_initialization.' + name)
        assert row.action is None and row.exempt == entries.READ_REASONS['internal']
    assert entries.classify('http', '/api/projects/create').action == 'create'
    assert entries.classify('http', '/api/projects/sample').action == 'create'


def test_strict_external_evaluation_is_exempt_but_persistent_review_import_is_gated():
    for surface, name in [('collaboration', 'external_review.evaluate'), ('cli', 'review evaluate'),
                          ('http', 'POST /api/reviews/evaluate')]:
        row = entries.classify(surface, name)
        assert row.action is None and row.exempt == entries.READ_REASONS['external_report']
    for surface, name in [('collaboration', 'review_import.import_report'), ('cli', 'review import'),
                          ('http', 'POST /api/projects/fixed/reviews/import')]:
        row = entries.classify(surface, name)
        assert row.action == 'review.import' and row.exempt is None
    assert entries.classify('http', 'POST /api/projects/fixed/reviews/bindings').exempt == entries.READ_REASONS['read_model']
    assert entries.classify('http', 'POST /api/projects/fixed/continue').action == 'continue_project'
    assert entries.classify('http', 'POST /api/projects/fixed/draft/import').action == 'import_draft'


@pytest.mark.parametrize('route', [
    '/api/projects/new-project/collaboration/new-write',
    'POST /api/projects/new-project/collaboration',
    'POST /api/projects/new-project/collaboration/authorizations/auth/revoke/escalate',
    'GET /api/projects/new-project/reviews/import',
    '/api/changes/brand-new-write', '/api/content/brand-new-write', '/api/styles/brand-new-write',
])
def test_unknown_descendants_never_inherit_a_prefix_read_exemption(route):
    assert entries.classify('http', route) is None


def test_discovery_catches_new_parameterized_runtime_routes(monkeypatch):
    from deck_master.collaboration_api import HTTP_ROUTES
    route = ('POST', '/api/projects/{project_id}/collaboration/new-write')
    monkeypatch.setitem(HTTP_ROUTES, route, 'grant')
    assert entries.uncovered() == {'http': ['POST /api/projects/{project_id}/collaboration/new-write']}


def test_discovery_catches_new_dispatcher_actions_even_before_frontend_wiring(monkeypatch):
    from deck_master.collaboration_api import _FIELDS
    monkeypatch.setitem(_FIELDS, 'unclassified.new_write', set())
    assert entries.uncovered() == {'collaboration': ['collaboration_api.invoke[unclassified.new_write]']}
