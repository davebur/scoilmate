"""Step 8 technical checks that are not covered elsewhere.

- Every GET and POST route is classified by owner and checked for every role pair (admin, parent of
  the child, another parent, the student, another student, anonymous): a new route that is not
  classified here fails the test, so nothing slips through.
- XSS: user-supplied names render escaped on every admin/parent/student page.
- Burst: ~30 students answer concurrently against a real, temporary Uvicorn server on a random
  loopback port; no lost or duplicated attempts. Then a CLI backup/restore drill of that database.

Other step-8 checks live in test_accounts.py (CSRF missing/wrong on every POST,
cross-origin, session
expiry, 429 login limits), test_storage.py (backup/restore drill, corrupt backup rejected),
test_learning.py (export, erasure, set IDOR) and test_content_workflow.py (authored-content XSS).
"""

import os
import re
import socket
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path

try:
    import httpx
    import testutil
    from sqlalchemy import func, select
    from testutil import PASSWORD, Client, make_user

    from scoilmate import accounts, content, db
    from scoilmate.config import settings
    from scoilmate.models import ContentItem, PracticeSet, Response, Topic, User
except ImportError as exc:
    raise unittest.SkipTest(f"dependencies unavailable: {exc}") from exc

ROOT = Path(__file__).resolve().parents[1]
XSS = "<script>alert(1)</script>"
ALLOW_ANY_STUDENT = {
    "/practice/rate",
    "/practice/mistakes/start",
    "/practice/topic/{slug}/start",
    "/practice/mixed/{strand_slug}/start",
}  # student actions on shared content, not on objects
PUBLIC = {"/", "/health", "/login", "/wellbeing"}
SKIP = {("POST", "/login"), ("POST", "/logout")}  # covered by LoginTests/CsrfTests


class Sweep(unittest.TestCase):
    def setUp(self):
        testutil.fresh_db()
        testutil.reset_limits()
        self.admin = make_user("admin", "admin1")
        self.p1 = make_user("parent", "parent1")
        self.p2 = make_user("parent", "parent2")
        self.s1 = make_user("student", "student1", parent=self.p1)
        self.s2 = make_user("student", "student2", parent=self.p2)
        st = Client().login("student1")
        with db.session_scope() as s:
            self.topic = s.scalar(
                select(Topic.slug).where(Topic.subject == "english").order_by(Topic.id)
            )
            self.qslug = s.scalar(select(ContentItem.slug).where(ContentItem.kind == "question"))
        r = st.submit(f"/practice/topic/{self.topic}/start", {"confidence": ""})
        self.set_id = int(re.search(r"/practice/set/(\d+)/", r.headers["location"]).group(1))

    def fill(self, path):
        values = {
            "student_id": self.s1,
            "user_id": self.s1,
            "set_id": self.set_id,
            "n": 1,
            "slug": self.qslug,
            "version": 1,
            "version_id": 1,
            "strand_slug": "english",
        }
        if path.startswith("/practice/topic/"):
            values["slug"] = self.topic
        if path == "/admin/content/new":
            path += f"?kind=question&topic={self.topic}"
        return re.sub(r"\{(\w+)\}", lambda m: str(values[m.group(1)]), path)

    def expected(self, method, path):
        """{actor: status} for one route. Objects belong to student1 (child of parent1)."""
        if path in PUBLIC:  # (/login sends a logged-in user to their home page)
            return {**{a: "ok" for a in ("admin1", "parent1", "student1")}, None: 200}
        if path.startswith("/admin"):
            return {"admin1": "ok", "parent1": 403, "student1": 403, None: 303}
        if path.startswith("/parent"):
            owned = "{student_id}" in path
            return {
                "parent1": "ok",
                "parent2": 404 if owned else "ok",
                "admin1": 403,
                "student1": 403,
                None: 303,
            }
        if path.startswith(("/practice", "/progress", "/me")):
            exp = {"student1": "ok", "parent1": 403, "admin1": 403, None: 303}
            if "{set_id}" in path:
                exp["student2"] = 404
            elif path not in ALLOW_ANY_STUDENT:
                exp["student2"] = "ok"  # own page/data
            return exp
        self.fail(f"route {method} {path} is not classified in test_pilot_gate.py; add it")

    def test_every_route_for_every_role_pair(self):
        clients = {None: Client()}
        for login in ("admin1", "parent1", "parent2", "student1", "student2"):
            clients[login] = Client().login(login)
        routes = sorted(
            {(m, p) for p, ms in testutil.all_routes() for m in ms if m in ("GET", "POST")}
        )
        self.assertGreater(len(routes), 50)
        checked = 0
        for method, path in routes:
            if (method, path) in SKIP:
                continue
            url = self.fill(path)
            for actor, want in self.expected(method, path).items():
                if method == "POST" and want == "ok":
                    continue  # allowed POSTs are exercised by the feature tests
                with self.subTest(actor=actor, method=method, path=url):
                    c = clients[actor]
                    r = (
                        c.get(url, follow_redirects=False)
                        if method == "GET"
                        else c.submit(url, {"active": "0"})
                    )
                    if want == "ok":
                        self.assertLess(r.status_code, 500)
                        self.assertNotIn(r.status_code, (401, 403, 404), r.text[:200])
                    else:
                        self.assertEqual(r.status_code, want)
                    if want == 303:
                        self.assertTrue(r.headers["location"].startswith("/login"))
                    checked += 1
        self.assertGreater(checked, 150)
        with db.session_scope() as s:  # denied requests changed nothing
            self.assertEqual(s.get(User, self.s1).status, "active")
            self.assertEqual(s.scalar(select(func.count()).select_from(User)), 5)


