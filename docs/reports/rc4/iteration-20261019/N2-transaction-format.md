# N2 installation transaction format and recovery

This is an installation control record, independent of Document, Task, receipts,
and project writer floors. Its implementation is
`src/deck_master/activation_transaction.py`; `install.py` retains release
verification, legacy manifest validation, Host preflight, and the activation
plan. There is one durable execution engine, replacing the in-memory Undo list.

## Record and lock locations

- `<prefix>/.deck-master/install.lock`: existing prefix lock, now opened through
  `store.locked_file` with regular-file and no-follow checks.
- `<prefix>/.deck-master/transactions/activation/<UUIDv4>.json`: sole authoritative
  `activation_transaction.v1` request, frozen plan, observed state, and receipt.
- `<prefix>/.deck-master/activation-pending.json`: version and transaction ID only;
  no copied plan. Missing pointers are repaired from the unique verified
  unfinished journal. Terminal journals remain terminal with a stale pointer.
- `<prefix>/.deck-master/.deck-master-pending-<UUIDv4>.before/.after`: retained
  pointer capture or unpublished pointer preparation. Cleanup captures rather
  than unlinks a pathname whose identity could have changed. A mismatching
  captured inode is restored without replacing an occupant, or retained as
  conflict evidence when restoration is occupied. Unrecognized captures block
  new activation rather than being interpreted as an absent pointer.
- `<Host skills>/.deck-master-registration.lock`: shared registration lock.
  Ordering is always prefix lock, then Host lock. Public paths and resources are
  preflighted again after acquiring the Host lock. The shared lock is retained.
- `.<deck-master>-<UUIDv4>-<step>.before/.after` (actual prefix is
  `.deck-master-`): adjacent backup and prepared item. Adjacent paths ensure
  same-filesystem rename even when Host and prefix are on different devices.
  The original validated legacy directory keeps its existing
  `legacy-companion-*` backup name instead.
- `.deck-master-<UUIDv4>-<index>.witness`: a retained same-filesystem hard link
  to each prepared symlink/file and existing watched symlink/file. These keep
  the original inode allocated even after an external unlink, including for
  unchanged public links and launcher. Witness identities and exact paths are
  frozen as `inode_anchors`; missing or changed witnesses are refused rather
  than recreated from a possibly substituted live path.

Directories and preparations are fsync'd before the prepared journal; JSON uses
`store._atomic_write_bytes` (file fsync, atomic replacement, parent fsync). Each
rename fsyncs its affected directories. No shell strings, pickle, or executable
callbacks are stored. Unknown versions, invalid or foreign IDs/prefixes,
unrecognized actions, escaped paths, and journal symlinks are refused and left
in place.

The inode witnesses close the same-content unlink/recreate gap exposed by three
Python 3.11 CI cases at `bc6bd55a07b249660e6af8ab4b19a147bb2caf14`.
Device/inode plus bytes can describe a recycled inode as though it were the
original object. Keeping a second persistent link prevents that inode from
being freed during the pending transaction. Legitimate rename and process-death
recovery retain this proof without depending on ctime, which rename may change.
Original failure assertions remain; deterministic lost/replaced-witness cases
also simulate equal recycled dev/inode and require conflict. Earlier failed CI
and pre-fix raw observations remain retained externally. An unfinished record
without the required witnesses is preserved and refused; an old terminal
receipt can still replay its historical result without a new ownership claim.

Preparation is now a durable `preparing` phase. The request, original managed
state and each `.after`/`.witness` intent are saved before creating the artifact;
its verified identity is saved afterward. Every pre-existing watched regular
file or symlink is witnessed before formal replacement `.after` creation.
Recovery derives the required set from the complete frozen `watched` state,
not from a nonempty or partial preparations/anchors list. Each required identity
must have a surviving witness. Death immediately after `Plan.begin`, before a
required intent is registered, or before its witness exists therefore returns
`installation_recovery_conflict` in `preparing`, preserving the original journal
and entire scene. Once the complete set is physically pinned, a process exit
between creation and identity persistence remains recoverable. The original ID
resumes after checking target resources, every old managed path/parent and all
already-proven preparation identities. Every registered witness,
including one with acknowledgement `identity=null`, must still match its frozen
`expected` inode identity: it keeps the old managed inode allocated. A missing
or replaced witness is a recovery conflict before any namespace is rebuilt;
neither a matching target nor a recycled live inode supplies the missing proof.
Ordinary unconfirmed `.after` residuals remain untouched and listed in
`preparation_history`; a fresh `preparation_id`
namespace prevents adopting or deleting them based only on a filename/target.
The request UUID stays fixed. New preparations never restart formal actions.
An interruption in this phase reports `preparing`; retry the original request.

