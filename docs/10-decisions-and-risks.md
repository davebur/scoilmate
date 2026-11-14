# ScoilMate: decisions and risks

## Recorded
- 2026-11-14: app name **ScoilMate**; independent local repo only. Planning plus user-requested minimal branded preview and local-testing launcher; full learning features remain deferred. Requested FastAPI/Uvicorn/nginx future shape and embedded local storage; no full database-server administration.
- Recommended, not yet accepted: SQLite/SQLAlchemy/Alembic, server-rendered UI, invite-only pilot and no external analytics.
- 2026-11-14: Dave supplied Git author/committer identity for the initial commit. Configure repository-local identity only; global Git settings unchanged. Branch `main`, no remote.

## Decisions required
Audience/controller and lawful basis; first cohort/year/exam years; English levels; Gaeilge T1/T2 and levels; original-content reviewers; desired pilot topics; simultaneous users; account recovery mechanism and adult contact; retention/DPIA; licence. Domain/GitHub/hosting remain explicitly deferred.

## Risks / mitigations
- Curriculum/circular drift: release-specific source metadata, checked date and educator sign-off; current T2 exact codes and English text lists are blocking unknowns for related publication.
- Superficial MCQ coverage: transparent supplementary scope, richer teaching help and future non-MCQ practice; no grade predictions.
- Incorrect/unidiomatic Irish: competent independent review; all examples draft/unreviewed.
- Minors/privacy: minimal data, no public social surface, documented controller/DPIA screening and rights workflow before real students.
- SQLite write contention: short atomic writes, bounded retry/idempotency and burst load tests; revisit engine only with evidence.
- Lost/corrupted records: consistent encrypted backups plus tested restore, version pins and migration recovery.
- Scope creep: one reviewed vertical slice first; teacher/parent/multi-school roles and exam simulation not MVP.
