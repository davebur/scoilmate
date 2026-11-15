"""Accounts: login, sessions, cookies, CSRF, rate limits, permission matrix, IDOR, audit."""

import hashlib
import os
import re
import subprocess
import sys
import unittest
from datetime import timedelta

try:
    import testutil
    from sqlalchemy import func, select, update
    from testutil import PASSWORD, Client, make_user

    from scoilmate import db
    from scoilmate.app import app
    from scoilmate.config import settings
    from scoilmate.db import utcnow
    from scoilmate.models import AuditLog, AuthSession, ParentStudent, User
except ImportError as exc:
    raise unittest.SkipTest(f"dependencies unavailable: {exc}")


def audit_actions():
    with db.session_scope() as s:
        return [a for a in s.scalars(select(AuditLog.action).order_by(AuditLog.id))]


class Family(unittest.TestCase):
    """admin; parent p1 with child s1; parent p2 with child s2."""

    def setUp(self):
        testutil.fresh_db()
        testutil.reset_limits()
        self.admin = make_user("admin", "admin1")
        self.p1 = make_user("parent", "parent1", email="p1@example.invalid")
        self.p2 = make_user("parent", "parent2")
        self.s1 = make_user("student", "student1", parent=self.p1)
        self.s2 = make_user("student", "student2", parent=self.p2)

    def as_(self, login):
        return Client().login(login)


