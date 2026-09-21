# Third Party Notices

Deck Master is licensed under the Apache License, Version 2.0 (see LICENSE).
Copyright 2026 MainQuestAI (see NOTICE).

## Runtime Dependencies

Versions below are the ones installed in the development environment used for
the rebuilt core (spec pack v1.1); regenerate from `pip show` / the lockfile
before each release.

| Dependency | Installed Version | License (per package metadata) | Purpose |
|---|---|---|---|
| python-pptx | 1.0.2 | MIT | Native PPTX container writing for the SVG→PPT compiler |
| Pillow | 12.3.0 | MIT-CMU (Pillow License) | Raster metrics for text layout; PNG/JPEG asset verification; render triage |
| numpy | 2.5.3 | BSD-3-Clause (and MIT/Zlib/CC0-1.0 components per metadata) | Numeric support in the Pillow dependency chain |
| jsonschema | 4.26.0 | MIT | Contract schema validation for documents/pages/artifacts |

## Development And Test Dependencies (not shipped to runtime users)

| Dependency | Installed Version | License (per package metadata) |
|---|---|---|
| pytest | 9.1.1 | MIT |
| coverage | (dev venv) | Apache-2.0 |
| ruff | (dev venv) | MIT |
| playwright | (dev venv, optional browser smoke) | Apache-2.0 |

## Bundled Non-Code Resources

- `src/deck_master/resources/static/` and the packaged `skill/` copy are
  first-party Deck Master assets.
- No font binaries are bundled or required; fonts resolve from the host system
  at compile/render time (see `docs/migration-to-rebuilt-core.md`).
- Compiler geometry functions carry first-party provenance headers extracted
  from the pinned B0 baseline; see `compiler-extraction.json` in the spec pack
  and the headers in `src/deck_master/compiler/geometry.py` / `native.py`.

This inventory is maintained per release candidate; it is not a claim of a
completed third-party legal audit beyond the package metadata above.
