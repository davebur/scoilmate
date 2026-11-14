# ScoilMate: product and MVP

A minimal preview now demonstrates branding and direct local Uvicorn connectivity only. All learning/account journeys below remain planned.

## Purpose
Support Irish Junior Cycle students in English, Gaeilge and History through a learn → practise → hint → explain → revisit loop. Short formative quizzes supplement teaching; MCQs cannot demonstrate extended writing, historical argument, oral interaction, listening or full literary response. Never present a quiz percentage as an SEC grade.

## Pilot assumptions (not approved)
One invited cohort, one server, approximately 30 simultaneous learners; scope and capacity require confirmation. Responsive, keyboard-accessible, low-bandwidth browser experience. No paid services. Adult administrator is also content manager; student accesses only their own activity. Teacher/parent/class roles are deferred, not silently granted administrator powers.

## MVP journeys
- Student signs in with an invitation-provisioned account, chooses subject and permitted track/year/level, reads a short lesson, starts a 5–10 question untimed quiz, requests ordered hints, submits an answer, sees explanation and topic help, and revisits a suggested topic.
- Administrator creates draft lessons/questions, previews as student, records subject review and source/licence checks, publishes a new immutable revision, retires mistakes without deleting attempt history, provisions/disables accounts and performs a narrowly authorised export/deletion.
- Student sees private counts of independent correct, assisted correct and topics to revisit. A retry is a new practice attempt, not overwriting a wrong answer.

## Included
Single-answer MCQs; manually curated quizzes; topic-help pages; explicit hint usage; versioned content; own-history/progress; minimal admin UI; auditable publishing; account recovery; safe backups and restore test. Initial content target for approval: three topics per subject and 5–10 reviewed questions per topic, not full coverage. Samples in this repository are demonstrations only.

## Excluded
Exam timing/marking emulation, official certification, reproducing past papers, social features, leaderboards, direct messages, student free-text uploads, automatic essay grading, AI-generated live advice, adaptive psychometrics, parent dashboards, SSO, multi-school tenancy, offline syncing, payments and third-party analytics.

## Quality gates
WCAG 2.2 AA target: semantic headings/forms, focus indication, screen-reader feedback, labelled choices, no colour-only states, 200% zoom, mobile layout, no forced timer, Irish lang attributes/fada input, reduced-motion support. Test with real assistive technology and educator-approved representative learners using synthetic accounts first. No assertion of certification before an audit.

Success measures for a pilot: students can explain why an answer was correct, find topic help, and resume reliably; educators approve accuracy and age appropriateness; no cross-account access; no lost/doubled submissions. Avoid engagement streak pressure and ranking children.
