# Release Python dependency locks

`runtime.lock` pins the complete production dependency closure. `build.lock`
pins pip, setuptools and wheel. All accepted distribution hashes are from
non-yanked wheels in the official PyPI version JSON API. Source archives are
not accepted. The Python interpreter and its bundled ensurepip are the bootstrap
trust boundary; the installed pip is replaced with the pinned wheel before
building Deck Master. LibreOffice, pdftoppm and fonts remain separately probed
host tools, not Python dependencies.

Release build copies both locks and includes them in SHA256SUMS and the capability
lock. Installation checks those checksums before fetching packages. pip downloads
with `--require-hashes --only-binary=:all:` from PyPI; every selected wheel is also
checked against its metadata and lock digest before offline installation. The
local project is built with `--no-build-isolation --no-deps --no-index` using the
pinned tools, then installed without resolving dependencies. `pip check` and exact
installed-version comparisons must succeed. The receipt lives at
`.venv/dependency-install.json`, including the actual wheel names and SHA256s.

Update these locks intentionally: choose versions satisfying pyproject.toml and
Python 3.11/3.12, retrieve `https://pypi.org/pypi/NAME/VERSION/json`, and record all
non-yanked `bdist_wheel` digests. Review version changes and run clean duplicate
installations for each supported interpreter plus compiler/render regressions.
Multiple platform wheel hashes allow pip's platform selection; they do not prove
that every platform has been tested. A platform without a matching wheel fails
closed. The current real validation platform is macOS arm64.

SHA256SUMS protects consistency with a trusted release, not authenticity against
an attacker who replaces both the lock and its manifest. Release distribution
must retain its existing source/release provenance verification.
