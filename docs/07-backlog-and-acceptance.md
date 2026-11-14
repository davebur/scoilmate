# ScoilMate: prioritised implementation backlog
A minimal branded landing page, /health and static branding are implemented and smoke-tested via run_local_testing. No learning, identity, database or admin features below are implemented. Order is dependency-driven; estimates await decisions.

| Priority / ID | Deliverable | Acceptance checks |
|---|---|---|
| P0 D1 | Agree audience, pilot, controller, Gaeilge track/levels and storage interpretation | Dave records decisions; no student onboarding with unresolved controller/lawful basis. |
| P0 D2 | Current curriculum/text register and reviewers | Teacher verifies full current specs, outcome mappings, text cohorts; search-only details resolved; content has review identities/dates/rights. |
| P0 D3 | Privacy and safeguarding design | DPIA screening, age-appropriate notices, retention, recovery, adult contact and data-flow approved; synthetic accounts only until ready. |
| P0 F1 | Dependencies and app foundation | Supported Python/deps locked; local-only FastAPI page and tests; no secrets/default admin; licence/advisory review. |
| P0 F2 | SQLAlchemy/Alembic schema | FK checks enabled; populated migration roundtrip/recovery; invalid option/version rejected; backup restores; immutable version tests. |
| P0 A1 | Auth, roles, sessions and CSRF | Student cannot reach admin/other student; cookie flags, rotation/expiry/revocation, generic failures, CSRF missing/wrong rejected on every unsafe endpoint; recovery token single-use. |
| P0 C1 | Admin author/review/publish | Draft invisible to students; publishing requires review and valid question/lesson/eligibility; edit produces new version; retired version excluded from new quizzes but old attempts render. |
| P0 L1 | Learn → quiz → feedback | Keyboard/mobile student completes topic; pre-submit payload contains no key; server grades; hints recorded; explanation/help match pinned versions. |
| P0 Q1 | Durable attempts | Duplicate submit returns same response; conflicting retry 409; interrupted/restarted server preserves state; mixed ownership/track tampering rejected. |
| P0 P1 | Transparent progress | Independent vs assisted counts distinct; abandoned items excluded; deterministic rebuild matches cache; topic suggestions not grades. |
| P0 R1 | Pilot release gate | 30-concurrent proposed burst target tested; no lost responses; rate-limit 429; XSS/IDOR/CSRF checks; restore drill; rights/export/erase including backup policy; assistive tech/manual Gaeilge checks. |
| P1 C2 | Expand reviewed content | Agree 3 topics/subject and 5–10 questions/topic; no unsupported full-curriculum claim; balance distractors and review ambiguity. |
| P1 P2 | Revisit scheduling | Simple explainable reminders within app, opt-in; no manipulative pressure; algorithm versioned. |
| P2 | Rich audio, short responses, school grouping, H5P | Separate requirements/security/privacy work; no implicit expansion of admin access. |
| Later | GitHub and production | Explicit Dave authorisation; licence/secret/content checks; hosting plan and rollback signed off before configuration changes. |

Test pyramid: stdlib fixture checks now; later unit tests for eligibility/grading/progress, database integration for constraints/migrations/locks/idempotency, HTTP tests for every permission/CSRF case, browser tests for complete journeys and accessibility, manual subject review. No tests against real minors' data.
