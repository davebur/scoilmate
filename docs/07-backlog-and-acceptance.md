# ScoilMate: roadmap and acceptance checks

Revised 2026-11-14 with Dave: deliver a clickable learning loop first, then add storage, accounts, reports and the review workflow. Research inputs: [competitor features](research/competitor-features.md), [exam paper analysis](research/exam-paper-analysis.md), [learning design guidance](research/learning-design-guidance.md) (all three completed 2026-11-14 and folded in below).

## Status

| Step | Deliverable | Status |
|---|---|---|
| 0 | Initial commit; README paths corrected | **Done** |
| 1 | Practice slice (no DB): topic notes → questions → hints → server-graded feedback → session summary; thumbs up/down ratings | **Done — ready to test** |
| 2 | Show to a teacher/student, adjust | Next (Dave) |
| 3 | Decisions D1/D2: cohort, Gaeilge track/levels, reviewers, pilot topics | Open (Dave) |
| 4 | Storage: SQLite + SQLAlchemy + Alembic for content, attempts, ratings | **Done** (`tools/test_storage.py`) |
| 5 | Accounts: admin, **parent** and student roles, sessions, CSRF; admins add/remove students and parents; parents add and manage their own children | **Done** (`tools/test_accounts.py`) |
| 6 | Reports: **student "My progress"**, **parent view of each linked child**, **admin per-student and class reports** | **Done** (`tools/test_learning.py`) |
| 7 | Admin content authoring/review/publish; ratings review queue; more content | Planned |
| 8 | Privacy/safeguarding sign-off and pilot release gate | Planned |

## Feature set from research

What students and admins get, and why. Sources: common features across 18 tools, the 35 SEC papers from 2022–2026, and the learning-science guidance.

| Feature | Evidence | Step |
|---|---|---|
| Topic notes + topic-tagged practice with instant, explained feedback | 15/18 tools; retrieval practice (high utility) | 1 ✅, extended in 4 |
| Hint ladder: nudge → strategy/worked parallel → eliminate one option; explanation says why right *and* why the chosen option is wrong | 7/18 tools; worked examples | 1 (2 hints) → 3 hints in content batch |
| **Topics + mastery levels** Not started / Attempted / Familiar / Proficient / Mastered, with the rule shown in plain words; hints reduce credit but are never shamed | Khan Academy mastery model | 4–6 |
| **Mixed reviews** (10–15 Qs from 3–5 topics within one subject), the only route to Mastered, ≥3 days later | interleaving + spacing; Khan | 6 |
| **Revisit ladder** 1 / 3 / 7 / 21 / 45 days by level; "Due for review: Thursday"; compresses if an exam date is set | spacing (high utility); 7/18 tools | 6 |
| **Mistake review** ("redo my wrong answers") | 6/18 tools | 6 |
| **More activity types** beyond MCQ, chosen from the paper analysis: cloze and three-option grammar (Gaeilge), timeline/ordering and cause-vs-consequence sorting (History), source cards with retrieval questions (History), flashcards for key terms/vocab/poetic terms, short typed recall | exam coverage map | 4 then content batches |
| **Structured writing plans + self-assessment checklists** for writing tasks MCQs can't cover: functional forms (English), *ceapadóireacht* to bullet points (Gaeilge), "account of a person/event" (History). Checklists mirror marking criteria (English: focus, ideas, development, coherence, expression, register; Gaeilge: bullets developed, tense and mutation accuracy); compare with a model answer | marking schemes; MCQ gap | 7 |
| **Metacognition**: confidence (1–4) before a set, compared with the result after; "What will I do next?" at the end | EEF metacognition (+8 months) | 6 |
| **Study plan**: exam date + weekly time → due reviews + one new topic per session; process goals; reschedule without penalty | EEF/self-regulation; rare in competitors | Later |
| **Student "My progress"** and **admin per-student + class reports** (see step 6) | 12/18 and 9/18 tools | 6 |
| **Admin assignments** ("practise topic X by date Y", completion tracking) | 9/18 tools | Later (after 6) |
| **Timed practice / mini-mock** per paper section | 4/18 tools; exam timing gap | Later |
| **Gaeilge listening** with original recorded audio (not SEC MP3s) | aural is 45–60 marks every year | Later (P2) |
| **Parent role**: admin adds parents; parents add and manage their own children and see their reports | Dave's request (Seneca has parent-shareable reports) | 5–6 |
| 👍/👎 content ratings → admin review queue | Dave's request | 1 ✅, queue in 7 |
| Exam-stress/wellbeing page linking official Irish supports | Bitesize; Dept of Education | 7 |

