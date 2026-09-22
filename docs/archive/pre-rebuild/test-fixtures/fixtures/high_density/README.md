# High-Density Synthetic Fixture

This fixture is source-controlled, synthetic, and customer-safe. It covers the
seven first-release page classes used by the high-density builder acceptance:
framework, process, table, comparison, architecture, data story, and dense
narrative.

`fixture.json` is the deterministic content seed. `blueprint.svg` is the
frozen 16:9 composition input used by hermetic tests. The test converts the
seed into valid Page Packages with a fixed run id before invoking the builder.

The distinct acceptance test uses `distinct_blueprint_01.svg` through
`distinct_blueprint_07.svg` and maps them to framework, process, table,
comparison, architecture, data story, and dense narrative scene layouts.

No customer names, source files, private claims, or production annotations are
included.
