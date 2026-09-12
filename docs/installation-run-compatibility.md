# Installed software rollback and Run compatibility

The managed `~/.deck-master/bin/deck-master` entrypoint keeps its compatibility
check outside the versioned `current` / `previous` software trees. A release
manifest declares `supported_run_formats`; the launcher compares that declaration
with the Run's native route and committed revision schema before invoking the
active runtime. The check does not depend on Git commit IDs.

After rollback to a release that does not support the Run format, write commands
return `RUN_FORMAT_READ_ONLY` without invoking the historical writer. `build
status` and `workflow status` return `legacy_read_only`, the committed revision
identifier, and unsupported formats. This response is compatibility status and
must not be interpreted as build or delivery readiness. Upgrade the software to
continue working with the Run; no downgrade or conversion of Run files occurs.

Use the managed entrypoint after rollback. Directly executing an old source
checkout or its `scripts/deck_master.py` bypasses the installed compatibility
check. The installer does not modify historical source or customer Runs.

Installation, failed upgrade, rollback, and suite uninstall preserve external
skill directories and project data. Removing a suite only removes its owned
links; independent `ppt-*` directories and their assets remain external.

The process-recovery tests use real POSIX `SIGKILL`, separate writer processes,
and fresh recovery interpreters. They distinguish pre-commit rollback from
post-commit receipt recovery; a Python exception alone is not process-death
evidence. Python 3.11 test runs that exercise installed releases need a prepared
Python 3.12 environment, selected with `DECK_MASTER_PYTHON`, because managed
releases require Python 3.12 and their runtime dependencies.
