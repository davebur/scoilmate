# ScoilMate: existing-solutions preflight
Checked 2026-11-14; evidence and access limitations in [source register](09-sources-and-evidence.md). No installation or external write performed.

| Option | Strength | Fit decision |
|---|---|---|
| Moodle LMS | Maintained full learning platform, question banks, quizzes, roles and feedback | Strong alternative if Dave relaxes stack. Official 5.3 requirements list PHP and database servers, not SQLite. Too much operational/product scope for requested FastAPI/embedded MVP. |
| H5P self-hosted open technology | Reusable interactive content and browser authoring; active 2026 maintainer news | Worth reconsidering for richer content later. It needs a supported host/integration and does not alone solve ScoilMate accounts, server-authoritative attempt tracking or curriculum review. Do not confuse open H5P with paid H5P.com. |
| Static notes plus forms | Minimal operational burden | Could validate lessons without collecting personal data; does not meet private versioned learning-history requirement. |

Custom planning is appropriate because Dave specified FastAPI/Uvicorn, local embedded storage and a narrow tailored experience. This is not a claim that Moodle lacks the features. Revisit Moodle if school administration becomes the primary product.

## Reuse rather than invent
Proposed, not installed or pinned: FastAPI/Pydantic validation; Uvicorn ASGI; Starlette request/cookie primitives; Jinja2 autoescaping; SQLAlchemy 2.x relational access; Alembic migrations; pwdlib with Argon2id (or argon2-cffi); pytest/httpx and browser accessibility tests later. Use Python secrets for opaque tokens. Standard library sqlite3 is the driver. No JWT requirement for same-origin browser sessions.

FastAPI has no complete built-in accounts/admin/CSRF system. Evaluate maintained session/CSRF and MFA libraries against the security contract before implementation; do not copy a stale package because of its name. Starlette SessionMiddleware is signed client-side readable session data, not the proposed revocable server-side store. Verify dependency support, licence, advisories, release activity and Python compatibility when creating the eventual lockfile. No version numbers in this plan are a production dependency pin.