class LoginTests(Family):
    def test_generic_login_errors(self):
        c = Client()
        bodies = []
        for login, pw in (
            ("nobody", PASSWORD),
            ("student1", "wrong-password"),
            ("student1", "x" * 500),
        ):
            r = c.submit("/login", {"login": login, "password": pw})
            self.assertEqual(r.status_code, 400)
            bodies.append(re.search(r'role="alert">([^<]*)<', r.text).group(1))
        self.assertEqual(len(set(bodies)), 1)
        self.assertNotIn("student1", bodies[0])

    def test_disabled_account_cannot_log_in(self):
        with db.session_scope() as s:
            s.get(User, self.s1).status = "disabled"
        r = Client().submit("/login", {"login": "student1", "password": PASSWORD})
        self.assertEqual(r.status_code, 400)

    def test_cookie_flags_and_token_digest(self):
        c = Client()
        r = c.submit(
            "/login", {"login": "Student1 ", "password": PASSWORD}
        )  # login names normalised
        self.assertEqual((r.status_code, r.headers["location"]), (303, "/practice"))
        cookie = [
            h for h in r.headers.get_list("set-cookie") if h.startswith("scoilmate_session=")
        ][0]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=lax", cookie)
        self.assertNotIn("Secure", cookie)
        token = c.cookies.get("scoilmate_session")
        with db.session_scope() as s:
            rows = s.scalars(select(AuthSession)).all()
            self.assertEqual(
                [x.token_digest for x in rows], [hashlib.sha256(token.encode()).hexdigest()]
            )
            self.assertNotIn(token, str([(x.token_digest, x.csrf_token) for x in rows]))

    def test_secure_cookie_setting(self):
        testutil.fresh_db(secure_cookies=True)
        make_user("student", "secure1")
        c = Client(base_url="https://testserver")
        r = c.submit("/login", {"login": "secure1", "password": PASSWORD})
        cookie = [
            h for h in r.headers.get_list("set-cookie") if h.startswith("__Host-scoilmate_session=")
        ][0]
        for flag in ("Secure", "HttpOnly", "SameSite=lax", "Path=/"):
            self.assertIn(flag, cookie)
        self.assertNotIn("Domain", cookie)
        self.assertIn("Strict-Transport-Security", r.headers)

    def test_session_rotation_and_logout(self):
        c = self.as_("student1")
        old = c.cookies.get("scoilmate_session")
        c.login("parent1")  # logging in again from the same browser replaces the session
        self.assertNotEqual(c.cookies.get("scoilmate_session"), old)
        stale = Client()
        stale.cookies.set("scoilmate_session", old)
        self.assertEqual(stale.get("/me/settings", follow_redirects=False).status_code, 303)
        r = c.submit("/logout")
        self.assertEqual(r.status_code, 303)
        with db.session_scope() as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(AuthSession)), 0)

    def test_session_idle_and_absolute_expiry(self):
        for column in ("idle_expires_at", "absolute_expires_at"):
            with self.subTest(column=column):
                c = self.as_("student1")
                self.assertEqual(c.get("/me/settings").status_code, 200)
                with db.session_scope() as s:
                    s.execute(update(AuthSession).values({column: utcnow() - timedelta(seconds=1)}))
                r = c.get("/me/settings", follow_redirects=False)
                self.assertEqual(
                    (r.status_code, r.headers["location"]), (303, "/login?next=/me/settings")
                )

    def test_admin_sessions_are_shorter(self):
        self.as_("admin1")
        self.as_("student1")
        with db.session_scope() as s:
            spans = {
                sess.user.role: sess.absolute_expires_at - sess.created_at
                for sess in s.scalars(select(AuthSession))
            }
        self.assertLess(spans["admin"], spans["student"])

    def test_login_rate_limit_429(self):
        c = Client()
        for _ in range(settings.login_max_per_account):
            self.assertEqual(
                c.submit("/login", {"login": "student1", "password": "nope-nope"}).status_code, 400
            )
        r = c.submit(
            "/login", {"login": "student1", "password": PASSWORD}
        )  # even the right password waits
        self.assertEqual(r.status_code, 429)
        self.assertGreater(int(r.headers["Retry-After"]), 0)
        self.assertEqual(
            Client().submit("/login", {"login": "parent1", "password": PASSWORD}).status_code, 303
        )

    def test_ip_rate_limit(self):
        old = settings.login_max_per_ip
        settings.login_max_per_ip = 3
        try:
            c = Client()
            for i in range(3):
                c.submit("/login", {"login": f"guess{i}", "password": "nope-nope"})
            self.assertEqual(
                c.submit("/login", {"login": "parent1", "password": PASSWORD}).status_code, 429
            )
        finally:
            settings.login_max_per_ip = old

    def test_login_next_is_local_only(self):
        for target, expected in (
            ("/me/settings", "/me/settings"),
            ("//evil.example/x", "/practice"),
            ("https://evil.example/", "/practice"),
        ):
            r = Client().submit(
                "/login", {"login": "student1", "password": PASSWORD, "next": target}
            )
            self.assertEqual(r.headers["location"], expected)


class CsrfTests(Family):
    def post_routes(self):
        yield from (
            re.sub(r"\{[^}]+\}", "x", path)
            for path, methods in testutil.all_routes()
            if "POST" in methods
        )

    def test_every_post_requires_csrf(self):
        c = self.as_("admin1")
        good = c.token()
        paths = list(self.post_routes())
        self.assertGreater(len(paths), 10)
        for path in paths:
            for data in ({}, {"csrf_token": "wrong"}, {"csrf_token": ""}):
                with self.subTest(path=path, data=data):
                    self.assertEqual(
                        c.post(path, data=data, follow_redirects=False).status_code, 403
                    )
        # another session's token is not accepted either
        other = self.as_("parent1").token()
        self.assertEqual(c.post("/logout", data={"csrf_token": other}).status_code, 403)
        self.assertEqual(
            c.post("/logout", data={"csrf_token": good}, follow_redirects=False).status_code, 303
        )

    def test_cross_origin_rejected(self):
        c = self.as_("admin1")
        r = c.post(
            "/admin/users/new",
            data={"csrf_token": c.token(), "role": "parent"},
            headers={"Origin": "https://evil.example"},
        )
        self.assertEqual(r.status_code, 403)

    def test_login_form_needs_csrf(self):
        c = Client()
        r = c.post("/login", data={"login": "student1", "password": PASSWORD})
        self.assertEqual(r.status_code, 403)


