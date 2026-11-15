"""Step 6: recorded practice, mastery rules, revisit ladder, mixed/mistake reviews, confidence,
reports for students/parents/admins, exports. Pure rule tests first, then HTTP tests."""

import json
import re
import unittest
from datetime import datetime, timedelta

try:
    import testutil
    from sqlalchemy import func, select
    from testutil import Client, make_user

    from scoilmate import db, learning
    from scoilmate.config import settings
    from scoilmate.learning import TopicState, apply_mixed, apply_topic_set, set_level
    from scoilmate.models import (
        Activity,
        Base,
        ContentRating,
        HintEvent,
        PracticeItem,
        PracticeSet,
        RatingReceipt,
        Response,
        TopicProgress,
    )
except ImportError as exc:
    raise unittest.SkipTest(f"dependencies unavailable: {exc}") from exc

DATA = json.loads((testutil.ROOT / "content/draft-samples.json").read_text())
BY_PROMPT = {q["prompt"]: q for q in DATA["questions"]}
T0 = datetime(2026, 11, 2, 16, 0)


class RuleTests(unittest.TestCase):
    def test_hint_credit_and_set_levels(self):
        self.assertEqual(learning.credit(True, 0), 1.0)
        self.assertEqual(learning.credit(True, 1), 0.5)
        self.assertEqual(learning.credit(True, 2), 0.0)
        self.assertEqual(learning.credit(False, 0), 0.0)
        self.assertEqual(set_level([(True, 0)] * 5)[0], "proficient")
        self.assertEqual(
            set_level([(True, 0)] * 4 + [(True, 1)])[0], "proficient"
        )  # one 1-hint answer is OK
        self.assertEqual(set_level([(True, 0)] * 3 + [(True, 1)] * 2)[0], "familiar")  # 80%
        self.assertEqual(set_level([(True, 0)] * 4 + [(True, 2)])[0], "familiar")
        self.assertEqual(set_level([(True, 0)] * 4 + [(False, 0)])[0], "familiar")  # 80%
        self.assertEqual(set_level([(True, 0)] * 3 + [(False, 0)] * 2)[0], "attempted")  # 60%

    def test_revisit_ladder(self):
        st = TopicState()
        apply_topic_set(st, T0, [(False, 0)])
        self.assertEqual((st.level, st.due_at - T0), ("attempted", timedelta(days=1)))
        apply_topic_set(st, T0, [(True, 0)] * 4 + [(False, 0)])
        self.assertEqual((st.level, st.due_at - T0), ("familiar", timedelta(days=3)))
        apply_topic_set(st, T0, [(True, 0)])
        self.assertEqual((st.level, st.due_at - T0), ("proficient", timedelta(days=7)))
        t1 = T0 + timedelta(days=3)
        apply_mixed(st, t1, [(True, 0)])
        self.assertEqual((st.level, st.due_at - t1), ("mastered", timedelta(days=21)))
        t2 = t1 + timedelta(days=21)
        apply_mixed(st, t2, [(True, 0)])
        self.assertEqual((st.level, st.due_at - t2), ("mastered", timedelta(days=45)))

    def test_mastered_only_through_delayed_mixed_review(self):
        st = TopicState()
        apply_topic_set(st, T0, [(True, 0)])
        apply_topic_set(
            st, T0 + timedelta(days=5), [(True, 0)]
        )  # topic practice never gives Mastered
        self.assertEqual(st.level, "proficient")
        apply_mixed(st, T0 + timedelta(days=2), [(True, 0)])  # too soon
        self.assertEqual(st.level, "proficient")
        self.assertIn("at least 3 days", st.reason)
        apply_mixed(
            st, T0 + timedelta(days=3), [(True, 1)]
        )  # hint used: not clean -> drops one step
        self.assertEqual(st.level, "familiar")

    def test_levels_drop_one_step_at_a_time(self):
        st = TopicState()
        apply_topic_set(st, T0, [(True, 0)])
        apply_mixed(st, T0 + timedelta(days=4), [(True, 0)])
        self.assertEqual(st.level, "mastered")
        apply_topic_set(
            st, T0 + timedelta(days=5), [(False, 0)]
        )  # earned Attempted, but only one step down
        self.assertEqual(st.level, "proficient")
        apply_mixed(st, T0 + timedelta(days=6), [(False, 0)])
        self.assertEqual(st.level, "familiar")
        apply_topic_set(st, T0 + timedelta(days=7), [(False, 0)])
        self.assertEqual(st.level, "attempted")

    def test_every_level_has_a_plain_rule(self):
        for level in learning.LEVELS:
            self.assertTrue(learning.RULES[level])


