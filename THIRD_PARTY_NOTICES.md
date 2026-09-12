# Third Party Notices

Deck Master source is licensed under Apache-2.0. The native PPTX kernel is
extracted from this repository's high-density implementation; it does not
bundle the external PPT Master product or its workflow.

## Python runtime dependencies

`pyproject.toml` and `requirements.txt` declare the same four direct runtime
dependencies. They are required for native production, not optional inspection
helpers. Installed distributions retain their own license files and notices.

| Dependency | Purpose | Package license metadata |
|---|---|---|
| [python-pptx](https://github.com/scanny/python-pptx) | Native editable PPTX compilation and structural readback | MIT |
| [Pillow](https://github.com/python-pillow/Pillow) | Image loading, measurements and render comparison | MIT-CMU |
| [NumPy](https://github.com/numpy/numpy) | Pixel and geometry measurements | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| [jsonschema](https://github.com/python-jsonschema/jsonschema) | Runtime input/output contract validation | MIT |

The production release installs the exact versions and verified wheel hashes in
`requirements/runtime.lock` and `requirements/build.lock`, including transitive
and build dependencies. Its `.venv/dependency-install.json` records the actual
platform wheel filename, SHA-256, installed version and locally built project
wheel hash. Source development dependency ranges do not override these locks.

The locked runtime also includes lxml (BSD-3-Clause), XlsxWriter (BSD-2-Clause),
typing_extensions (PSF-2.0), attrs, referencing, jsonschema-specifications and
rpds-py (MIT). The build environment includes pip and setuptools (MIT), and
wheel with its bundled notices. NumPy and other binary wheels can carry
additional native-library notices. Installed license files remain authoritative;
the summary license labels do not replace them.

`docs/specs/sc1.1-native-deck-core/implementation/dependency-provenance.json`
records the inspected macOS arm64 Python 3.12 distributions and the hashes of
their retained license files. This inventory identifies a tested distribution,
not a claim about untested wheel platforms. Reinstall verification compares
the actual selected distribution hashes independently on Python 3.11 and 3.12.

## Host tools and separately installed components

LibreOffice, Poppler (`pdftoppm`), librsvg (`rsvg-convert`), fontconfig and
Noto Sans SC are discovered on the host and exercised by runtime probes.
They are not copied into Deck Master's source release tree. Host installation
and redistribution retain each component's original terms and notices.
PPT Library is an optional separately installed backend with its own source,
version and component evidence; its installation is not a transfer of its
license to Deck Master's Apache-2.0 license.

## Development and verification

pytest, coverage, Playwright and Ruff are declared in `pyproject.toml[dev]`.
They support tests, browser verification and static checks. They are not
required to author and compile a native production deck after runtime setup.