class PermissionTests(Family):
    def test_no_default_admin_and_cli(self):
        path = testutil.TMP / "cli-admin.db"
        env = dict(os.environ, SCOILMATE_DB=str(path), SCOILMATE_ADMIN_PASSWORD="")
        run = lambda *a, **kw: subprocess.run(
            [sys.executable, "-m", "scoilmate.cli", *a],
            cwd=testutil.ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            **kw,
        )
        self.assertEqual(run("migrate", env=env).returncode, 0)
        import sqlite3
        from contextlib import closing

        q = lambda sql: closing(sqlite3.connect(path)).__enter__().execute(sql).fetchone()
        self.assertEqual(q("SELECT count(*) FROM user")[0], 0)
        env["SCOILMATE_ADMIN_PASSWORD"] = "short"
        self.assertNotEqual(run("create-admin", "boss", env=env).returncode, 0)
        env["SCOILMATE_ADMIN_PASSWORD"] = "a-long-test-password"
        r = run("create-admin", "boss", "--name", "Test Admin", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("a-long-test-password", r.stdout + r.stderr)
        row = q("SELECT role, password_hash FROM user")
        self.assertEqual(row[0], "admin")
        self.assertTrue(row[1].startswith("$argon2id$"))

    def test_admin_adds_student_and_parent_and_links(self):
        c = self.as_("admin1")
        r = c.submit(
            "/admin/users/new",
            {
                "role": "parent",
                "login": "newparent",
                "display_name": "New Parent",
                "email": "np@example.invalid",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("newparent", r.text)
        with db.session_scope() as s:
            np = s.scalar(select(User).where(User.login == "newparent"))
        r = c.submit(
            "/admin/users/new",
            {
                "role": "student",
                "login": "newkid",
                "display_name": "Kid",
                "password": "kid-password-1",
                "subj_english": "on",
                "level_english": "higher",
                "parent_id": np.id,
                "school_year": "2",
            },
        )
        self.assertEqual(r.status_code, 200)
        with db.session_scope() as s:
            kid = s.scalar(select(User).where(User.login == "newkid"))
            self.assertEqual([(x.subject, x.level) for x in kid.subjects], [("english", "higher")])
            self.assertEqual(kid.school_year, 2)
            self.assertIsNone(kid.email)
            links = s.scalars(
                select(ParentStudent.parent_id).where(ParentStudent.student_id == kid.id)
            ).all()
        self.assertEqual(links, [np.id])
        Client().login("newkid", "kid-password-1")
        c.submit(f"/admin/users/{kid.id}/link", {"other_id": self.p1})
        c.submit(f"/admin/users/{kid.id}/link", {"other_id": np.id, "unlink": "1"})
        with db.session_scope() as s:
            links = s.scalars(
                select(ParentStudent.parent_id).where(ParentStudent.student_id == kid.id)
            ).all()
        self.assertEqual(links, [self.p1])
        for action in ("parent_created", "student_created", "link_added", "link_removed"):
            self.assertIn(action, audit_actions())

    def test_duplicate_and_invalid_logins_rejected(self):
        c = self.as_("admin1")
        for login in ("student1", "a", "bad name!", "<script>"):
            r = c.submit(
                "/admin/users/new", {"role": "student", "login": login, "display_name": "X"}
            )
            self.assertEqual(r.status_code, 400, login)

    def test_parent_adds_child_auto_linked_and_manages_it(self):
        c = self.as_("parent1")
        r = c.submit(
            "/parent/children/new",
            {"login": "kid3", "display_name": "Kid Three", "subj_history": "on"},
        )
        self.assertEqual(r.status_code, 200)
        password = re.search(r"Password</dt><dd><code>([^<]+)</code>", r.text).group(1)
        with db.session_scope() as s:
            kid = s.scalar(select(User).where(User.login == "kid3"))
            self.assertEqual(
                s.scalars(
                    select(ParentStudent.parent_id).where(ParentStudent.student_id == kid.id)
                ).all(),
                [self.p1],
            )
        kid_client = Client().login("kid3", password)
        r = c.submit(
            f"/parent/children/{kid.id}/settings",
            {"display_name": "K3", "school_year": "3", "subj_gaeilge": "on", "track_gaeilge": "T1"},
        )
        self.assertEqual(r.status_code, 303)
        r = c.submit(f"/parent/children/{kid.id}/reset")
        new_pw = re.search(r"Password</dt><dd><code>([^<]+)</code>", r.text).group(1)
        self.assertEqual(
            kid_client.get("/me/settings", follow_redirects=False).status_code, 303
        )  # logged out
        kid_client = Client().login("kid3", new_pw)
        c.submit(f"/parent/children/{kid.id}/status", {"active": "0"})
        self.assertEqual(kid_client.get("/me/settings", follow_redirects=False).status_code, 303)
        self.assertEqual(
            Client().submit("/login", {"login": "kid3", "password": new_pw}).status_code, 400
        )
        c.submit(f"/parent/children/{kid.id}/status", {"active": "1"})
        Client().login("kid3", new_pw)
        for action in (
            "student_created",
            "link_added",
            "settings_changed",
            "access_reset",
            "deactivated",
            "reactivated",
        ):
            self.assertIn(action, audit_actions())

    def test_student_edits_only_own_year_and_subjects(self):
        c = self.as_("student1")
        r = c.submit(
            "/me/settings", {"school_year": "1", "subj_english": "on", "display_name": "Hacked"}
        )
        self.assertEqual(r.status_code, 303)
        with db.session_scope() as s:
            me = s.get(User, self.s1)
            self.assertEqual((me.display_name, me.school_year), ("Student1", 1))
        self.assertEqual(c.submit("/me/settings", {"school_year": "7"}).status_code, 400)

    def test_deletion_request_and_admin_confirm_erases_data(self):
        p = self.as_("parent1")
        p.submit(f"/parent/children/{self.s1}/deletion")
        a = self.as_("admin1")
        self.assertIn("Deletion requests", a.get("/admin").text)
        self.assertEqual(
            a.submit(f"/admin/users/{self.s1}/delete", {"confirm": "wrong"}).status_code, 400
        )
        r = a.submit(f"/admin/users/{self.s1}/delete", {"confirm": "student1"})
        self.assertEqual(r.status_code, 200)
        with db.session_scope() as s:
            self.assertIsNone(s.get(User, self.s1))
            self.assertEqual(
                s.scalar(
                    select(func.count())
                    .select_from(ParentStudent)
                    .where(ParentStudent.student_id == self.s1)
                ),
                0,
            )
            leftovers = s.scalars(
                select(AuditLog.detail).where(AuditLog.detail.contains("student1"))
            ).all()
            self.assertEqual(leftovers, [])
        self.assertIn("student_deleted", audit_actions())
        self.assertIn("deletion_requested", audit_actions())

    def test_removing_parent_keeps_children_and_flags_orphans(self):
        a = self.as_("admin1")
        r = a.submit(f"/admin/users/{self.p2}/delete", {"confirm": "parent2"})
        self.assertIn("no linked parent", r.text)
        with db.session_scope() as s:
            self.assertIsNotNone(s.get(User, self.s2))
        self.assertIn("Students without a parent", a.get("/admin").text)

    def test_admin_cannot_delete_or_deactivate_self(self):
        a = self.as_("admin1")
        self.assertEqual(
            a.submit(f"/admin/users/{self.admin}/delete", {"confirm": "admin1"}).status_code, 400
        )
        self.assertEqual(
            a.submit(f"/admin/users/{self.admin}/status", {"active": "0"}).status_code, 400
        )


class IdorTests(Family):
    """Every role pair: who may reach which page/object. 404 hides other families' students."""

    def matrix(self):
        s1, s2, p1, p2 = self.s1, self.s2, self.p1, self.p2
        return [  # (method, path, data, {actor: expected status})
            ("GET", "/admin", None, {"admin1": 200, "parent1": 403, "student1": 403, None: 303}),
            (
                "GET",
                "/admin/users/new?role=student",
                None,
                {"admin1": 200, "parent1": 403, "student1": 403},
            ),
            ("GET", "/admin/users/new?role=parent", None, {"admin1": 200}),
            ("GET", "/parent/children/new", None, {"parent1": 200, "admin1": 403, "student1": 403}),
            (
                "GET",
                "/admin/audit",
                None,
                {"admin1": 200, "parent1": 403, "student1": 403, None: 303},
            ),
            ("GET", f"/admin/users/{s1}", None, {"admin1": 200, "parent1": 403, "student1": 403}),
            ("GET", f"/admin/users/{p2}", None, {"admin1": 200, "parent1": 403, "student1": 403}),
            (
                "POST",
                "/admin/users/new",
                {"role": "parent", "login": "sneaky", "display_name": "S"},
                {"parent1": 403, "student1": 403},
            ),
            (
                "POST",
                f"/admin/users/{s2}/link",
                {"other_id": p1},
                {"parent1": 403, "student1": 403},
            ),
            (
                "POST",
                f"/admin/users/{s2}/delete",
                {"confirm": "student2"},
                {"parent1": 403, "student1": 403},
            ),
            ("POST", f"/admin/users/{s2}/reset", {}, {"parent1": 403, "student1": 403}),
            ("GET", "/parent", None, {"admin1": 403, "parent1": 200, "student1": 403, None: 303}),
            (
                "GET",
                f"/parent/children/{s1}",
                None,
                {"parent1": 200, "parent2": 404, "student1": 403, "admin1": 403},
            ),
            ("GET", f"/parent/children/{s2}", None, {"parent1": 404, "parent2": 200}),
            ("GET", f"/parent/children/{p2}", None, {"parent1": 404}),  # not a student at all
            ("GET", "/parent/children/does-not-exist", None, {"parent1": 404}),
            (
                "POST",
                f"/parent/children/{s2}/settings",
                {"subj_english": "on"},
                {"parent1": 404, "student2": 403},
            ),
            ("POST", f"/parent/children/{s2}/reset", {}, {"parent1": 404, "student2": 403}),
            ("POST", f"/parent/children/{s2}/status", {"active": "0"}, {"parent1": 404}),
            ("POST", f"/parent/children/{s2}/deletion", {}, {"parent1": 404}),
            (
                "POST",
                "/parent/children/new",
                {"login": "sneaky2", "display_name": "S"},
                {"student1": 403, "admin1": 403},
            ),
            (
                "GET",
                "/me/settings",
                None,
                {"student1": 200, "parent1": 403, "admin1": 403, None: 303},
            ),
        ]

    def test_role_pairs(self):
        clients = {None: Client()}
        for login in ("admin1", "parent1", "parent2", "student1", "student2"):
            clients[login] = self.as_(login)
        for method, path, data, expectations in self.matrix():
            for actor, expected in expectations.items():
                with self.subTest(actor=actor, method=method, path=path):
                    c = clients[actor]
                    r = (
                        c.get(path, follow_redirects=False)
                        if method == "GET"
                        else c.submit(path, data, follow_redirects=False)
                    )
                    self.assertEqual(r.status_code, expected)
        with db.session_scope() as s:  # nothing above changed another family's data
            self.assertEqual(s.get(User, self.s2).status, "active")
            self.assertIsNone(s.scalar(select(User).where(User.login.in_(("sneaky", "sneaky2")))))
            self.assertEqual(
                s.scalars(
                    select(ParentStudent.parent_id).where(ParentStudent.student_id == self.s2)
                ).all(),
                [self.p2],
            )


if __name__ == "__main__":
    unittest.main()
