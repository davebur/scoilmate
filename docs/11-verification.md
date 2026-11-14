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
