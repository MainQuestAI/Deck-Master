# Initial helper inspection

Inspected helper SHA-256: `a37e861d5abb12dca199197fbb4807a3742deb84797ebea461c36b807257dcc9` (`observe-native-ppt-initial.py`). Verdict: **REQUEST_CHANGES for two observation guard gaps**, not an actual product or rendering failure.

1. Preview reloads the project through the SDK, while the helper initially saved an earlier SVG. The original postconditions did not preserve p04 blueprint/SVG slots or verify that the returned preview derived from that exact SVG. A concurrent update or an already-present stale preview could therefore mismatch the paired observation.
2. Compilation retained readback findings, but did not check that rendering yielded exactly one page or expose a combined mechanical result in the root observation. `completed=true` by itself could be read as successful verification even when readback failed or the renderer returned no pages.

Both findings were immediately sent to Root before execution. This reviewer did not run the helper, any project writer, compilation or rendering. SDK signatures and current fields were independently inspected read-only. The original helper and its actual source bytes remain preserved; later edits do not turn this initial inspection into a PASS.