class Practice(unittest.TestCase):
    def setUp(self):
        testutil.fresh_db()
        testutil.reset_limits()
        self.admin = make_user("admin", "admin1")
        self.p1 = make_user("parent", "parent1")
        self.p2 = make_user("parent", "parent2")
        self.s1 = make_user("student", "student1", parent=self.p1)
        self.s2 = make_user("student", "student2", parent=self.p2)
        self.c = Client().login("student1")

    def start(self, path, confidence=""):
        r = self.c.submit(path, {"confidence": confidence})
        self.assertEqual(r.status_code, 303, r.text[:300])
        return int(re.search(r"/practice/set/(\d+)/", r.headers["location"]).group(1))

    def question_at(self, set_id, n):
        html = self.c.get(f"/practice/set/{set_id}/q/{n}").text
        prompt = re.search(r"</span> ([^<]+)</legend>", html).group(1)
        return (
            BY_PROMPT[prompt.replace("&#39;", "'").replace("&amp;", "&").replace("&#34;", '"')],
            html,
        )

    def run_set(self, set_id, plan):
        """plan: list of (correct?, hints) per question in order; then finish."""
        for n, (ok, hints) in enumerate(plan, 1):
            q, _ = self.question_at(set_id, n)
            for _ in range(hints):
                self.c.submit(f"/practice/set/{set_id}/q/{n}/hint")
            choice = (
                q["correct_option_id"]
                if ok
                else next(o["id"] for o in q["options"] if o["id"] != q["correct_option_id"])
            )
            self.assertEqual(
                self.c.submit(f"/practice/set/{set_id}/q/{n}", {"option": choice}).status_code, 200
            )
        self.assertEqual(self.c.submit(f"/practice/set/{set_id}/finish").status_code, 303)
        return self.c.get(f"/practice/set/{set_id}/summary")

    def shift_history(self, days):
        """Move all recorded practice back in time (to test spacing) and rebuild progress."""
        delta = timedelta(days=days)
        with db.session_scope() as s:
            for ps in s.scalars(select(PracticeSet)):
                ps.started_at -= delta
                ps.completed_at = ps.completed_at - delta if ps.completed_at else None
            s.flush()
            for sid in (self.s1, self.s2):
                learning.refresh_cache(s, sid)