**Deliberately excluded**, because they conflict with a privacy-first, invite-only app for 13–15-year-olds: leaderboards/leagues, streaks and loss-aversion mechanics (replaced by a private "this week: 3 sessions" tally that resets quietly), push/email nags (opt-in, daytime, max 1/day if ever added), AI tutor/marking, messaging or tutor chat, ads, third-party video embeds, grade or descriptor predictions, learning-styles matching, and reproducing SEC papers (write original exam-style items and link to examinations.ie for real papers).

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

**Step 5 — accounts, parents and student management**
- Roles: **admin**, **parent**, **student**. Each student is managed by one or more linked parents (a `parent_student` link).

| Action | Admin | Parent | Student |
|---|---|---|---|
| Add a student | ✅ any (optionally link to parents) | ✅ automatically linked to themselves | ❌ |
| Add a parent | ✅ | ❌ | ❌ |
| Link/unlink a parent and a student | ✅ | ❌ (prevents claiming someone else's child) | ❌ |
| Edit student settings (year, subjects, Gaeilge track/level), reset access | ✅ any | ✅ own children only | own year/subjects only |
| Deactivate a student | ✅ any | ✅ own children only | ❌ |
| Permanently delete a student and their data | ✅ (audited) | requests it; admin confirms | ❌ |
| Remove a parent | ✅ (their children stay; any child left without a parent is flagged for admin) | ❌ | ❌ |
| See progress reports | all students + class overview | own children only | own only |

- Minimal data: student alias, year, subject tracks/levels. Parent: name and email for login/recovery (adult contact). No student email required.
- No public registration. Parents are invited by an admin and add students from inside their own account. A student cannot reach parent/admin pages; a parent cannot reach another family's student or any admin page (IDOR tests for every role pair). CSRF on every POST. Cookie flags, rotation, expiry, generic login errors, rate-limited login. Every add, remove, link and reset is recorded in an audit log.

**Step 6 — progress, revisit and reports**
- Mastery levels, revisit ladder, mixed reviews, mistake review and confidence prompts as specified in [learning design guidance §3](research/learning-design-guidance.md); every level shows the rule that produced it.
- **Student "My progress":** per subject/topic: level and why, what's due and when, recent sessions, correct on own vs with hints (neutral wording), confidence vs result, suggested next step. Own data only; no class averages, rankings or grade predictions.
- **Parent report:** the student report for each linked child, plus last active date and a simple weekly activity count. No class comparison, other children or rankings. Private reflections and notes stay private to the student, and the student's report tells them which parts their parent can see.
- **Admin student report:** the same per-student view plus activity over time, overdue reviews, topics most often missed, last active date. **Class overview** (student × topic level) filtered by subject/track/year; question stats (% correct, most-chosen wrong option, hint use); CSV/printable export. Admins never see private reflection text or time-of-day detail beyond aggregates.
- Reports cover every activity type added later (quizzes, lessons read, revisit sessions, future writing/self-assessment tasks) through a common activity log, so new approaches appear without redesign.
- Deterministic: report rebuilt from attempts equals cached figures.

**Step 7 — content workflow**
- Draft invisible to students; publish requires review; edit creates new version; retired versions excluded from new quizzes, old attempts still render.
- Ratings queue: items sorted by 👎 and reason; admin can mark resolved with new version.

**Step 8 — pilot gate**
- 30-concurrent burst; no lost responses; 429 rate limits; XSS/IDOR/CSRF checks; restore drill; export/erase; accessibility and manual Gaeilge checks; DPIA screening and notices approved.

## First content batch (from the exam analysis, pending teacher review)
- **English:** poetic techniques + unseen-poem response; functional writing forms (diary, speech, email/letter, review, blog); unseen non-fiction comprehension; studied-text key-moment bank; Shakespeare (HL) generic skills.
- **History:** working with sources; chronology and key terms; archaeology and archives; Great Famine/emigration and the Holocaust; Age of Exploration/Renaissance with an "account of" plan.
- **Gaeilge:** question words + paragraph *léamhthuiscint*; grammar in context (tenses, copula, séimhiú/urú); *ceapadóireacht* to bullet points; themed vocabulary; *sraith pictiúr* (T2 OL). Literature only after the cohort's text list is verified.
All items original; SEC papers inform format and skills only.

## Later
More reviewed content (3+ topics/subject, 5–10 questions/topic); P2: audio/listening, short answers, school groups, H5P; GitHub and production hosting only with Dave's explicit sign-off.

Test pyramid: content fixture checks and HTTP tests now (`tools/test_*.py`); DB integration, permission matrix and browser/accessibility tests as steps land. Never test with real minors' data.
