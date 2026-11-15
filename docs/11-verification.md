# ScoilMate: local verification

Checked 2026-11-14. Independent repository (since moved to `~/coding/scoilmate`), originally at `/home/dave/.openclaw/workspace/scoilmate`, renamed safely from the newly created planning directory after Dave supplied the ScoilMate name; destination did not exist. Parent workspace files/config untouched.

- `git init --initial-branch=main`: succeeded. No remotes.
- Git author/committer identity initially unavailable; later supplied by Dave and set repository-locally only.
- `python3 tools/validate_content.py`: PASS, nine lessons and nine MCQs with answers, hints, links, track/level/draft checks.
- `python3 -m unittest discover -s tools -p 'test_*.py' -v`: PASS; valid fixture and rejection of six bad mutations (answer, help, track, History level, publication state, duplicate ID).
- JSON parsed successfully; three questions per subject. Correct-key validation establishes structural reference, not factual correctness. Human subject/language review remains required.
- Supplied logo original is 1408×768 (not the initially estimated 1200×655); byte-identical copied original verified SHA-256. Detected tile bbox (456,142,952,625); padded square crop (440,119,968,647), 528×528; PNG sizes 32/180/192/512; ICO frame sizes 16/32/48 verified using installed Pillow. No stretching/clipping; documentation in assets/branding/README.md.
- Internal Markdown relative-file references checked; `git diff --check` and staged whitespace check run before handoff. Preview smoke tests are recorded below; no full application/security/load tests are claimed.
- No system/global package install, production service, nginx/scheduler change, remote/push, paid service or external write. Project-only dependency downloads were authorised for the preview.

## User-requested local preview extension
- Minimal FastAPI branded `/`, JSON `/health`, static PNG/ICO implemented; no accounts/student data/database/quiz backend.
- Executable `run_local_testing`: shell syntax valid; root-independent launch tested from `/tmp`; venv preferred; validated HOST/PORT/RELOAD; default all-interface port 8000/reload off; no forwarded-proxy trust; loopback and discovered candidate host addresses printed with isolation/firewall warnings.
- Ordinary `python3 -m venv .venv` initially failed due to missing ensurepip. Official PyPA get-pip bootstrap used only inside ignored project .venv; no system installs/config changes. Runtime versions captured in requirements-local-tested.txt; pip check passed.
- Temporary smoke server on loopback port **39431**: GET `/`, `/health`, `/static/branding/favicon.ico`, `/static/branding/scoilmate-icon-192.png` all 200 with expected content. Owned process terminated and confirmed stopped. Four invalid setting cases rejected. No persistent server left running.
- `bash -n`, fixture checks and unit tests repeated successfully. LAN reachability from another physical device was NOT established; isolation/firewall can block host candidates. No production security/readiness claim.
- Initial commit made 2026-11-14 with repository-local identity supplied by Dave; global Git config unchanged.

## Steps 7 and 8 (2026-11-15, overnight build authorised by Dave)

Everything below ran locally against throwaway SQLite databases under a temporary directory, with made-up accounts only. No real student data, no system changes, no remote/push.

**Full suite:** `.venv/bin/python -m unittest discover -s tools -p 'test_*.py'`: **76 tests, OK** (62 before tonight + 11 content-workflow + 3 pilot-gate). `tools/smoke_preview.py`: PASS (launcher from `/tmp`, migrations incl. 0004 on start, `/`, `/login`, `/practice`, `/wellbeing`, `/admin/content`, static icons; owned server stopped; four bad settings rejected). `bash -n run_local_testing`: OK. No server left running afterwards (`pgrep uvicorn` empty).

**Step 7 — content workflow** (`tools/test_content_workflow.py`)
- Only admins reach every content/ratings page and action (parent and student 403, anonymous redirected to login), and denied attempts change nothing.
- Draft → review (reviewer name, date not in the future, notes) → publish; publish without review is refused; reviewed-but-unpublished is not offered when draft practice is off.
- Every edit adds a version; a no-change edit adds none; v1 text unchanged after v2; publishing v2 retires v1. Invalid edits (missing options, wrong key, no hints, duplicate options, bad slug) re-render with an error and save nothing.
- Retire removes the item from new practice; a student's earlier attempt on it still renders.
- Admin "Preview as a student" shows no key/explanation before answering, grades on request, records nothing.
- Draft-practice setting on: students see drafts with the "Draft, not teacher-reviewed" banner.
- Stored XSS: script/img/quote payloads in prompt, options, explanation, hints, note title and body are escaped on admin pages, preview and student question/hint/feedback pages.
- Ratings queue order (most 👎, then most serious reason) and "resolved by version N" / "no change needed"; resolving with an earlier/non-existent version is refused.
- Wellbeing page links checked with live fetches on 2026-11-15: gov.ie *Wellbeing support for exam students, parents and school staff* (fetched 200 via web fetch; plain curl gets 403 from gov.ie bot protection), jigsaw.ie 200, spunout.ie 200, spunout.ie/services/text-about-it 200, childline.ie 200. Phone numbers (Childline 1800 666 666, Samaritans 116 123, text 50808) taken from the gov.ie page.

**Step 8 — technical pilot-gate checks**

| Check | Result | Where |
|---|---|---|
| XSS escaping (authored content; user-supplied names on admin, parent and student pages); CSP `script-src 'none'`; no `<script` in any page | PASS | test_content_workflow, test_pilot_gate.NameXssTests, test_app |
| CSRF: missing, empty and wrong token on **every** POST route → 403; another session's token rejected; cross-origin Origin rejected; login form needs a token | PASS | test_accounts.CsrfTests |
| IDOR / role pairs: **every** GET and POST route × admin, parent of the child, another parent, the student, another student, anonymous (≈200 requests); unclassified new routes fail the test | PASS | test_pilot_gate.Sweep, test_accounts.IdorTests, test_learning (set IDOR) |
| Session idle and absolute expiry; rotation on login; logout revokes | PASS | test_accounts.LoginTests |
| Login rate limiting: 429 + Retry-After per account and per IP | PASS | test_accounts.LoginTests |
| Burst: 30 students at once against a real Uvicorn on a random loopback port: 1,200 requests (start, hint, answer, finish, summary across 8 topic sets each) in about 9 s, 0 errors, 240/240 answers and 240/240 hint records stored, no duplicates; server stopped and confirmed exited | PASS | test_pilot_gate.BurstTests |
| Backup/restore drill: CLI `backup` (file mode 0600, integrity check) → simulated loss → CLI `restore --yes` → all answers back; corrupt backup refused | PASS | test_pilot_gate.BurstTests, test_storage |
| Student data export (student, parent, admin; private reflection only in the student's own export) and erasure (no row anywhere still references the student) | PASS | test_learning |

**Not done / not claimed** (open items for Dave, see the roadmap step 8):
- **DPIA screening** (and full DPIA if needed), controller/lawful basis, **privacy notice** for parents and a child-friendly version: not written or approved.
- **Teacher content review**: every item is still a draft; nothing has been reviewed or published by a teacher.
- **Gaeilge language review** (spelling, grammar, dialect/register) by a fluent reviewer: not done.
- **Accessibility**: only structural basics (labels, `lang="ga"`, skip link, keyboard-usable forms); no screen-reader, zoom or contrast audit.
- Not implemented from docs/05: re-authentication before admin export/erasure, answer-submit rate limits (60/student/min), MFA for admins, account-recovery tokens. Login rate limits are in memory and reset on restart.
- Burst test is one Uvicorn process on this machine with SQLite; it is not evidence about a production host, network or more than ~30 simultaneous users.