class PracticeFlowTests(Practice):
    def test_practice_requires_student_login(self):
        self.assertEqual(Client().get("/practice", follow_redirects=False).status_code, 303)
        self.assertEqual(Client().login("parent1").get("/practice").status_code, 403)
        self.assertEqual(Client().login("admin1").get("/practice/topic/simile").status_code, 403)
        self.assertEqual(self.c.get("/practice").status_code, 200)

    def test_question_pages_never_leak_keys_and_hints_are_server_recorded(self):
        for topic in (
            "simile",
            "purpose",
            "inference",
            "primary",
            "corroboration",
            "continuity",
            "ga-message",
            "ga-time",
        ):
            with self.subTest(topic=topic):
                sid = self.start(f"/practice/topic/{topic}/start")
                q, html = self.question_at(sid, 1)
                self.assertNotIn(q["explanation"], html)
                self.assertNotIn(q["hints"][0], html)
                self.assertNotIn("correct_option", html)
                for _i in range(len(q["hints"]) + 2):  # extra requests are capped
                    self.c.submit(f"/practice/set/{sid}/q/1/hint")
                html = self.c.get(f"/practice/set/{sid}/q/1").text
                for h in q["hints"]:
                    self.assertIn(h.replace("'", "&#39;"), html)
                self.assertNotIn(q["explanation"], html)
        with db.session_scope() as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(HintEvent)), 16)

    def test_gaeilge_t1_hidden_unless_chosen(self):
        self.assertEqual(
            self.c.get("/practice/topic/ga-register").status_code, 404
        )  # default track is T2
        self.c.submit("/me/settings", {"subj_gaeilge": "on", "track_gaeilge": "T1"})
        self.assertEqual(self.c.get("/practice/topic/ga-register").status_code, 200)
        self.assertEqual(self.c.get("/practice/topic/simile").status_code, 404)  # English unticked

    def test_answers_first_only_invalid_and_missing(self):
        sid = self.start("/practice/topic/simile/start", confidence="3")
        q, _ = self.question_at(sid, 1)
        self.assertEqual(
            self.c.submit(f"/practice/set/{sid}/q/1", {"option": "Z"}).status_code, 400
        )
        r = self.c.submit(f"/practice/set/{sid}/q/1", {})
        self.assertIn("Choose an answer", r.text)
        wrong = next(o["id"] for o in q["options"] if o["id"] != q["correct_option_id"])
        r = self.c.submit(f"/practice/set/{sid}/q/1", {"option": wrong})
        self.assertIn("Not this time", r.text)
        self.assertIn(q["explanation"], r.text.replace("&#39;", "'"))
        r = self.c.submit(f"/practice/set/{sid}/q/1", {"option": q["correct_option_id"]})
        self.assertIn("first answer is the one that counts", r.text)
        with db.session_scope() as s:
            rows = s.scalars(select(Response)).all()
            self.assertEqual([(x.selected, x.is_correct) for x in rows], [(wrong, False)])
        self.c.submit(f"/practice/set/{sid}/finish")
        summary = self.c.get(f"/practice/set/{sid}/summary").text
        self.assertIn("you felt <b>“mostly”</b> confident, and you got <b>0 of 1</b>", summary)
        self.assertIn("Attempted", summary)

    def test_attempt_pins_versions_used(self):
        sid = self.start("/practice/topic/simile/start")
        with db.session_scope() as s:
            item = s.get(PracticeSet, sid).items[0]
            self.assertEqual((item.question.item.slug, item.question.version), ("q-simile", 1))
            self.assertEqual(item.lesson.item.slug, "lesson-simile")

    def test_mastery_path_and_cache_matches_replay(self):
        self.assertIn(
            "Proficient", self.run_set(self.start("/practice/topic/simile/start"), [(True, 0)]).text
        )
        self.run_set(self.start("/practice/topic/purpose/start"), [(True, 1)])
        self.run_set(self.start("/practice/topic/inference/start"), [(False, 0)])
        self.assertEqual(
            self.c.get("/practice/mixed/history").text.count("Practise at least 2 topics"), 1
        )
        self.shift_history(4)
        sid = self.start("/practice/mixed/english/start")
        with db.session_scope() as s:
            self.assertEqual(len(s.get(PracticeSet, sid).items), 3)
        summary = self.run_set(sid, [(True, 0)] * 3).text
        self.assertIn("Mastered", summary)
        with db.session_scope() as s:
            cache = {
                (p.topic_id, p.level, p.due_at, p.reason) for p in s.scalars(select(TopicProgress))
            }
            fresh = learning.replay(s, self.s1)
            self.assertEqual(
                cache, {(tid, st.level, st.due_at, st.reason[:300]) for tid, st in fresh.items()}
            )
            levels = sorted(st.level for st in fresh.values())
        self.assertEqual(levels, ["attempted", "mastered", "mastered"])  # inference stays Attempted

    def test_mistake_review(self):
        self.run_set(self.start("/practice/topic/simile/start"), [(False, 0)])
        self.run_set(self.start("/practice/topic/primary/start"), [(False, 0)])
        self.assertIn("Redo my wrong answers (2)", self.c.get("/practice").text)
        sid = self.start("/practice/mistakes/start")
        self.run_set(sid, [(True, 0), (False, 0)])
        self.assertIn("Redo my wrong answers (1)", self.c.get("/practice").text)

    def test_what_next_and_private_reflection(self):
        sid = self.start("/practice/topic/simile/start")
        self.run_set(sid, [(True, 0)])
        r = self.c.submit(
            f"/practice/set/{sid}/next", {"choice": "mixed", "reflection": "SECRET-NOTE <b>x</b>"}
        )
        self.assertEqual(r.headers["location"], "/practice/mixed/english")
        mine = self.c.get("/progress").text
        self.assertIn("SECRET-NOTE &lt;b&gt;x&lt;/b&gt;", mine)
        self.assertIn("private notes are only shown to you", mine)
        parent = Client().login("parent1").get(f"/parent/children/{self.s1}/report").text
        admin = Client().login("admin1").get(f"/admin/reports/students/{self.s1}").text
        for html in (parent, admin):
            self.assertIn("Simile", html.replace("Comparisons in writing", "Simile"))
            self.assertNotIn("SECRET-NOTE", html)
        self.assertEqual(
            self.c.submit(f"/practice/set/{sid}/next", {"choice": "nonsense"}).status_code, 400
        )

    def test_ratings_anonymous_once_and_only_for_seen_items(self):
        sid = self.start("/practice/topic/simile/start")
        with db.session_scope() as s:
            item = s.get(PracticeSet, sid).items[0]
            qv, lv = item.question_version_id, item.lesson_version_id
        r = self.c.submit(
            "/practice/rate",
            {
                "version_id": qv,
                "rating": "down",
                "reason": "unclear",
                "back": f"/practice/set/{sid}/q/1",
            },
        )
        self.assertEqual(r.headers["location"], f"/practice/set/{sid}/q/1?thanks=1")
        self.c.submit("/practice/rate", {"version_id": qv, "rating": "up"})  # second vote ignored
        self.c.submit(
            "/practice/rate", {"version_id": lv, "rating": "up", "back": "//evil.example"}
        )
        with db.session_scope() as s:
            self.assertEqual(
                sorted((x.rating, x.reason) for x in s.scalars(select(ContentRating))),
                [("down", "unclear"), ("up", None)],
            )
            self.assertEqual(s.scalar(select(func.count()).select_from(RatingReceipt)), 2)
        cols = {c.name for c in ContentRating.__table__.columns}
        self.assertFalse(cols & {"user_id", "student_id", "ip"})
        other = Client().login("student2")
        self.assertEqual(
            other.submit("/practice/rate", {"version_id": qv + 100, "rating": "up"}).status_code,
            404,
        )
        self.assertEqual(
            other.submit("/practice/rate", {"version_id": qv, "rating": "meh"}).status_code, 400
        )

    def test_draft_content_hidden_when_setting_off(self):
        html = self.c.get("/practice/topic/simile").text
        self.assertIn("Draft, not teacher-reviewed", html)
        settings.allow_draft_practice = False
        try:
            self.assertEqual(self.c.get("/practice/topic/simile").status_code, 404)
            self.assertIn("No practice ready", self.c.get("/practice").text)
        finally:
            settings.allow_draft_practice = True


