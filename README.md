# Deck Master

Deck Master is a local-first, agent-operable solution-deck workbench: from a
brief and real source material it drives content composition, blueprint
generation, editable SVG/PPT production, review and repair — all through one
CLI and a loopback review workbench.

**Status:** RC4 development candidate, Python package `1.0.0rc4`.
Read the [current increment](docs/specs/deck-master-next-iteration-20261019/README.md)
and its [single candidate ledger](docs/reports/rc4/iteration-20261019/execution-ledger.json)
for verified scope and remaining gaps. A source candidate, built wheel,
isolated installation, active user installation and public Release are separate facts.
**License:** Apache-2.0.

RC4 extends the existing RC3 and Flow Quality contracts with recoverable input
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

Deck Master is built for solution architects and proposal builders who need a repeatable way to decide which pages should be generated, which pages should be reused, and which pages are ready for review or delivery.

## Install

Python 3.11 and 3.12 are supported (`requires-python >=3.11,<3.14`); use
either as the default. Python 3.14 is not a supported test environment because
the PPTX dependency chain may not have compatible wheels yet.

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
final reviews, then run `final-readiness` and export `--purpose delivery`.
`review` can return an unfinished readable copy with its unresolved list.
`needs_tool` and `needs_reviewer` must retain their actual reasons.

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

The [N6 normal-task evidence](docs/reports/rc4/iteration-20261019/N6-evidence.md)
records the actual staged path and its remaining adoption/review gaps; it is
not a claim that this candidate has completed an end-to-end delivery.

## Workbench

RC3 的功能试用与口播说明保留在
[RC3 功能进度与试用](docs/rc3-tryout.md)，其记录属于该候选时点；当前状态见 RC4 台账。

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

- [Agent Entry](AGENTS.md)
- [Agent Task Index](docs/agent-task-index.md)
- [Agent Recovery Playbook](docs/agent-recovery-playbook.md)
- [Current RC4 Increment](docs/specs/deck-master-next-iteration-20261019/README.md)
- [Migration to the Rebuilt Core](docs/migration-to-rebuilt-core.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
