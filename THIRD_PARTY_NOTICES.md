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

- `frontend/` and `deck-skill/` contain first-party Deck Master assets except
  for the third-party adaptations and licensed assets identified below.
- No font binaries are bundled or required; fonts resolve from the host system
  at compile/render time (see `docs/getting-started.md`).
- Compiler geometry functions carry first-party provenance headers extracted
  from the pinned B0 baseline; see `compiler-extraction.json` in the spec pack
  and the headers in `deck-tools/src/deck_tools/compiler/geometry.py` / `native.py`.

This inventory is maintained per release candidate; it is not a claim of a
completed third-party legal audit beyond the package metadata above.

## Lucide 1.49.0 icon subset

24 offline SVG assets under `deck-tools/src/deck_tools/resources/icons/lucide/`. Upstream: https://github.com/lucide-icons/lucide/tree/1.49.0. Full ISC and applicable Feather MIT copyright/permission notices are retained in `LICENSE.txt`; `manifest.json` records source URLs and SHA-256.

## Humanizer expression-review adaptation

`deck-skill/references/expression-review-humanizer.md` adapts selected
editorial guidance from [blader/humanizer](https://github.com/blader/humanizer/tree/8c307f367c91bd974002f10f2be2965d642c13df),
SKILL version 3.1.0, commit `8c307f367c91bd974002f10f2be2965d642c13df`.
Copyright (c) 2025 Siqi Chen; MIT License. The canonical reference includes the
complete upstream copyright and license text plus SHA-256 hashes of the fixed
SKILL.md, README.md and LICENSE. The four role Skills share this reference from `deck-skill/references/`.
This is a bounded Chinese PPT adaptation, not an installed third-party Skill.

## CyberPPT select_icon

Only `scripts/select_icon.py` and `scripts/test_select_icon.py` are bundled in
`deck-tools/src/deck_tools/vendor/cyberppt/`, under the MIT License.
Copyright (c) 2026 CyberPPT contributors

Source repository / committer: [crazyykhllc-bit/CyberPPT](https://github.com/crazyykhllc-bit/CyberPPT),
commit `980e557`; crazyykhllc-bit is identified as the source committer.
The verbatim license is in that directory's LICENSE; SOURCE.md records original
file hashes, adaptations and the files not ported. The native generator starts
from a first-party project script and is not CyberPPT code.

## Tabler Icons v3.46.0

The outline set only is bundled in
`deck-tools/src/deck_tools/resources/icons/tabler-outline/`.
MIT License; © 2020-2026 Paweł Kuna.
[Upstream](https://github.com/tabler/tabler-icons/tree/v3.46.0/icons/outline),
commit `8ac7d81b72ece11072ef25ea9fd92e80c6f3c9fc`.
LICENSE retains the full upstream copyright and permission notice;
manifest.json records the source and file inventory.

## pptxgenjs 4.0.1

[Upstream](https://github.com/gitbrent/PptxGenJS/tree/v4.0.1), MIT License,
Copyright (c) 2015-2022 Brent Ely.
The exact runtime dependency is pinned in `deck-tools/native-pptx/package.json`
and package-lock.json. npm installs its upstream LICENSE with the dependency.