class ReportTests(Practice):
    def setUp(self):
        super().setUp()
        self.run_set(self.start("/practice/topic/simile/start", "4"), [(False, 0)])
        self.run_set(self.start("/practice/topic/primary/start"), [(True, 1)])

    def test_student_report_contents(self):
        html = self.c.get("/progress").text
        for text in (
            "Attempted",
            "Proficient",
            "Due for review",
            "Recent sessions",
            "Suggested next step",
            "not exam grades",
            "right with hints",
        ):
            self.assertIn(text, html)
        for banned in ("streak", "leaderboard", "rank", "average", "predicted", "Distinction"):
            self.assertNotIn(banned, html.lower().replace("arrange", ""))

    def test_parent_sees_own_child_only(self):
        p = Client().login("parent1")
        html = p.get(f"/parent/children/{self.s1}/report").text
        self.assertIn("Last active", html)
        self.assertIn("Weekly activity", html)
        self.assertEqual(p.get(f"/parent/children/{self.s2}/report").status_code, 404)
        self.assertEqual(
            Client().login("parent2").get(f"/parent/children/{self.s1}/report").status_code, 404
        )
        self.assertNotRegex(html, r"\d\d:\d\d")  # dates only, no time of day

    def test_set_idor_between_students(self):
        with db.session_scope() as s:
            sid = s.scalars(select(PracticeSet.id).where(PracticeSet.student_id == self.s1)).first()
        other = Client().login("student2")
        for path in (
            f"/practice/set/{sid}/q/1",
            f"/practice/set/{sid}/summary",
            f"/practice/set/{sid}/q/1/note",
        ):
            self.assertEqual(other.get(path).status_code, 404, path)
        for path in (
            f"/practice/set/{sid}/q/1",
            f"/practice/set/{sid}/q/1/hint",
            f"/practice/set/{sid}/finish",
            f"/practice/set/{sid}/next",
        ):
            self.assertEqual(other.submit(path, {"option": "A"}).status_code, 404, path)
        self.assertEqual(other.get(f"/admin/reports/students/{self.s1}").status_code, 403)
        self.assertEqual(Client().login("parent1").get("/admin/reports").status_code, 403)

    def test_admin_reports_and_csv(self):
        a = Client().login("admin1")
        html = a.get(f"/admin/reports/students/{self.s1}").text
        for text in ("Topics most often missed", "Ready to revisit", "Weekly activity"):
            self.assertIn(text, html)
        overview = a.get("/admin/reports?strand=english").text
        self.assertIn("Student1", overview)
        self.assertIn("Student2", overview)
        self.assertNotIn("Student1", a.get("/admin/reports?strand=english&year=3").text)
        stats = a.get("/admin/reports/questions").text
        self.assertIn("q-simile", stats)
        csv_text = a.get("/admin/reports/questions.csv").text
        self.assertTrue(
            csv_text.startswith("question,version,topic,prompt,first_answers,pct_correct")
        )
        self.assertIn("q-simile,1,", csv_text)
        cls = a.get("/admin/reports/class.csv?strand=history").text
        self.assertIn("Student1,student1,,Proficient", cls)

    def test_csv_formula_injection_neutralised(self):
        from scoilmate.reports import to_csv

        self.assertIn("'=HYPERLINK", to_csv(["a"], [['=HYPERLINK("x")']]))

    def test_exports(self):
        sid = None
        with db.session_scope() as s:
            sid = s.scalars(select(PracticeSet.id).where(PracticeSet.student_id == self.s1)).first()
        self.c.submit(f"/practice/set/{sid}/next", {"reflection": "my private note"})
        mine = self.c.get("/progress/export.json")
        self.assertIn("attachment", mine.headers["content-disposition"])
        data = mine.json()
        self.assertEqual(data["account"]["login"], "student1")
        self.assertEqual(len(data["practice_sets"]), 2)
        self.assertIn("my private note", mine.text)
        for c, path in (
            (Client().login("parent1"), f"/parent/children/{self.s1}/export.json"),
            (Client().login("admin1"), f"/admin/users/{self.s1}/export.json"),
        ):
            r = c.get(path)
            self.assertEqual(r.status_code, 200)
            self.assertNotIn("my private note", r.text)
            self.assertIn("private to the student", r.text)
        self.assertEqual(
            Client().login("parent2").get(f"/parent/children/{self.s1}/export.json").status_code,
            404,
        )

    def test_erasure_removes_every_trace(self):
        a = Client().login("admin1")
        self.assertEqual(
            a.submit(f"/admin/users/{self.s1}/delete", {"confirm": "student1"}).status_code, 200
        )
        with db.session_scope() as s:
            for table in Base.metadata.sorted_tables:
                for col in table.columns:
                    if col.foreign_keys and any(
                        fk.column.table.name == "user" for fk in col.foreign_keys
                    ):
                        n = s.scalar(select(func.count()).select_from(table).where(col == self.s1))
                        self.assertEqual(n, 0, f"{table.name}.{col.name}")
            self.assertEqual(s.scalar(select(func.count()).select_from(PracticeItem)), 0)
            self.assertEqual(s.scalar(select(func.count()).select_from(Response)), 0)
            self.assertEqual(s.scalar(select(func.count()).select_from(Activity)), 0)


class DemoSeedTests(unittest.TestCase):
    def test_seed_demo_creates_fake_accounts_with_history(self):
        testutil.fresh_db()
        from scoilmate import demo

        with db.session_scope() as s:
            logins = demo.seed(s)
        with self.assertRaises(ValueError):
            with db.session_scope() as s:
                demo.seed(s)
        with db.session_scope() as s:
            demo.seed(s, reset=True)
        self.assertEqual(len(logins), 6)
        c = Client().login("demo-student1", logins["demo-student1"])
        html = c.get("/progress").text
        self.assertIn("Mastered", html)
        self.assertIn("Demo note", html)
        p = Client().login("demo-parent1", logins["demo-parent1"])
        self.assertIn("Demo Student B", p.get("/parent").text)
        self.assertNotIn("Demo Student C", p.get("/parent").text)


if __name__ == "__main__":
    unittest.main()