class NameXssTests(unittest.TestCase):
    def test_user_supplied_names_are_escaped(self):
        testutil.fresh_db()
        testutil.reset_limits()
        make_user("admin", "admin1")
        a = Client().login("admin1")
        r = a.submit(
            "/admin/users/new",
            {
                "role": "parent",
                "login": "parentx",
                "display_name": "P " + XSS,
                "email": "p@example.invalid",
            },
        )
        self.assertEqual(r.status_code, 200, r.text[:300])
        with db.session_scope() as s:
            pid = s.scalar(select(User.id).where(User.login == "parentx"))
            s.get(User, pid).password_hash = accounts.auth.hash_password(PASSWORD)
        p = Client().login("parentx")
        r = p.submit(
            "/parent/children/new",
            {
                "login": "childx",
                "display_name": "C " + XSS,
                "school_year": "2",
                "subj_english": "on",
                "track_english": "general",
                "level_english": "higher",
            },
        )
        self.assertIn(r.status_code, (200, 303), r.text[:300])
        with db.session_scope() as s:
            cid = s.scalar(select(User.id).where(User.login == "childx"))
            self.assertIsNotNone(cid)
            s.get(User, cid).password_hash = accounts.auth.hash_password(PASSWORD)
        st = Client().login("childx")
        pages = {
            "admin home": a.get("/admin"),
            "admin user": a.get(f"/admin/users/{cid}"),
            "admin parent": a.get(f"/admin/users/{pid}"),
            "audit": a.get("/admin/audit"),
            "admin report": a.get(f"/admin/reports/students/{cid}"),
            "class": a.get("/admin/reports"),
            "parent home": p.get("/parent"),
            "parent child": p.get(f"/parent/children/{cid}"),
            "parent report": p.get(f"/parent/children/{cid}/report"),
            "student": st.get("/practice"),
            "progress": st.get("/progress"),
        }
        for name, r in pages.items():
            with self.subTest(page=name):
                self.assertEqual(r.status_code, 200)
                self.assertNotIn("<script", r.text.lower())
        self.assertIn("&lt;script&gt;", pages["admin home"].text)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class BurstTests(unittest.TestCase):
    N = 30

    def test_concurrent_burst_then_backup_restore_drill(self):
        path = testutil.fresh_db()
        logins = [f"burst{n:02d}" for n in range(self.N)]
        for login in logins:
            make_user("student", login)  # default subjects: English, Gaeilge T2, History
        with db.session_scope() as s:
            strands = [
                content.Strand("english", "general"),
                content.Strand("gaeilge", "T2"),
                content.Strand("history", "general"),
            ]
            plan = [
                (t.slug, len(content.topic_versions(s, t, "question", include_drafts=True)))
                for st in strands
                for t in content.strand_topics(s, st, include_drafts=True)
            ]
        per_set = sum(n for _, n in plan)  # questions answered per student
        self.assertGreaterEqual(per_set, 5)
        db.dispose()
        port = free_port()
        env = dict(
            os.environ,
            SCOILMATE_DB=str(path),
            SCOILMATE_ALLOW_DRAFT_PRACTICE="1",
            SCOILMATE_SECURE_COOKIES="0",
        )
        log = open(testutil.TMP / "burst-server.log", "w+", encoding="utf-8")
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "scoilmate.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-proxy-headers",
                "--log-level",
                "warning",
            ],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        base = f"http://127.0.0.1:{port}"
        statuses, errors = [], []
        try:
            for _ in range(150):
                try:
                    if httpx.get(base + "/health", timeout=1).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                self.assertIsNone(server.poll(), "server exited")
                time.sleep(0.1)
            # log everyone in first (Argon2 is deliberately slow), then burst the practice traffic
            clients = []
            for login in logins:
                c = httpx.Client(base_url=base, timeout=60, follow_redirects=False)
                token = re.search(
                    r'name="csrf-token" content="([^"]*)"', c.get("/login").text
                ).group(1)
                r = c.post(
                    "/login", data={"login": login, "password": PASSWORD, "csrf_token": token}
                )
                self.assertEqual(r.status_code, 303)
                token = re.search(
                    r'name="csrf-token" content="([^"]*)"', c.get("/practice").text
                ).group(1)
                clients.append((c, token))
            barrier = threading.Barrier(self.N)
            lock = threading.Lock()

            def student(c, token):
                try:
                    barrier.wait(timeout=30)
                    got = []
                    for topic, count in plan:
                        r = c.post(
                            f"/practice/topic/{topic}/start",
                            data={"csrf_token": token, "confidence": "3"},
                        )
                        got.append(r.status_code)
                        set_id = re.search(r"/practice/set/(\d+)/", r.headers["location"]).group(1)
                        for n in range(1, count + 1):
                            got.append(
                                c.post(
                                    f"/practice/set/{set_id}/q/{n}/hint", data={"csrf_token": token}
                                ).status_code
                            )
                            got.append(
                                c.post(
                                    f"/practice/set/{set_id}/q/{n}",
                                    data={"csrf_token": token, "option": "A"},
                                ).status_code
                            )
                        got.append(
                            c.post(
                                f"/practice/set/{set_id}/finish", data={"csrf_token": token}
                            ).status_code
                        )
                        got.append(c.get(f"/practice/set/{set_id}/summary").status_code)
                    with lock:
                        statuses.extend(got)
                except Exception as exc:  # noqa: BLE001 - recorded and asserted below
                    with lock:
                        errors.append(repr(exc))

            started = time.monotonic()
            threads = [threading.Thread(target=student, args=ct) for ct in clients]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=120)
            elapsed = time.monotonic() - started
            for c, _ in clients:
                c.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
            log.seek(0)
            server_log = log.read()
            log.close()
        self.assertIsNotNone(server.poll(), "temporary server still running")
        self.assertEqual(errors, [], server_log[-2000:])
        expected_requests = self.N * (3 * len(plan) + 2 * per_set)
        self.assertEqual(len(statuses), expected_requests)
        bad = [s for s in statuses if s >= 400]
        self.assertEqual(bad, [], server_log[-2000:])
        self.assertNotIn("Traceback", server_log)
        settings.db_path = path
        with db.session_scope() as s:
            sets = s.scalars(select(PracticeSet).where(PracticeSet.kind == "topic")).all()
            self.assertEqual(len(sets), self.N * len(plan))
            self.assertTrue(all(ps.completed_at is not None and ps.confidence == 3 for ps in sets))
            answers = s.scalar(select(func.count()).select_from(Response))
            self.assertEqual(answers, self.N * per_set)  # no lost and no duplicate attempts
            hinted = s.scalar(
                select(func.count()).select_from(Response).where(Response.hints_used == 1)
            )
            self.assertEqual(hinted, self.N * per_set)
        print(
            f"\n  burst: {self.N} students x {expected_requests // self.N} requests "
            f"({expected_requests} total) in {elapsed:.1f}s, 0 errors, {answers} answers stored",
            file=sys.stderr,
        )

        # Backup/restore drill through the CLI (as an operator would do it), server stopped.
        db.dispose()
        backup = testutil.TMP / f"burst-backup-{port}.db"
        cli = [sys.executable, "-m", "scoilmate.cli"]
        out = subprocess.run(
            cli + ["backup", "--out", str(backup)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(oct(backup.stat().st_mode & 0o777), "0o600")
        with db.session_scope() as s:  # simulate loss after the backup
            s.query(Response).delete()
        db.dispose()
        out = subprocess.run(
            cli + ["restore", "--yes", str(backup)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        with db.session_scope() as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(Response)), answers)


if __name__ == "__main__":
    unittest.main()
