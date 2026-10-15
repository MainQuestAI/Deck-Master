# RQ-05-M02-PLANNED-ID — register M02 before actual Pages exist

Original RC3 AC-M02 requires one fixed Narrative and two complete sequential
live/read uses in one project, followed by a bounded notes edit of the original
live version. Its prospective production scope must be fixed before first
output. This is a narrow recorder correction within RC3-05 work 6/7/8 and
AC-M02's version/current-control evidence, not a new product quota or Runtime
feature.

Exact d61/b982 `validate_m02_policy` compares actual leaf `page_id` values with
planned live/read IDs. A policy correctly containing null actual IDs is rejected
before M02 initialization, although the actual Pages do not yet exist. Preserve
that failure and its metadata-only seam; do not fabricate future SDK Pages,
Requests, rights or approval to make initialization succeed.

Match each use's stable `page_label` to its preregistered Page IDs, with distinct
labels across both uses. Permit null `page_id`; a nonnull value must equal that
leaf's own planned ID. Retain exact use/cap/instruction/installation/protocol
checks. Actual begin/preparation/dispatch guards, counters and shared locking
remain unchanged. No change to Runtime, methods, d0/d9/bf or M02 recorder
business logic, and no mutation of existing registrations or experiment data.

Meaningful regressions cover pre-Page registration/initialization with null,
partial and complete bindings; incorrect/swapped nonnull IDs and cross-use
borrowing refused without charges; and an unbound policy requiring an actual
SDK Page/claim/frozen Request/allowance/Attempt before a single charged dispatch.
Engineering observation/install seams remain explicit. No model/image call or
formal M02 effect is claimed. Freeze a separate commit for independent review
and re-review; previous code reviews and CI retain their exact source identity.
