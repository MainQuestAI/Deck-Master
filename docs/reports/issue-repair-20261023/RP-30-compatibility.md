# Fixed integrated compatibility receipt

Source: `dd424554284f881a1ce76c0f3323cbcbcc37bace`, checkout
`/workspace/deck-rp02`, branch `codex/rp30-final-c6`. No source changes,
package builds/installations, model calls, customer material or remote writes.

## Actual command and result

```sh
PYTHONPATH=src /workspace/Deck-Master/.venv/bin/python -m pytest -q -rs tests/rebuild/test_rp19_asset_inputs.py tests/rebuild/test_rp20_original_review.py tests/rebuild/test_design_entry_basis.py tests/rebuild/test_rc3_adopted_design_handoff.py tests/rebuild/test_styles.py tests/rebuild/test_selective_content_review.py tests/rebuild/test_review_owner_scope.py tests/rebuild/test_selective_requirements_integration.py tests/rebuild/test_rp14_effective_requirements.py tests/rebuild/test_audience_register_review.py tests/rebuild/test_native_review_recovery.py tests/rebuild/test_review_graph_reuse.py -m 'not render'
```

**141 passed in 69.93s**, no failures/skips. Log:
`/tmp/rp30-dd424554-c6.log`. `test_styles` includes all runtime schemas having
exactly one byte-identical documentation mirror.

## C6 format matrix — what this run establishes

|Format|Registration and binding/freeze|Local output or actual consumption|
|---|---|---|
|PNG/JPEG Logo/images|PASS synthetic originals: exact bytes/format/ref, explicit selection, permission checks, immutable frozen references and omission rejection|PASS local native compiler: resulting PPTX zip media bytes equal stored selected original. NOT_RUN real ImageGen/visual observation.|
|WebP image|PASS actual decoder + original bytes/ref freeze and original-review packet|No claim of native PPTX embedding; that path supports PNG/JPEG. Actual ImageGen NOT_RUN.|
|SVG Logo|Explicitly rejected as direct selected image attachment; no implicit rasterization|UNSUPPORTED in this direct-attachment flow; no actual model or renderer acceptance.|
|TTF/OTF font|Existing metadata registration is distinct from image attachment; selected font attachment rejected|Installation, actual model use or font embedding NOT_RUN; no added fonts or HOME changes.|
|PPTX template|No template asset kind/master binding introduced|UNSUPPORTED master reuse, NOT_RUN template output. Text extraction is not template consumption.|

## Cross-card compatibility

- Original image review accepts standard authenticated **synthetic** owned
  observations without requiring SVG, but rejects unknown/untrusted/wrong
  identity or basis, cancelled/late results and unchanged pixels claimed as a
  known endpoint-error fix. No professional/model visual result is claimed.
- RP-12 expanded scope retains exact narrower historical owners and closes an
  actual synthetic old finding only after relevant Page change/recheck.
  Same-page and nonintersecting isolation are tested.
- RP-14 effective requirements plus RP-12 selective review: new speech-only
  requirement causes speech-only recheck while valid old conclusions remain.
- RP-16 page_copy checklist and finding/gate integration, blank-vs-unexecuted
  distinction and Page→packet→design→freeze identity pass at synthetic layer.
  #174/#179 actual-image closure remains BLOCKED.
- RP-11 recovery retains original execution/proof/consumption; damaged,
  cross-project, cancelled, stale or expired proof rejects.
- RP-19 history without selection marker reads unchanged; changed selected
  bytes/permission affect the consumer, unrelated assets/audit timestamp isolate.
- RP-21 exact ordered reference and original-image-preview preparation checks
  included; no extra visual approval inferred.

Real rsvg rendering remains BLOCKED (no installed rsvg-convert), not tested or
installed in this run. Browser/desktop image acceptance NOT_RUN here. Parent
owns matching package installation on this exact code; not duplicated.

## C4/channel follow-up on the same unchanged SHA

```sh
PYTHONPATH=src /workspace/Deck-Master/.venv/bin/python -m pytest -q -rs tests/rebuild/test_review_channel_discovery.py tests/rebuild/test_rc4_content_review.py tests/rebuild/test_rc4_work_context.py
```

**85 passed in 10.77s**, no failures/skips;
`/tmp/rp30-dd424554-methods.log`. Confirms stage/capability distinctions,
frozen/legacy method manifest handling, scope-bound readers, reissue and credit
ceilings after the original-review stage addition. It does not establish a real
Host session or actual independent model inspection.
