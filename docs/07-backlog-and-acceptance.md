# ScoilMate: roadmap and acceptance checks

Revised 2026-11-14 with Dave: deliver a clickable learning loop first, then add storage, accounts, reports and the review workflow. Research inputs: [competitor features](research/competitor-features.md), [exam paper analysis](research/exam-paper-analysis.md), [learning design guidance](research/learning-design-guidance.md) (step details below are refined once these land).

## Status

| Step | Deliverable | Status |
|---|---|---|
| 0 | Initial commit; README paths corrected | **Done** |
| 1 | Practice slice (no DB): topic notes → questions → hints → server-graded feedback → session summary; thumbs up/down ratings | **Done — ready to test** |
| 2 | Show to a teacher/student, adjust | Next (Dave) |
| 3 | Decisions D1/D2: cohort, Gaeilge track/levels, reviewers, pilot topics | Open (Dave) |
| 4 | Storage: SQLite + SQLAlchemy + Alembic for content, attempts, ratings | Planned |
| 5 | Accounts: admin + student roles, sessions, CSRF; **admin adds/removes students** | Planned |
| 6 | Reports: **student "My progress"** and **admin per-student and class progress reports** | Planned |
| 7 | Admin content authoring/review/publish; ratings review queue; more content | Planned |
| 8 | Privacy/safeguarding sign-off and pilot release gate | Planned |

## Acceptance checks

**Step 1 — practice slice (done)**
- Question page contains no answer key or explanation before submit (tested for every question); hints revealed one at a time on request.
- Server grades; invalid option 400; missing answer re-prompts; first answer counts, retries are practice only.
- Summary distinguishes correct-on-own, correct-with-hints and to-review; links each to its topic note. Not a grade.
- State in a signed, httpOnly, SameSite=Strict cookie only; tampered cookie ignored; nothing about the learner stored server-side.
- Ratings: 👍/👎 plus optional fixed reason (no free text, so no personal data) for questions and notes; stored anonymously with item id + version; one rating per item per browser; `tools/feedback_report.py` summarises.
- Gaeilge text marked `lang="ga"`; keyboard usable; security headers incl. CSP.

**Step 4 — storage**
- FK checks on; migration up/down on populated DB; content versions immutable; attempts pin question/hint/lesson version; backup + restore drill.
- Ratings move from JSONL to a table (import existing file).

**Step 5 — accounts and student management**
- Roles: admin, student. Admin can **add a student** (display name/pseudonym, year, subject tracks/levels — minimal data), **deactivate/remove a student**, reset access. Removal: deactivate first; hard delete erases attempts and ratings links per retention policy; action audited.
- No public registration. Student cannot reach admin pages or any other student's data (IDOR tests). CSRF on every POST. Cookie flags, rotation, expiry, generic login errors, rate-limited login.

**Step 6 — progress reports**
- **Student "My progress":** per subject/topic: questions tried, correct on own vs with hints, topics to revisit, recent activity; own data only; supportive wording, no grade prediction or ranking against others.
- **Admin student report:** same per-student view plus activity over time, hint use, topics needing review, content ratings given; **class overview** table (student × topic) with filters by subject/track/year; CSV export.
- Reports cover every activity type added later (quizzes, lessons read, revisit sessions, future writing/self-assessment tasks) through a common activity log, so new approaches appear without redesign.
- Deterministic: report rebuilt from attempts equals cached figures.

**Step 7 — content workflow**
- Draft invisible to students; publish requires review; edit creates new version; retired versions excluded from new quizzes, old attempts still render.
- Ratings queue: items sorted by 👎 and reason; admin can mark resolved with new version.

**Step 8 — pilot gate**
- 30-concurrent burst; no lost responses; 429 rate limits; XSS/IDOR/CSRF checks; restore drill; export/erase; accessibility and manual Gaeilge checks; DPIA screening and notices approved.

## Later
More reviewed content (3+ topics/subject, 5–10 questions/topic); spaced revisit reminders (opt-in, explainable); P2: audio/listening, short answers, school groups, H5P; GitHub and production hosting only with Dave's explicit sign-off.

Test pyramid: content fixture checks and HTTP tests now (`tools/test_*.py`); DB integration, permission matrix and browser/accessibility tests as steps land. Never test with real minors' data.
