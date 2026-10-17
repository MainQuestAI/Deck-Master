# S12 independent source and engineering evidence review — 2026-10-17

**Verdict: LIMITED_ENGINEERING_PASS. No confirmed new P1/P2 finding within the reviewed repository contract and exercised engineering scenarios.** This is not original-contract completeness, formal M02 admission, final managed installation, product quality, PowerPoint, Owner/audience, or release acceptance.

The reviewer did not modify source, tests, expectations, Runtime guards, Skills, grants, or PRs. The sole executed test command was an independently started, serial ordinary S12 pytest after the implementation owner explicitly stopped their tests. No model, image tool, renderer, paid service, formal project or actual actor invocation was started. No observer private key file was inspected, copied, hashed, or included in this report.

## Reviewed identities and scope

- Main reference: `43d4bc8ccbd1850564e9391c84e98db3c424eae4`.
- PR120 inherited parent: `48ee08616ec3ad977302c8c34556f2608cad1130`.
- Initial independent S12 candidate: `7c8edea7538645a89d712b671e37b976daf9e386`.
- Reviewed fixed candidate: `54b974e7551d4eea59586fc1cb9fc8daa701355f`, branch `codex/rc3-cloud-resume-20261017`.
- Read first: `AGENTS.md`, `docs/agent-task-index.md`, `docs/agent-recovery-playbook.md`, `docs/specs/deck-master-v1.0.0-rc3/task-cards/RC3-S12.md`, and `tools/rc3_campaign/M02-IMAGE-TRANSITION.md`.
- Read the S12 companion, fixture, installed probe, evidence helper, pytest entry and dedicated workflow; traced relevant inherited implementations in `controller.py`, `image_controller.py`, `image_event_controller.py` and `m02_runtime_continuation.py`.
- Relative to the PR120 parent, only the nine S12 files are added/changed. Source Runtime, Skills, frozen original helpers and `.github/workflows/rebuild.yml` are unchanged. The fixed commit changes only four of those S12 files. The reviewed six executable/test/workflow byte hashes were unchanged before and after independent execution.

## Findings and reasoning

No new P1/P2 is established by the available source or independent execution. In particular:

1. **Original helper path compatibility.** `m02_image_transition.py:72` resolves the original registered controller and primitive refs, checks their pinned hashes, derives the exact event-controller sibling and checks its frozen hash. `original_epoch` delegates load to that original module. Both `mark` (`:496`) and `seal` (`:524`) now call the original module's bootstrap primitive, satisfying its original sibling-path check. Registration, old `installations.B`, and inherited helpers are not rewritten. The fixture at `rc3_m02_image_fixture.py:227` deliberately puts original helpers in a separate directory, so the positive and negative Runtime scenarios exercise the formerly failing condition.
2. **Same ledger, finite budget and current consumer checks.** `validate` binds the original canonical root and immutable predecessor, global44/M02parent4/live2/read2/leaves, same S11 successor, and exact status/installation/admission refs. `current_scope`, `actual_task` and `rights` check the real current Request/instruction/phase, actual exhausted live roots, original read pool, Task/claim, methods, packet/application evidence, frozen request, allowance and Attempt. Forward commands gate inherited whole/phase/role caps through `require_effective_budget`; charging also gates global/parent/scope/leaf caps. Operational Root barriers remain explicitly host attestations, not cryptographic retirement of old processes.
3. **Lost ACK and unresolved outcomes.** The one grant attempt binds directly to an immutable successful `sdk_outcome`; a committed grant with no recorded outcome stays blocked and cannot be retried or replaced. Task origins likewise derive from actual recorded SDK results. Unfinished successor/transition SDK intents and an unsealed, unsettled or unknown prior read dispatch block later consumption. Query only calls the actual `generation.show` for the stored Attempt and reconciles matching `tasks.call_settle` intents. It does not retry a grant, resolve another mutation, import a receipt or refund an image.
4. **Native authentication and retained facts.** The scoped provider inherits the original provider ID/protected transport, checks the original authenticated seal, and supplies the original bytes to the actual native registry. The companion uses the original recorder's internal HMAC operation; it does not introduce a new key or caller-selected receipt/context. Raw first callbacks are frozen before validation; malformed first input remains immutable. The role-overrun scenario confirms raw/consumed SDK facts are retained while adoption is refused at 13/12.
5. **Fixture and interpreter fixes.** The fixture now declares both actual live Pages before submitting them, leaving the ordinary SDK scope guard intact. The nested venv exposes the parent venv site directory through one plain `.pth` path; it does not execute the parent's `.pth` files. Its own installed Runtime precedes that dependency path. The probe compares the complete installed Runtime/resource inventory with its own wheel and Source and checks loaded Runtime module paths after every scenario. The independent observed identity has `source=null`, `install=null`, packaged methods, isolated execution and bytecode disabled; it does not imply managed candidate admission.
6. **Workflow.** The dedicated workflow retains the reserved S12 branch trigger, read-only permission, all five Python compile/lint targets, ordinary pytest, serial child and always-upload public evidence. Moving `${{ runner.temp }}` from job `env` to the test step's `env` removes the invalid context location. The original seven-job workflow is unchanged. This reviewer did not certify a remote workflow result.

## Independent execution

Command (one serial run):

```text
RC3_S12_EVIDENCE_ROOT=/workspace/rc3-recovery-20261017/independent-s12 .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/rebuild/test_rc3_m02_image_transition.py --basetemp=/workspace/rc3-recovery-20261017/independent-tests --junitxml=/workspace/rc3-recovery-20261017/independent-s12.xml
```

