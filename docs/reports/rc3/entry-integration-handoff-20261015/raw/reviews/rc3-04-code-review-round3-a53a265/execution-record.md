# Execution record

The actual finite execution is retained in `run-focused.sh`, `probe_f9_and_c6.py`, both logs and complete JSON results. Commands used the exact dedicated interpreter with explicit `PIP_NO_INDEX=1`, `PIP_FIND_LINKS=/workspace/work/rc3/wheelhouse` and `PYTHONDONTWRITEBYTECODE=1`. No activated older environment supplied imports. No render toolchain or network was needed.

Static comparison command:

```bash
git -C /workspace/work/rc3/reviews/rc3-04-code-snapshot-a53a265 diff 573a46a85bf93d71a13652756bc3a6cdb1fab6ae a53a265321ca6bb15f347bbe23b5143fe8b7378c --
```

The complete output is `full-delta.patch`; all 52 paths are in `changed-files.json`. Focused file reads and unchanged dependencies were cross-checked against the fixed snapshot. `assertion-delta.json` is a mechanically collected old/new AST-assertion inventory; the report records semantic assessment rather than treating assertion counts as coverage. `r2-closure-reuse.json` records exact matching R2/R3 bytes for the 14 unchanged dependency modules. No R2 failure or report was overwritten.

Own probe uses actual `service.create`, `read_skill_methods`, `samples.create_sample`, `service.inputs_update`, `Store` and read-only `run_desk.task_row`. `create_sample` supplies an explicitly synthetic two-page software fixture; it is not real human/native evidence. It grants no authority through the summary function. No product monkeypatch or implementation fixture helper is used by this own probe.

The four selected existing tests use their fixed-source explicit L1 fixtures. They do not run a browser despite their containing module's name. The actual source files and imported Task contracts are covered by the source identity manifest. No installed source/package or build output is substituted for this source-runtime execution.

Final read-only identity check is `capture_identity.py`, with complete output in `source-identity-verification.json`. Before and after include all 3622 tracked contents, HEAD/tree, clean Git status, actual interpreter/module/version. The R1/R2 report SHA256 values are independently checked before freezing this review's evidence manifest.
