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

The inspected `0cfbe54` macOS Python 3.12 release additionally resolved these
transitive dependencies: lxml (BSD-3-Clause), XlsxWriter (BSD-2-Clause),
typing_extensions (PSF-2.0), attrs, referencing, jsonschema-specifications and
rpds-py (MIT). Platform wheels may include further native libraries; their
bundled license files remain authoritative. These labels are an inventory,
not a replacement for those notices or a claim about an uninspected wheel.

Release verification records actual installed versions and license-file
hashes. This historical inventory does not pin future dependency resolution;
use the installed release's metadata and lock evidence for its exact versions.

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
