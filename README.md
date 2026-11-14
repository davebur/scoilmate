# ScoilMate — planning repository

**Status:** planning plus a local practice preview (step 1 of the [roadmap](docs/07-backlog-and-acceptance.md)) · **Checked:** 14 November 2026 · **Owner:** Dave (decisions pending)

A proposed Irish Junior Cycle learning website for **English, Gaeilge and History**: learn a short topic, try original practice questions, request hints, understand feedback, and revisit topics. “Junior Certificate” is a useful legacy search term; the product should use **Junior Cycle** for the current programme.

This contains a **FastAPI practice preview** (topic notes, questions with hints, server-side marking, session summary, anonymous 👍/👎 content ratings), not an implemented learning application, a complete curriculum, an official NCCA/SEC resource, or a full exam simulator. Preview dependencies were installed only in project `.venv`; a temporary owned Uvicorn process was smoke-tested and stopped. No nginx changes, GitHub repository creation or production deployment occurred. All sample teaching material is **original, draft and unreviewed** and must not be offered to students as approved content.

## Recommended direction

- FastAPI + Uvicorn, eventually behind nginx on one server.
- Server-rendered HTML (Jinja2) and small progressive enhancement; avoid an SPA for the MVP.
- **SQLite + SQLAlchemy 2.x + Alembic**: an embedded relational database, **not a separately administered database server**. SQLite is still an RDBMS in the technical sense. Confirm this interpretation of “no full RDBMS” with Dave.
- Two initial roles: administrator and student. Invite-only pilot; no public student registration, messaging, ads, AI tutor or student uploads.
- Review-gated, immutable published content revisions; attempts pin exact question, hint and lesson versions.
- Private, understandable progress feedback, not predicted exam grades or high-stakes assessment.

Maintained existing options were checked first. Moodle/H5P are credible reuse options, but Moodle's PHP/database-server stack conflicts with the requested FastAPI/embedded-storage direction. H5P may be useful later if its authoring value outweighs integration complexity. See [the preflight](docs/02-existing-solutions.md); custom work is justified here by the requested stack and narrow product, not because existing LMSs lack quizzes.

## Branding

User-supplied ScoilMate logo and derived favicons are in [assets/branding](assets/branding/README.md). Original preserved byte-for-byte; square icon and PNG/ICO sizes verified.

## Read the plan

1. [Product scope and MVP](docs/01-product-and-mvp.md)
2. [Existing solutions and maintained libraries](docs/02-existing-solutions.md)
3. [Architecture and embedded-storage decision](docs/03-architecture-and-storage.md)
4. [Data model, versioned attempts and progress](docs/04-data-model.md)
5. [Security, minors, privacy and safeguarding](docs/05-security-and-privacy.md)
6. [Curriculum and content plan](docs/06-curriculum-and-content.md)
7. [Prioritised backlog with acceptance checks](docs/07-backlog-and-acceptance.md)
8. [Deferred deployment shape — no configuration applied](docs/08-deployment-later.md)
9. [Dated source and evidence register](docs/09-sources-and-evidence.md)
10. [Decisions and risks](docs/10-decisions-and-risks.md)
11. [Verification record](docs/11-verification.md)

## Run the local/LAN preview

From the repository (Python 3.12+ recommended):

```sh
cd ~/coding/scoilmate
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-local-tested.txt
./run_local_testing
```

This checkout already has a populated ignored `.venv`. `requirements-local-tested.txt` records the complete versions used for the smoke test, not a security-audited production lockfile. `requirements.txt` is the updateable runtime dependency input. Never install these globally.

On this host, `ensurepip` was unavailable, so ordinary venv creation reported an error after creating the interpreter. The existing project venv was bootstrapped using official PyPA `https://bootstrap.pypa.io/get-pip.py`, saved and run inside `.venv` only. For another similarly minimal host, either have the operator provide venv support, or explicitly download/review that official bootstrap and run it with `.venv/bin/python`; do not use system pip or sudo. No system package was installed here.

Launcher defaults: `HOST=0.0.0.0`, `PORT=8000`, `RELOAD=0`. It prefers `.venv/bin/python`, validates IP/port/reload, disables forwarded proxy-header trust, and works from any current directory. **Default binding exposes this preview on available interfaces: trusted local testing only, never the public Internet.** For loopback only or different port:

```sh
HOST=127.0.0.1 PORT=8080 ./run_local_testing
# Explicit development auto-reload (off by default):
RELOAD=1 ./run_local_testing
# Launch while elsewhere:
~/coding/scoilmate/run_local_testing
```

Open `http://127.0.0.1:8000/` and choose **Start practising**. Launcher prints discovered host/LAN address candidates; isolation/container networking, bind address and firewall can make those unreachable from your LAN. No firewall/public route is configured. Stop with Ctrl-C. Production remains HTTPS behind nginx, separately approved. There is no login or database: quiz progress lives only in a signed browser cookie for a few hours and resets when the server restarts. Anonymous ratings are appended to git-ignored `instance/content-feedback.jsonl`; summarise with `python3 tools/feedback_report.py`. Do not use real student data.

Repeat the owned-process smoke test (starts a server on a temporary loopback port, then stops only that process):

```sh
bash -n run_local_testing
.venv/bin/python tools/smoke_preview.py
.venv/bin/python -m pip check
```

## Draft examples and local checks

[content/draft-samples.json](content/draft-samples.json) contains **nine MCQs (three per subject), nine short topic-help lessons, answers, explanations and two hints per question**. Gaeilge has two T2 examples and one T1 example; this is not balanced coverage of either track. [Content contract](content/README.md).

Content checks use dependency-free Python. The preview also has a temporary-server smoke test:

```sh
python3 tools/validate_content.py
.venv/bin/python -m unittest discover -s tools -p 'test_*.py' -v   # content + HTTP tests
git diff --check
git diff --cached --check
```

Checks validate JSON structure, unique identifiers, allowed subject/track/level combinations, draft status, answer references and lesson links. They **do not establish educational accuracy, good Irish, legal compliance or curriculum approval**. A human educator must review these separately.

## Next decisions for Dave

1. **Audience/controller:** family/private pilot, a school, or a public service? Who decides purposes of student data processing?
2. **Cohort:** which year(s), exam cohort(s), English level(s), Gaeilge T1 or T2 and level(s)? Start with one Gaeilge track; do not mistake T1 for Higher or T2 for Ordinary.
3. **Content reviewers:** who can review English, Gaeilge (including dialect/register) and History? No student pilot before review.
4. **MVP slice:** approve selected topics and a modest reviewed question bank rather than “the entire Junior Cycle”.
5. **Storage:** confirm SQLite means “embedded/no database server”, plus expected simultaneous students.
6. **Privacy/onboarding:** approve invite-only access, lawful-basis assessment, retention and account recovery approach.
7. **Git authorship resolved:** Dave supplied the author/committer identity on 14 November 2026. It is configured locally for this repository only; global Git settings are unchanged. The initial commit contains this plan and preview. The repository is on `main` with no remote.

## Local-only boundary

Repository: `~/coding/scoilmate` (its own `.git`, independent of the surrounding workspace). GitHub, licence selection, domain, hosting, TLS, dependency lockfile, full learning-application implementation and any production deployment require a later decision. No open-source licence is selected merely by writing this plan; do not publish the materials before Dave decides licensing and the content is reviewed.
