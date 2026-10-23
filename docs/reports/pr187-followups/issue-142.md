# #142: reuse the exact current poll observation

PR187's passive control refresh previously issued a second summary read after every poll. The poll's response is now passed to refreshCurrentWork and reused only when project, artifact revision and current control revision all match. Historical reading, a concurrent mutation/control change or missing usable observation still reads a fresh summary. Existing navigation generations, passive-read serials and response identity checks remain; no authorization or mutable facts are cached across polls.

Actual Chromium: both 30-page frontends idle for 16 seconds retain the original exact three summary / three project reads across startup and one poll. Negative tests cover historical artifact, changed control, no observation and a superseding navigation generation. Independent review also checked personal-reading updates and a late navigation response. Combined #133/#142 independent targeted suite: 12 passed. This is not a claim about sustained full CPU load or concurrent-overlap performance, which the original reproduction did not establish.

No polling interval, timeout, read-count assertion or product safety check was relaxed. Fixed-HEAD package/install and CI results are recorded separately.
