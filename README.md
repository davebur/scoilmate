# ScoilMate — planning repository

**Status:** local pilot build: roadmap steps 1 and 4–8 done ([roadmap](docs/07-backlog-and-acceptance.md)); step 8 sign-offs (DPIA, privacy notice, teacher and Gaeilge review) open · **Checked:** 15 November 2026 · **Owner:** Dave (decisions pending)

A proposed Irish Junior Cycle learning website for **English, Gaeilge and History**: learn a short topic, try original practice questions, request hints, understand feedback, and revisit topics. “Junior Certificate” is a useful legacy search term; the product should use **Junior Cycle** for the current programme.

This contains a **FastAPI + SQLite app for local testing**: admin, parent and student accounts; practice with hints, server-side marking, mastery levels, revisit dates, mixed and mistake reviews; student, parent and admin reports; an admin content workflow (draft, preview, review, publish, retire) with a ratings review queue; and a wellbeing page. It is not a complete curriculum, an official NCCA/SEC resource, a full exam simulator, or approved for real students. Preview dependencies were installed only in project `.venv`; a temporary owned Uvicorn process was smoke-tested and stopped. No nginx changes, GitHub repository creation or production deployment occurred. All sample teaching material is **original, draft and unreviewed** and must not be offered to students as approved content.

## Recommended direction

- FastAPI + Uvicorn, eventually behind nginx on one server.
- Server-rendered HTML (Jinja2) and small progressive enhancement; avoid an SPA for the MVP.
- **SQLite + SQLAlchemy 2.x + Alembic**: an embedded relational database, **not a separately administered database server**. SQLite is still an RDBMS in the technical sense. Confirm this interpretation of “no full RDBMS” with Dave.
- Three roles: admin, parent and student. Invite-only pilot; no public student registration, messaging, ads, AI tutor or student uploads.
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

## Run it locally

```sh
cd ~/coding/scoilmate
.venv/bin/python -m scoilmate.cli migrate          # creates instance/scoilmate.db (also done by the launcher)
.venv/bin/python -m scoilmate.cli seed-demo        # fake demo accounts + some history (--reset to recreate)
HOST=127.0.0.1 ./run_local_testing                 # http://127.0.0.1:8000/  (Ctrl-C stops)
```

`run_local_testing` applies database migrations, imports the draft content and any old ratings file on every start (all idempotent), then starts Uvicorn. It turns on `SCOILMATE_ALLOW_DRAFT_PRACTICE=1`, so students can practise draft content, always shown with a **"Draft, not teacher-reviewed"** banner; set it to `0` to show only published content. Defaults: `HOST=0.0.0.0` (all interfaces: trusted LAN testing only, never the public Internet), `PORT=8000`, `RELOAD=0`. It prints LAN address candidates; firewalls/isolation may block them. Plain HTTP, so Secure cookies are off unless `SCOILMATE_SECURE_COOKIES=1` behind HTTPS.

First-time setup on another machine: `python3 -m venv .venv && .venv/bin/python -m pip install -r requirements-local-tested.txt` (never install globally). On this host `ensurepip` was missing, so the venv was bootstrapped with the official PyPA `get-pip.py` inside `.venv` only.

Real admin instead of demo: `.venv/bin/python -m scoilmate.cli create-admin yourname` (prompts for a password). Backups: `cli backup` writes `instance/backups/…db`; `cli restore FILE --yes` with the server stopped.

### Demo logins (fake people; created by `seed-demo`; local testing only)

| Login | Password | Role |
|---|---|---|
| `demo-admin` | `demo-admin-pass` | admin |
| `demo-parent1` | `demo-parent-pass` | parent of Student A and Student B |
| `demo-parent2` | `demo-parent-pass` | parent of Student C |
| `demo-student1` | `demo-student-pass` | student (year 3, has the most history) |
| `demo-student2` | `demo-student-pass` | student (year 2) |
| `demo-student3` | `demo-student-pass` | student (year 1, Gaeilge T1) |

### Roles

- **Admin:** adds/removes parents and students, links them, resets access, confirms deletions; reports for every student, class overview, question stats, CSV exports; **Content** (write/edit drafts, preview as a student, record a review, publish, retire) and **Ratings** (👎 queue, mark resolved by a version); audit log.
- **Parent:** adds their own children, edits their settings, resets their access, deactivates them, asks for deletion; sees each child's report (not their private reflections).
- **Student:** practises topics, uses hints, sees explanations, rates items anonymously, mixed reviews and "redo my wrong answers", **My progress**, own data export.

