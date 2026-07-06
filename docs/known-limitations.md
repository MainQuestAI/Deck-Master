# Known Limitations

Deck Master is currently a public Technical Preview.

## M1 Technical Preview

M1 guarantees a local fixture demo and Review Desk preview path. It does not guarantee a full production deck build unless production companion backends are configured and verified.

Current M1 boundaries:

1. Fixture demo is the default first-run path.
2. Production backend status must be checked through `setup-status`, `suite-status`, or `backend status`.
3. If `ppt-master` or `ppt-deck-pro-max` bridge is not configured, production commands should block instead of reporting ready.
4. Browser smoke depends on local Playwright/browser availability.
5. The public demo uses synthetic retail transformation content.

## M2 RC Requirements

Before formal RC, Deck Master must also close:

1. Production external dependency handling.
2. Review Desk full design-system alignment.
3. Localhost write-operation token or origin checks.
4. Release tree install, verification, and rollback evidence.