The preparing reader retains the finite action/path boundary: migration can
only move `current` to a prefix-local `legacy-companion-*`, and exact legacy
retirements must match the live validated migration action set. Watched paths,
steps, intents and existing witnesses are validated even while preparation is
partial. Informational skipped entries can grow as retained preparations appear;
they do not change the frozen action domain. Escaped or invented migration
actions are refused before creating external witnesses or performing moves.

For a symlink Host skills directory, new plans bind the actual canonical
directory and separately freeze `host_access_path`/`host_access_identity` for
the original access ancestry. Locked actions use the verified actual directory;
the ancestry is checked during nonterminal recovery and before completion.
Existing `skill_link`/`skill_links` success fields keep the logical access path.
Terminal receipts remain historical and do not acquire a new alias-identity
requirement. Previous prepared records without these optional new fields still
use their frozen parent proof and request; they are not relabeled as preparing.
For these actual old records, request matching retains the original logical
Host path. A different logical Host request is refused even if both aliases
resolve to the same real directory. New records keep their canonical-root
binding. Matching a request is separate from proving its frozen parents and
action ownership; replay does not normalize or rewrite the old journal.

All transaction backup, publish, unpublish and restoration renames use one
atomic no-replace operation with a pinned adjacent parent directory descriptor.
The descriptor's device/inode must match the frozen parent. An external file,
symlink or directory appearing after the final path check is rejected by the
kernel and retained. Pointer publication uses the same no-replace operation;
an existing matching pointer is immutable and is not rewritten.

