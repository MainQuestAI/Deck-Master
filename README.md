# Deck Master

Deck Master 帮助解决方案作者、提案者、竞标者和分享者，**在真实需求与技术边界内，把复杂的事情讲简单，把抽象的事情讲具体。**

我们从讲述者的商业任务出发：这次要讲什么、表达什么判断、争取什么结果。受众的语言与经验用来校准表达。核心工作是理解需求、理清架构、提炼业务框架，并让它贯穿整套内容、场景与讲稿。

## 同一材料，形成适合这次任务的 deck

首次提案介绍会员系统，重点是改善什么、如何改善、具体怎样使用；竞标则突出对关键需求的理解、方案回应和有依据的优势。这样的变化应当改变内容的主线与取舍。

“钱、事、酒、账”代表我们追求的业务提炼能力：简洁名称背后有准确拆解，能展开回需求、能力、场景与边界，并统领完整方案。它不是固定四格模板，也不是靠生成口诀替代理解。

方法卡应帮助作者完成这种有效加工。视觉负责说明关系、变化和过程；PPT 和生成引擎负责稳定承载表达。当前工程提供本地优先的 Agent 工作台，通过 CLI 和本机 Web UI 连接内容、生成、可编辑 SVG/PPT、审查与返修。

详见[核心理念](docs/product-philosophy.md)。下一轮优先建设[商业表达能力与开发卡套件](docs/specs/deck-master-business-expression-20261029/README.md)：任务策略、业务框架、方法有效调用、全文贯穿和策略重编。**这些是待开发与验证的目标；排版优化及新输出引擎留待后续迭代。**

