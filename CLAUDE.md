# Deck Master — Claude entry

Read [AGENTS.md](AGENTS.md) first, then the
[intent index](docs/agent-task-index.md) and the current task's method or
[RC4 increment](docs/specs/deck-master-next-iteration-20261019/README.md).
They define the same Runtime, contracts, scope and recovery rules used by
other Hosts. Claude has no separate installation or approval policy.

Inspect the actual checkout, interpreter and deck-master doctor results.
Use rg for local files and symbols. An optional search index is useful only
after its availability, source and freshness have been checked; no clone
implicitly has one.

Use the actual loaded Skill and its matching Runtime. Task methods come from
the frozen manifest; a changed basis requires the documented recovery path.
Return completed content or bounded samples at their requested scope.
Review stays read-only, and a role name does not create independent identity.

No local service, fixed port, launchd job or deployment is assumed.
Start the loopback workbench through the documented CLI only when needed.
Push, merge, releases and activation follow the user's actual authorization.

The former machine-specific instructions are preserved as
[historical maintainer guidance](docs/archive/maintainer-environment/CLAUDE-before-rc4-20261019.md).
They describe a past setup and are not prerequisites for this checkout.