Observed result: **12 passed in 58.15s**. The own-wheel child executed all six scenarios with **81/81 checks passing and 524 function observations**. The child was `-I -B` and loaded `deck_master` exclusively from its own prefix. Its actual public installation identity reports `metadata_version=1.0.0rc3`, packaged method bytes, `install=null` and `source=null`.

| Scenario | Function observations | Observed scope |
| --- | ---: | --- |
| positive | 127 | Two exact PNG adoptions; original live2 plus read2 retained; settlement lost ACK recovered only by exact query; no replay/refund |
| unknown | 91 | Actual SDK unknown remains charged; next read leaf blocked |
| bad-callback | 86 | Malformed first raw bytes retained; no replacement/refund/next Task |
| grant-lost-ack | 59 | Actual committed grant with absent transition outcome remains blocked; no new pool/Task |
| grant-durable | 60 | Durable actual outcome restores original binding; Task uses exact returned root; no second pool |
| role-overrun | 101 | All 13 production observations count; actual image fact retained; adoption refused at inherited 12 cap |

Evidence:

- `/workspace/rc3-recovery-20261017/independent-s12.log`
- `/workspace/rc3-recovery-20261017/independent-s12.xml`
- `/workspace/rc3-recovery-20261017/independent-s12/own-wheel-14e53eafaa3c4c0198b89862685090e8/probe/result.json` — 93467 bytes, SHA256 `649ffad6646a6644a97dc4a8a9d2f95ea7a2e10c97b3a43b30a328b691385825`.
- Its adjacent `identity.json`, `checks/`, `functions/`, `refusals/`, `source-inputs/` and public `neutral-workspaces/` contain the actual observations. The private IG key root is pruned before evidence enumeration; only named public IG files/directories are copied.
- The independently built wheel SHA256 is `204dcd273d5286496124742200123350f5d99c96a43437e3e2c52f4cbefd6e57`; wheel ZIP metadata can differ from the owner's build, while the probe enforces complete member byte equality against its installed Runtime and Source.

The implementation owner's earlier r2 report independently of this reviewer has 12 passed in 37.29s and the same six scenario/81-check/524-observation totals. Its result SHA256 is `152f4ca25951ccc29b2f791c9a974ee1272f7dfbe06f30c2a3de2dc076cbc592`. It is supporting evidence, not a substitute for this run.

Historical failures remain present: `s12-r0.log` records missing `pytest` in the own venv (1 failed, 11 passed); `s12-r1.log` records the original pinned-sibling bootstrap refusal (1 failed, 11 passed). Neither has been relabelled as passing or removed.

## Limits and remaining blockers

- **Original S12 prospective contract not recovered.** Neither `Root-S12-prospective-M02-companion-card.json` nor the cited `m02-prospective-controller-02/prospective-companion-cards.json` was available in the repository/recovered evidence provided to this reviewer. The claimed 13595-byte/SHA256 `d1f401a9d500a05edbf991f42f808db033ea5c76b99aa4750f7f414382ebcec4` contract was not read. The parent reported no usable historical-thread read tool. Original-contract completeness therefore remains **UNVERIFIED**, pending an authorized persistent copy; the repository prose has not been treated as a replacement.
- The separately cited historical full S11 export report at `/dev/shm/rc3-new-work-20261016/s11-independent-R2-v34dqa5k/report.final.json` is absent in this environment. This reviewer has not recertified that report or its reuse clarification. The new fixture openly uses a public content-only export plus synthetic L1 current-read/history/observer premises. It emits `new_S11_full_export_or_formal_M02=false` and `managed_candidate=false`.
- The neutral 12x8 PNGs, invocation/observer facts, prereview, historical rows and administrative Root assertions are synthetic test inputs. SDK writes, authorization/Task/Attempt IDs, own-wheel Runtime, native authentication and acceptance are actual engineering execution. There are zero actual model/image/actor/render calls. This run supplies no product-effect or formal-budget consumption evidence.
- Formal same-root M02 continuation still requires original persisted state, genuine full-live-export → release → next-read chain, exact final managed installation admission/review, remaining legal budget and actual Root observations. Human Owner/audience and PowerPoint acceptance remain separate and outstanding.
- Dedicated/ordinary remote CI outcomes and PR120 integration are owned by the parent; no merge, release or PR update was performed by this reviewer.

## Frozen executable/test/workflow hashes

| Path | SHA256 |
| --- | --- |
| tools/rc3_campaign/m02_image_transition.py | d89b5171385e1f70b624a0aa469329ad6128300300f9aeae3d985f21055db22e |
| tests/rebuild/rc3_m02_image_fixture.py | 86fed708ddfb77500f299dad7d250ca0204e71223268c5e8b912fa540a2ede2c |
| tests/rebuild/rc3_m02_image_installed_probe.py | 40f457e4e777663b13d6c08efe384221a254ec30d42265dd5c687599b13c9045 |
| tests/rebuild/rc3_s12_evidence.py | 3a470d7a761ed161fa3f9964f48d1e72a5eb4cefa62e93a1bdc8b196a676ff2e |
| tests/rebuild/test_rc3_m02_image_transition.py | 78988c830c73acf87aa6ebdce2f128e4e5ced63b4fa2bfdded461e42895815f8 |
| .github/workflows/rc3-s12-validation.yml | be8c714d2bc51c018a0fe8b4bafabefeb4952b6f4a20b1b7768c95ff713096df |