**Version:** Python package `1.0.0`, in release preparation. Published assets
and publication status are listed in [GitHub Releases](https://github.com/MainQuestAI/Deck-Master/releases).
Start with the [installation and first-run guide](docs/getting-started.md).
The [RC4 increment](docs/specs/deck-master-next-iteration-20261019/README.md)
and its [single ledger](tests/rebuild/fixtures/history/rc4/iteration-20261019/execution-ledger.json)
retain their original candidate evidence. A source version, built wheel,
active installation and published Release are separate facts.
The source includes the RC5 content-method catalog and bounded Host selection,
PR130's content/method/evidence reading and recoverable handoffs, plus support
and documentation governance. See the [release preparation record](docs/releases/1.0.0-preparation.md)
for validation scope and remaining publication steps.
**License:** Apache-2.0.

The core inherits RC4 extensions to the RC3 and Flow Quality contracts with recoverable input
and installation operations, frozen Task methods, scoped content validation
and negotiated reading contexts. Engineering checks, actual Host application
and professional/user acceptance are recorded separately.

The rebuilt core does not require a PPT Master backend binding, a slide
library installation, or any first-run workspace setup: a plain material
directory is enough to start. Legacy v0.9.x material and runs are handled by
the migration notes in [docs/migration-to-rebuilt-core.md](docs/migration-to-rebuilt-core.md);
the old command surface maps onto the new CLI per
[spec 09.6](docs/specs/deck-master-rebuild-v1/specs/09-cli-and-host-protocol.md)
(`deck-master legacy-map` lists every mapping).

## Who It Is For

Deck Master serves solution architects, proposal authors, bidders and presenters.
It aims to help them turn business understanding into a clear, coherent deck:
choose what matters for this task, organize a meaningful framework, and explain
the solution in language the audience can use. Existing content, review and
production workflows provide the foundation; the next increment develops and
evaluates the business-expression capabilities described above.

## Install

Python 3.11 and 3.12 are tested in CI. Package metadata permits Python 3.13,
which is outside the tested matrix, and excludes Python 3.14.
For a release installation, download its wheel and `release.json` together,
then follow [managed installation](docs/getting-started.md#install-a-release).
The commands below are for source development:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

If local Python cannot bootstrap pip in a venv, use the equivalent uv path:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

The only command surface is the rebuilt CLI: `deck-master ...` after install,
or `python -m deck_master ...` from a source checkout. Release activation also
registers all four Codex Skills (Master, Content, Design, Review); see [installation](skills/deck-master/references/installation.md).

## Quick Start

Use your own complete material and brief. The commands below are staged:
substitute IDs and hashes from the actual returned Task; do not paste the
angle-bracket placeholders as values.
They assume `deck-master` is on PATH, for example after activating the source
venv above. For a managed release, substitute the selected prefix's absolute
`.deck-master/bin/deck-master` launcher or add that directory to PATH first.

```bash
# 1. New projects default to workbench.v3, with instruction evidence and
#    proposal-only initial work; create does not grant production authority.
deck-master capabilities
deck-master create --brief-file ./brief.txt --source ./materials \
  --out ./my-deck --no-open
deck-master continue --project ./my-deck --no-open

# 2. Read the Task's exact frozen methods and complete source/context.
#    Use v2 only if capabilities.read_protocols declares it; otherwise omit
#    the read options for v1. v2 defaults to full bodies.
deck-master methods --project ./my-deck --task-id <task_id> --read \
  --read-protocol work_context.v2 --body-mode full

# 3. Claim the actual Task before executing it. Repeat --capability for
#    every required_capabilities value, declaring only actual Host support.
deck-master task start --project ./my-deck --task-id <task_id> \
  --execution-ref <actual_Host_execution> --supported-protocol <protocol_version> \
  --capability <required_capability>

# 4. Execute the returned scope, then submit its actual result envelope.
deck-master task accept --project ./my-deck --task-id <task_id> \
  --operation-id <operation_id> --produced-against <produced_against> \
  --result ./result.json
deck-master continue --project ./my-deck --no-open

# 5. Open readable work and export the selected purpose.
deck-master view --open --project ./my-deck
deck-master export --project ./my-deck --out ./out --purpose review
```

Follow each `continue` result: framing and argument are proposals, then
page_copy, applicable speech and reviews proceed according to the current
request. A `compose.v2` result uses `schema_version=compose_result.v2`, the
Task's variant/IDs/produced_against/eligibility_digest, and that variant's
payload; do not submit all phases as one draft. Inspect the actual
[result contracts](src/deck_master/resources/contracts/) and
[collaboration method](skills/deck-master/references/collaboration-routing.md).
When `continue` asks for a direction decision, record the real decision via
`collaboration decision --input decision.json`, then use
`collaboration adopt-proposal --input adoption.json` with the current CAS
and the exact proposal. A grant uses `collaboration grant` only when there
is actual covering authorization. A copied handoff or a claim is not approval.
Missing authority or a trusted independent review channel remains a named gap.

For content alone, pass `create --request-input request.json` with
`intent=content_only`, the requested `content_intent`
(`plan_only|write_only|speech_only|content_full`), actual scope and instruction
evidence. Follow `completion.state/outputs/checks/missing`; completed content
returns its requested artifacts without starting design or PPT. A confirmed
complete manuscript can use `create --draft draft.json` or `import-draft`
with its real import instruction and `imported_mapping`; it need not invent
a new Narrative. Teaching content need not contain a sales CTA.

For `full_deck`, continue only within the actual production scope. Generation
requires its frozen request, allocated call, begin → real tool call → settle
→ accept chain. Inspect actual original images and PPT previews, page and
final reviews, then run `final-readiness`, export `--purpose delivery`, and
check the actual exported PPTX with `handoff-check --purpose delivery`.
`review` can return an unfinished readable copy with its unresolved list.
`needs_tool` and `needs_reviewer` must retain their actual reasons.

Explicit local `--file` verification accepts stable regular files only, including
copies outside the project. Symlinks, devices, FIFOs and directories are refused;
the HTTP delivery checker does not accept local file paths. Reads are bounded by
known output lengths and checked again for replacement or growth.
Review-purpose `handoff-check` can identify an exact committed historical original
as `historical_output`, listing every matched revision and output reference. This
remains blocked for current delivery. Historical sanitized copies are not recreated
for identification. An incomplete history index is reported as a gap; a complete
index does not mean every historical PPTX body was reread—only matching originals
are byte-verified.

Personal-state clearing retains its operation and request before submission. If a
response is lost, reopen “个人状态与恢复” and use “核实并重试原清理”; the same request
is replayed and later drafts are preserved. Historical clear receipts without an
input digest remain readable and their backups usable, but cannot prove an exact
request replay; they are not treated as a new cleanup instruction.

Preproduction review reports preserve every blocking review record and expose
both `blocking_record_count` and `logical_finding_count`. The latter follows an
explicit same-owner replacement chain and never merges unrelated findings merely
because their local IDs match. The existing eligibility `open_findings` field
remains a record-count alias for compatibility; the UI labels the two counts
separately. Neither count relaxes the production gate.

Persist changed requirements or materials before continuing the same project:

```bash
deck-master inputs show --project ./my-deck
deck-master inputs update --project ./my-deck --patch update.json \
  --base-revision <original_revision_id> --operation-id <saved_unique_id>
deck-master operations show --project ./my-deck --operation-id <saved_unique_id>
```

After a lost response, preserve the original payload, base, ID and relative
path context. Exact replay returns the original result alongside the current
revision; use a fresh `continue` for current pending work. `unknown` does not
permit retrying under a new ID. New unchanged input updates may advance a
receipt-only revision while preserving Page/input basis and tasks. Ordinary
`inputs update` and `content inputs` have distinct ID/digest contracts. Read
[input recovery](skills/deck-master/references/input-update.md) before retrying.

The [N6 normal-task evidence](https://github.com/MainQuestAI/Deck-Master/blob/62dfcfc5637f0bee2358074c4458047689dd5299/docs/reports/rc4/iteration-20261019/N6-evidence.md)
preserves its original staged observations. Subsequent actual installed Host
validation at PR125 head `d7ec4530` completed native independent review,
two-page native-image observation, SVG/PPT, real rendering and formal delivery,
with `ready` and `handoff-check verified`. This is one observed complete task;
see the [validation scope and known limitations](docs/getting-started.md#known-limitations)
for the font workaround and unverified WPS editing.

## Workbench

For current use, follow the [installation and first-run guide](docs/getting-started.md).
The [RC3 tryout](docs/rc3-tryout.md) is a historical compatibility entry, not
the current installation or release instructions.

The workbench provides a project launcher, production overview, content and
sources, gallery, style calibration, tasks and delivery. Each page retains its
source, content, prompts, original image, SVG and PPT views. `deck-master view --open --project <dir>`
starts (or reuses) one loopback service per project.

The workbench is the only UI. The retired `/legacy/` interface and `--ui legacy`
option have been removed; existing project data and CLI workflows remain supported.

Workbench writes require a per-server session token and same-origin origin
check; reads are open on loopback. The server binds to `127.0.0.1` only.

## Capability Boundaries

The rebuilt core guarantees:

1. Real editable shapes and text in the produced PPTX (`editability=editable_shapes_and_text`); tables and charts are shape/text compositions, not Office-native data objects.
2. Honest status at every step: pending Host tasks show `awaiting_host` (never fake running); export `review` purpose ships unfinished decks with the real unresolved list; `delivery` requires passing current checks.
3. Renderer and font gaps surface as `needs_tool` with the actual reason.
4. The review workbench serves the four real views (content / blueprint / SVG / PPT) from project-relative objects only.

Professional human review and desktop-editing evidence stay `not_evaluated` until actually performed.

## Diagnostics

```bash
deck-master doctor --step compose   # content inputs
deck-master doctor --step render    # renderer toolchain (soffice/pdftoppm/rsvg-convert)
deck-master doctor --step export    # delivery-time checks
```

Renderer or font gaps are reported per step as `needs_tool` with the real
reason; nothing silently falls back to fixtures.

## Project Docs

Start with the [documentation index](docs/README.md) for user guides, inherited
engineering specifications and dated evidence. Historical reports do not certify
the current candidate; see the [archive index](docs/archive/README.md).

- [Installation, First Run, Host Requirements and Upgrade](docs/getting-started.md)
- [核心理念：从业务判断到商业表达](docs/product-philosophy.md)
- [下一轮商业表达能力：总方案与开发卡](docs/specs/deck-master-business-expression-20261029/README.md)
- [Agent Entry](AGENTS.md)
- [Agent Task Index](docs/agent-task-index.md)
- [Agent Recovery Playbook](docs/agent-recovery-playbook.md)
- [Inherited RC4 Increment](docs/specs/deck-master-next-iteration-20261019/README.md)
- [Migration to the Rebuilt Core](docs/migration-to-rebuilt-core.md)
- [Support and Feedback](SUPPORT.md)
- [Issue Maintenance](docs/issue-maintenance.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
