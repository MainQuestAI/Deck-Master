# Third Party Notices

Deck Master is licensed under Apache-2.0.

## Runtime Dependencies

The current Python runtime dependency list is intentionally small:

| Dependency | Purpose | Declared In |
|---|---|---|
| python-pptx | Optional PPTX inspection and graceful-degradation checks | `requirements.txt`, `pyproject.toml` |

## Development And Test Dependencies

| Dependency | Purpose | Declared In |
|---|---|---|
| pytest | Contract and schema tests | `pyproject.toml[dev]` |
| jsonschema | JSON schema validation tests | `pyproject.toml[dev]` |
| playwright | Optional Review Desk browser smoke | `pyproject.toml[dev]` |
| coverage | Test coverage reporting | `pyproject.toml[dev]` |

Before a stable release, regenerate this inventory from the lockfile or packaging metadata and verify license compatibility.

