# Explicit Q2 helper v2: contract and verification

User-approved scope (2026-10-23 17:02 UTC): introduce a new verifier/test-helper version while retaining original identity and every security/freshness check. This supersedes the prior stop decision only for this explicit versioned work. No UI redesign, model execution, merge, release or credential changes.

## Version contract

The old controller.py, supplementary_recorder.py and q2_later_300.py remain byte-for-byte unchanged from 888c9c76. New controller_v2.py, supplementary_recorder_v2.py and q2_later_300_v2.py have their own file/hash bindings. New controls use rc3-q2-later-300-control.v2 and new supplementary registrations use rc3-supplementary-registration.v2. Persisted campaign data schema remains v1 where unchanged; it does not imply old executable identity.

| File | SHA256 |
| --- | --- |
| controller.py | d0b2b079afb7a714c4d7028b7e5eaa6be70cc0cef41db6c73d664c952f373261 |
| supplementary_recorder.py | afd3e419dcc88b631347250239d33d83dec5c9d4ea69b7429a9f868c7ef0771d |
| q2_later_300.py | c7515c4a8dc9e2a6e560502bd6d94e20f9cb8d41caa7f8463e102e28e3da6b54 |
| controller_v2.py | db94a7bb8008c0c55dfb6761703b831027904e563873599ca87a025180931d8b |
| supplementary_recorder_v2.py | 883232f3f06b0732b48a4014291cf3a5489936d91a27980e4f9c582a0810801c |
| q2_later_300_v2.py | f85dbd2ad0bb6c1d3395ffa0f1c6bd82e234e8ee9aaa46615770fa5547deafcd |

Old controls are not migrated or rewritten. V2 rejects old format and old tool/common/scoped references even when other fields declare v2. Formal historical run/registration hashes are not replaced or retrospectively approved. New real execution still requires valid new control admission; engineering fixtures are not Host evidence.

The same 70-case carrier selects v2 through three explicit fixture paths. Its assertions/cases are unchanged. Wrapper runs one -I -B child with the same 180-second limit and complete JUnit/identity checks. CLI isolation/override/no-Runtime-import tests now cover both old and new entrypoints.

## Allowed implementation changes

Within each installation() invocation only, retain root.parts/root_depth and the normalized relative key. Compare fully resolved path components against the full root prefix instead of constructing extra Path objects through is_relative_to. For entries produced by the original root.rglob traversal, form the lexical relative inventory string from the remaining path components. The tools already require POSIX facilities (fcntl); no new portability promise is made.

Keep the original traversal and its symlink policy, every resolve/is_symlink/read/hash, all inventory/missing/duplicate/escape checks, manifest/source/tree/wheel/interpreter/module checks, and every freshly observed installation identity. No filesystem or authorization observations are cached between calls. Fresh scoped and controller modules remain; only the prior immutable compilation cache is inherited.

File forks are explicit to preserve executable history rather than monkey-patching the fixed controller. Diff old/new implementations to review the small algorithm change independently of the full file copies.

## Evidence and limitations

Local same-case profile: v2 installation23 calls1.369841 seconds vs prior old23 calls2.393449; case call3.611814 vs4.856827. These are local profiler samples, not a controlled remote-run guarantee. First full wrapper/regression run29 passed106.01s; original70 outcome checks passed. Final expanded regression and fixed-head build identities are recorded separately after completion.

27 differential/identity tests cover repeated fresh file reads, same-size/same-mtime byte changes, add/remove, duplicate/absolute/parent paths, leaf symlink and parent/sibling escape, inside-parent alias inventory behavior, ignored bytecode, changed manifest bytes/metadata, interpreter/module/wheel and borrowed-module drift, B source/tree/wheel identity changes between calls, old control refusal, fresh modules, accepted module-path aliases, and mutation at the file-read boundary. Old/new results and failure classes/messages are compared.

An initial three old-binding probes failed at finite-scope validation because their synthetic control omitted required scope fields. Completing the fixture made them reach the intended binding rejection; assertions were not relaxed. Raw failed and corrected logs are retained. Focused wrapper+identity run39 passed/1 deselected. Final complete run includes these additions.

Original push CI failures and unknown PR-triggered status remain separate. There is no claim that local timing proves the remote 180-second issue resolved. Actual model, customer, rendering and S3 quality effects remain not_run for this increment.

Final source regression: 46 passed in 111.08 seconds, including the original 70-case child. Two final alias/read-boundary probes were then added; the expanded differential file passed all27 in0.60 seconds. The fixed-head installed regression below is required to cover the final combined set. No product code changed between these runs.
