# CyberPPT source record

Source repository / committer: https://github.com/crazyykhllc-bit/CyberPPT / crazyykhllc-bit.
Commit: `980e557`. License: MIT; see LICENSE.

Only these files were ported (SHA-256 of the original bytes):

- `scripts/select_icon.py`: `999b35c9eac609e5ddd5b4816587c865a05efef8cee3728a7db712d0bfb9ae31`
- `scripts/test_select_icon.py`: `7497563e85fa7493c315df8be23b3dd76b9eeb543ff46260d4d3e32764c01908`

Deck changes: select_icon indexes a flat outline directory as well as the original library subdirectories; sync accepts that flat directory. The original test is unchanged.

Not ported: measure_blueprint, compare_render, compare_merged_render, validate_pptx, qa_gate, rework, merge, inspect_pptx_objects, CyberPPT assets/icons.

Rule documents were not ported or included in the Skill reading path. Source locations only:

- https://github.com/crazyykhllc-bit/CyberPPT/blob/980e557/SKILL.md#L1-L1040 (commit `980e557`, lines 1–1040)
- https://github.com/crazyykhllc-bit/CyberPPT/blob/980e557/references/ppt-production.md#L1-L679 (commit `980e557`, lines 1–679)
- https://github.com/crazyykhllc-bit/CyberPPT/blob/980e557/references/quality-assurance.md#L1-L402 (commit `980e557`, lines 1–402)
