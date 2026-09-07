# Installation Scope

The central release owns code and bundled skills. Codex project discovery uses
`<project>/.agents/skills` links into the active central `current` tree.
Upgrades and rollback move the central tree; the links remain stable.

From a validated source checkout, install/upgrade the central release and its
global links with the existing command:

```bash
python3 scripts/deck_master.py suite-install --target codex --scope global --include-optional
```

To add a project to an already verified central release:

```bash
deck-master suite-install --target codex --scope project --project-root <project> --links-only --include-optional
deck-master suite-status --target codex --scope project --project-root <project> --output json
deck-master validate-skill --target codex --scope project --project-root <project>
```

The default `auto` scope discovers the nearest ancestor containing a
`.agents/skills/deck-master` entry, including broken links for diagnosis;
otherwise it uses global discovery. Explicit `--scope global` checks global
installation even inside a project. `--agent-skill-dir` selects a custom root
and cannot be combined with `--scope` or `--project-root`.

Project installations expose 18 entries including optional skills. They keep
the `ppt-master` compatibility document in the central release and route build
work to `deck-builder`. A same-named standalone production skill is independently
owned; its files and configuration are preserved. Backend certification is a
separate status from discovering the suite compatibility document.

To remove only suite-owned links from a project:

```bash
deck-master uninstall-skill --target codex --suite --scope project --project-root <project>
```

Real directories and foreign links survive removal; foreign links are reported
as blocked. The central release is retained. Single `uninstall-skill` remains
available for removing only the main Deck Master entry.

For upgrade, execute `suite-install` from the new source or release tree. Use
the same scope/project arguments to refresh those links; `--links-only` attaches
to the current release and does not upgrade it. Verify the current `REVISION`
and the scope returned in `suite-status.installations`. `release-rollback`
restores the previous central release for every linked project.

Migration order: validate in isolation, install the new central release, add
project links, check inside/outside discovery and run smoke, then remove global
suite links only when the user has authorized that switch. Global entries
remain visible outside projects until removed. Keep standalone PPT Master.
