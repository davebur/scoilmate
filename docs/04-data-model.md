# ScoilMate: proposed logical schema
Planning schema, not executable migration. UUID text IDs at boundaries; UTC timestamps; explicit CHECK/UNIQUE/FK constraints and application validation. Never persist passwords/tokens in content fixtures.

## Identity and curriculum
- `user(id, login_normalised UNIQUE, display_alias, password_hash, role CHECK admin/parent/student, status, created_at, disabled_at)`; student email/full DOB not required. Role cannot be self-assigned.
- `parent_student(parent_id FK user, student_id FK user, created_by FK user, created_at, PRIMARY KEY(parent_id, student_id))`: which parents manage which students; created when a parent adds a student or an admin links them. Parent email (adult contact) on `user`, nullable for students.
- `audit_log(id, actor_id, action, target_user_id, at, detail)`: add/remove/link/reset/delete events.
- `student_subject(user_id, subject_id, track, preferred_level, school_year, exam_year nullable)`; UNIQUE user/subject. English track `general`, levels higher/ordinary/undecided; History `general`, common only; Gaeilge T1/T2 plus higher/ordinary/undecided. T1/T2 are not ability levels. School year 1–3 is guidance, not automatic proof of prescribed-text eligibility.
- `curriculum_release(id, subject, track, title, official_url, checked_at, effective_cohorts, verification_status)`; `learning_outcome(id, release_id, code, paraphrase)` UNIQUE release/code.
- `topic(id, subject, track, slug)`; `topic_outcome(topic_id, outcome_id, mapping_review_status)`; exact mapping requires educator approval.
- `text_selection(id, title, track, source_circular, exam_year_start/end, level_scope, stage, rights_status)` optional later. Do not infer cohort from age. No copyrighted text import by default.

## Immutable educational revisions
- `lesson(id, topic_id)`; `lesson_version(id, lesson_id, version, body, status, author_id, reviewer_id, review_at, published_at, rights_note)` UNIQUE lesson/version.
- `question(id, topic_id)` is stable identity; `question_version(id, question_id, version, prompt, type, language, status, difficulty_editorial, rights_note, author_id, reviewer_id, published_at)` UNIQUE question/version.
- `question_eligibility(question_version_id, curriculum_release_id, year_min/max, level, track)` separates editorial difficulty from official examination level.
- `option(question_version_id, option_key, body)` composite primary key; `answer_key(question_version_id, correct_option_key, explanation)` composite FK to that version's option. MCQ requires exactly one key, at least three distinct choices; publishing validates this transactionally.
- `hint(question_version_id, ordinal, body)` UNIQUE version/ordinal; `question_help(question_version_id, lesson_version_id)` pins help seen with an attempt.
- `quiz(id)`; `quiz_version(id, quiz_id, version, status)`; `quiz_item(quiz_version_id, ordinal, question_version_id)` UNIQUE quiz/ordinal. Mixed-subject/track accidental selection rejected by service rules.

Draft → reviewed → published → retired. Published question, options, key, hints, eligibility and linked help are immutable. Changes create a revision; a typo still creates a revision. Separate publication/retirement events permit hiding a version without mutating its content. No hard deletion of referenced versions. Severe factual error flags previous results for explanation; never silently regrade history. Record an explicit correction/regrade event with policy version if later needed.

## Attempts and reproducibility
- `quiz_attempt(id, user_id, quiz_version_id, state, started_at, submitted_at, client_request_id)` UNIQUE user/client_request_id.
- `attempt_item(id, attempt_id, ordinal, question_version_id, lesson_version_id, displayed_option_order_json, state)` UNIQUE attempt/ordinal; snapshot version/order before display. Supports shuffled options without changing keys.
- `hint_event(id, attempt_item_id, hint_ordinal, requested_at)` UNIQUE item/hint ordinal, FK to pinned question hint. Server records request, not a client-supplied hint count.
- `response(id, attempt_item_id UNIQUE, selected_option_key, answered_at, is_correct, assistance_state, scoring_policy_version, submission_key UNIQUE)`; composite option FK to the item's question version enforced through explicit version column/composite constraint or service plus DB design review. Never trust client correctness, ownership, timestamps or score.
- `progress(user_id, topic_id, algorithm_version, independent_correct, assisted_correct, answered_count, last_practised_at, computed_through_event)` composite key; derived cache, not source of truth. Rebuild from completed first responses/hints, exclude abandoned items and retries from the same question encounter. Separate total practice count from distinct-question count.

One submit per item; same idempotency key/payload returns same result, conflicting payload returns 409. Incorrect answer ends that item; “try again” starts a new practice encounter linked to the original, preserving independent first-response statistics. Hints reduce independent-evidence counts, not encouragement or punitive marks. Suggested topic status (“not yet tried”, “practising”, “revisit”) uses a documented versioned rule and minimum evidence; no claim of mastery from three MCQs.

## Security, operational and deletion tables
`session(token_digest UNIQUE, user_id, csrf_secret, created_at, idle_expires_at, absolute_expires_at, revoked_at)`; hashed single-use expiring invite/recovery tokens; minimal `audit_event(actor_id nullable, action, entity_id, at, request_id)`; bounded rate-limit buckets if persistent limiting needed. Never log secrets or response bodies. Index attempts(user_id, started_at), responses(item), question(topic/status), sessions(digest/expiry), progress(user/topic).

Student erasure deletes sessions/tokens/profile/preferences/attempts/responses/hints/progress; keep shared content versions without student identifiers. Audit actor references become null/pseudonymised according to approved retention, never retain identity through a supposed “anonymous” hash. Backup expiry and deletion replay after restore are required. Retention durations are proposals in the privacy plan, not statutory defaults.
