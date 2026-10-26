# Personal clear recovery storage

`ui_clear_closure.v2` separates the small terminal marker from the complete
recovery evidence. Ordinary local JSON, including pre-deletion clear backups,
retains its 2,000,000-byte limit. A valid near-limit backup must still be endable.

Under the existing ordered clear locks, end rechecks the caller's inspection
digest, writes the canonical v1 recovery bundle into
`workbench/clear-evidence/<sha256>.json`, verifies its exact bytes, then atomically
writes the v2 marker in `workbench/clear-closures/<operation_id>.json`. Both are
personal state under `.deckmaster`; neither is a business object or revision.
Only the final marker fences late commits. Each atomic write synchronizes the
file and parent directory. An interrupted evidence write or marker write must
not return an ended receipt; orphan evidence is retained and is not a terminal
fact. Existing content-addressed evidence is verified, never overwritten.

The evidence reader uses a safe digest-derived path, no-follow regular-file
open, exact length, and chunked SHA-256 verification before JSON/schema parsing.
It spools verified bytes rather than reopening the path. This dedicated evidence
format has no aggregate small-state limit: a backup plus complete request and
inspection may exceed that limit, including later personal-state growth. Disk
or parsing failures remain explicit failures; no evidence is discarded to make
end succeed. The marker retains the normal small-state limit.

V1 inline terminal records remain readable without migration. New markers bind
project/operation identity, request and inspection digests, evidence length/hash,
and end time. Inspect/end HTTP and CLI results, recovery listings and full v1
JSON downloads keep their existing public shape. Corrupt/missing evidence cannot
release a terminal fence or masquerade as success. Old executables that only
recognize v1 refuse a v2 marker, rather than executing its old operation.


A clear-backup manifest slot may legitimately belong to another operation.
Inspection first validates its complete manifest and every record, then classifies
ownership. With no receipt or backup owned by the requested operation, inspection
remains `no_execution_evidence`, not proof that the request never ran.
`backup.available` describes only the requested operation. The optional
`backup.related_operation` contains the other operation ID, manifest digest,
complete backup digest, and count; this is included in the confirmation digest.
Ending rechecks this evidence under the existing clear locks. It preserves the
other operation's original backup/receipt and stores only its attribution summary
in the requested operation's inspection; the closure's own `backup` remains null.
Existing backup listing/download still serves the other operation's backup.
Malformed, foreign-project, duplicate, or hash-mismatched records remain
unverifiable. A valid own success receipt remains authoritative even when its
backup slot now holds another valid operation's backup.