### What to test

1. As `demo-student1`: Practice → a topic → answer with and without hints → finish → summary and "what next" → My progress (levels, why, due dates). Rate a question 👍/👎.
2. As `demo-parent1`: see both children's reports; add a new child (shows a one-time password); try changing settings.
3. As `demo-admin`: Accounts, Reports (class overview, question stats, CSV); **Content** → pick a question → *Preview as a student* → edit it (new version v2) → *Record a review* (name, date, notes) → *Publish*; add a new question with three hints; *Retire* an item and check old attempts still open. **Ratings** → mark an item resolved by version N.
4. `/wellbeing` (linked in the top bar for everyone).
5. Try things that should fail: a student opening `/admin`, a parent opening another family's child (404), logging in wrongly 6 times (429).

### Automated checks

```sh
.venv/bin/python -m unittest discover -s tools -p 'test_*.py'   # 76 tests, ~35 s; includes a 30-student burst on a temporary loopback server
.venv/bin/python tools/smoke_preview.py                           # starts the launcher on a random loopback port, then stops it
bash -n run_local_testing
```

Results and what is **not** covered (DPIA, privacy notice, teacher/Gaeilge review, accessibility audit) are in the [verification record](docs/11-verification.md).

## Draft examples and local checks

[content/draft-samples.json](content/draft-samples.json) contains **nine MCQs (three per subject), nine short topic-help lessons, answers, explanations and two hints per question**. Gaeilge has two T2 examples and one T1 example; this is not balanced coverage of either track. [Content contract](content/README.md).

Content checks use dependency-free Python. The preview also has a temporary-server smoke test:

```sh
python3 tools/validate_content.py
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

## Install and update from GitHub

The repository is `git@github.com:davebur/scoilmate.git`. Use a read-only GitHub deploy key on the server (Settings → Deploy keys on the repo), so the server can pull but cannot push.

**First install on a server (Ubuntu):**
```sh
ssh-keygen -t ed25519 -f ~/.ssh/scoilmate_deploy -N ""     # then add the .pub as a read-only deploy key
cat >> ~/.ssh/config <<'CFG'
Host github.com
  IdentityFile ~/.ssh/scoilmate_deploy
  IdentitiesOnly yes
CFG
git clone git@github.com:davebur/scoilmate.git ~/scoilmate
cd ~/scoilmate
sudo DOMAIN=scoilmate.example.ie ./deploy/install-ubuntu.sh
sudo ./deploy/init-admin.sh your-login --name "Your Name"
```
Full steps, including the HTTP-then-HTTPS certificate order, are in [docs/deploy-ubuntu.md](docs/deploy-ubuntu.md).

**Updating a running server:**
```sh
cd ~/scoilmate && git pull
sudo ./deploy/update-ubuntu.sh
```
The update backs up the database first, keeps the previous code for rollback, and never changes the nginx site, the certificates, `/etc/scoilmate/scoilmate.env` or the live database. Details are in [docs/deploy-ubuntu.md](docs/deploy-ubuntu.md#updating).

## Server deployment

Ubuntu install with uvicorn (systemd) behind nginx with HTTPS, and creating the first admin: see [docs/deploy-ubuntu.md](docs/deploy-ubuntu.md). Files are in `deploy/`: `install-ubuntu.sh`, `update-ubuntu.sh`, `init-admin.sh`, `scoilmate.service`, `nginx-http.conf`, `nginx-https.conf`, `scoilmate-proxy.conf`, `scoilmate.env.example`.

## Code style and lint

Config is in `pyproject.toml` (line length 100). Developer tools are in `requirements-dev.txt`; install them into the project venv only:
```sh
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m black --check scoilmate tools      # formatting (drop --check to apply)
.venv/bin/python -m ruff check scoilmate tools          # imports, bugs, style rules
.venv/bin/python -m pycodestyle scoilmate tools         # PEP 8
.venv/bin/python -m pylint scoilmate tools              # code quality (rated about 9.9/10)
```
Black, ruff and pycodestyle must pass cleanly. Pylint's remaining messages are mostly minor naming and subprocess notes; the disabled checks are listed with reasons in `pyproject.toml`.