Linux uses `renameat2(RENAME_NOREPLACE)` as documented by the
[Linux manual](https://man7.org/linux/man-pages/man2/rename.2.html); macOS uses
`renameatx_np(RENAME_EXCL)` with the flag declared in
[Apple's header](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/stdio.h).
This run exercised Linux and its current temporary filesystem. The macOS path
has not been run here. Missing primitives and unsupported filesystems fail;
there is no check-then-overwrite fallback. A synthetic unsupported-filesystem
test verifies rollback without changing managed paths.

This does not serialize arbitrary noncooperating writers. A source swapped at
the syscall boundary can be moved into its unique retained backup/capture;
post-action identity checks then refuse ownership. Pointer cleanup restores a
racing replacement when the original slot is empty, otherwise preserves both
occupants and evidence. Process death during capture leaves the captured inode
retained. These tests establish destination non-overwrite and conflict recovery,
not a universal compare-and-swap operation on arbitrary filesystem entries.

## Frozen request and finite actions

The request records `verb`, normalized absolute `prefix`, target release ID and
SHA256 identity (release JSON plus the checked Host/installed resource bytes),
registration option, initially resolved Host root or null, and canonical UUIDv4.
Rollback freezes its target and original current/previous before applying.
Current/previous, original managed inodes, migration report, watched unchanged
paths, parent and ancestor identities, and planned result are frozen plan data,
not fields recomputed from the partially switched installation.

Finite mutation kinds are `link`, `launcher`, `remove`, and `move`. Parent
preparations are `mkdir` entries with their witnessed identity and retain policy.
Each mutation includes step ID, managed path, parent/ancestor identities,
`before`, `prepared`, `expected_after`, unique backup, `step_state`, and observed
proof. Snapshots include dev/inode/type; links also include their exact target;
launchers include bytes hash and mode. Validated legacy directories include
manifest identity/hash and entry names.

Replacements have a complete prepared inode and retain the original inode by
renaming it to the backup. Removal also renames to backup. Thus recovery can
prove ready, backed-up-but-not-published, and applied states even when the process
died before updating `step_state`. `apply_cursor` is persisted before dispatch,
so compensation handles an action whose filesystem change outlived its state
write and excludes actions never reached. Repeated paths during legacy
remove/re-register are restored in reverse order. A restored state write can
also lag its rename and be recovered by the same inode evidence.

`preparing -> prepared -> applying -> completed` is the success path. Exceptions and Ctrl-C
persist `compensating` before reverse restoration, then `rolled_back` only after
verifying the original managed paths and parents. Recovery of `compensating`
continues reverse restoration. Ownership/resource conflicts preserve
`recovery_conflict`, backups, preparations, and external contents; safe owned
steps still compensate. Failed persistence reports unknown/unavailable rather
than claiming rollback. Empty preparation parents and witnessed artifacts may
remain; no generic cleanup or journal pruning is introduced.

## Request and result behavior

Both `install activate` and `install rollback` accept optional
`--transaction-id <canonical UUIDv4>`. Same ID with a changed verb, activation
target, prefix, Host root, or registration option is refused. An unfinished
matching request resumes its original identity even without an explicit ID;
a different request reports `installation_transaction_pending`.

A completed explicit-ID retry returns its original receipt with `recovered=true`
and never switches current or previous again. A rolled-back ID returns its
original failure and verified rollback; use a new ID for another attempt.
Without an ID, a completed rollback followed by another rollback still uses the
now-current previous pointer to make a new switch. A rollback interrupted before
completion instead resumes its original frozen target.

Original success keys remain, with `transaction_id`, `transaction_state`, and
`recovered`. Historical `cli_active`/`host_skill` belong to the original receipt.
`observed_current_release_id` and `current_install_state` (`verified`,
`inconsistent`, or `unknown`) are separate current observations within the
request's registration scope. An opt-out observation verifies CLI only;
`host_unregistered` describes the registration option, not an inspection or
assertion that preserved Host links are absent.

Ctrl-C returns structured `installation_interrupted`, exit 130, ID and state.
Ordinary Python exceptions retain their original type and carry transaction
metadata; CLI maps their outcome to an installation failure with original type
and reason. Conflicts use exit 5; unverifiable journals/persistence use exit 4.
Conflict payloads retain affected paths, expected/observed identities, original
failure, and backup locations where applicable.

`--no-host-registration` never resolves the Host root, acquires its lock, scans
legacy Host links, or writes Host paths during preparation, applying,
compensation, recovery, or replay. It may still move the validated legacy
companion directory inside the installation prefix under the original contract.

## Validation boundary

N2 tests use fabricated releases, independent temporary prefixes, synthetic
Host roots, and dedicated child processes terminated with `os._exit(91)`.
They verify actual pointer/link/launcher inode, bytes, mode and durable state,
including action-before-log windows and compensation dying again. The broader
resource-inventory regression retains strict installed/wheel protections.

Original pre-second-review focused result: **290 passed, 0 failed/errors/skips** in
`N2-focused-junit.xml`. `N2-install-recovery-evidence.json` records source hashes,
the exact command, twelve AC-to-test mappings checked against that JUnit, and
47 separately collected child-process exits: 25 forward, 16 retirement,
5 compensation and 1 opt-out. Recovery verified 42 completed and 5 rolled-back
transactions. Every child exited at its requested breakpoint with code 91.
Both HOME and CODEX_HOME were explicitly isolated under each temporary fixture.
Published paths use `<fixture>`; raw observations remain outside the repository.
The repository JSON retains case identity, requested breakpoint/exit, recovery,
key inode/hash comparisons and focused proof/test mappings. Its raw artifact
index records the complete external JSON's SHA256 and size; full generated
installation trees and repeated journal snapshots are not included in Git.

The first collector attempt correctly failed because its previous/after_backup
case had no existing previous inode and never reached the breakpoint. The
collector fixture was corrected by first switching bare then old, producing an
actual previous backup action. The subsequent 47-case collection passed; no
implementation change or test-result substitution was made for that repair.

AC-N2-05 also requires the integration owner's canonical installation/recovery
wording. AC-N2-12's final candidate identity and installed-wheel/renderer gates
remain integration evidence. The JSON records passed engineering assertions,
not a second authoritative AC status ledger.

This evidence does not substitute for installed-wheel/renderer release gates,
actual power-loss testing, user HOME migration, loaded user Skills, or the
ability of an old binary to write a project whose writer floor was raised. N2
never reads or lowers a project's writer floor.

The second-review preparation-witness/request fixes have297 source passes,
47 actual child91 windows (42completed/5rolled_back), and242 real new-wheel
installed passes with candidate/historical import identities kept separate.
See [second-review evidence](N2-review2-evidence.json) and
[the new installed regression](Installed-review2-N2.json); these retain the
original failure history and do not relabel the earlier290/build evidence.

The third review found the empty/partial witness-coverage gap. Its complete-set
repair has309 source passes and254 actual new-wheel installed passes, including
12 new coverage negatives;47 actual child91 windows still recover42completed/
5rolled_back. See [third-review resolution](PR124-review3-resolution.md),
[evidence](N2-review3-evidence.json) and [installed proof](Installed-review3-N2.json).
Original first-witness negatives and the five initial fixture failures are
retained; sufficiently proven last-unconfirmed-witness recovery stays positive.
