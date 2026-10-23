# Second review: isolated native-review subprocess provenance

Independent review baseline: `fdb8fca959a40d54e8cc2e4881533473a1838657`.
Fix: `092bb984`; installed CI inclusion: `2f6072cc`.

The receipt-survival regression launches `python -I -m deck_master`. `-I`
ignores PYTHONPATH, so a parent preloaded from a wheel does not establish that
its child uses the same installation. Before this increment the test did not
check either module provenance or installed version.

The regression now probes the same interpreter with `-I` from its isolated
working directory and compares actual package root, package code version and
installed distribution version(s) with the parent. Distribution discovery is
anchored to that interpreter's purelib, avoiding cwd metadata ambiguity. It
then runs the original CLI command and preserves its receipt/state assertions.
No child sys.path/PYTHONPATH injection or isolation bypass is used.

Deterministic negative check: parent preloaded from the 9b7a22f6 wheel, child
using the existing editable interpreter, is rejected with both actual roots.
Both report code version 1.0.0; this demonstrates why version alone is inadequate.
The old interpreter's installed distribution reports 1.0.0.dev2, while querying
metadata from repository cwd had reported 1.0.0. Neither is hidden as a wheel
installation result.

Source check: `PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider
 tests/rebuild/test_native_review.py` — **11 passed in 3.12s**.

Matching wheel check: isolated temporary venv installed the exact 9b7a22f6 wheel
(the product source is unchanged by the two test-only commits), invoked with
`python -I`, preloaded its installed parent, and ran that same test file —
**11 passed in 3.59s**; all **59** loaded runtime modules belonged to that venv's
site-packages. Parent and child both used the actual 1.0.0 wheel. This was a
synthetic receipt/transport test, not a real model call. The matching source and
Skill inventory and wheel SHA are in RP-24-settled-reuse.md.

The existing installed CI gate now includes the native review suite, so its
subprocess provenance is checked under the actual wheel interpreter. Current
second-review head has not been pushed; no new remote CI result is claimed.
Normal dependency download succeeded for this temporary test venv. No HOME,
Host registration, credentials or security settings changed.
