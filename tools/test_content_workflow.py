"""Step 7: admin content workflow.

Covers preview, review, publish, versioning, retire, ratings queue and wellbeing.
"""

import html
import re
import unittest

try:
    import testutil
    from sqlalchemy import select
    from testutil import Client, make_user

    from scoilmate import content, db
    from scoilmate.config import settings
    from scoilmate.models import (
        AuditLog,
        ContentItem,
        ContentRating,
        ContentVersion,
        PracticeItem,
        Topic,
    )
except ImportError as exc:
    raise unittest.SkipTest(f"dependencies unavailable: {exc}") from exc

XSS = "<script>alert(1)</script><img src=x onerror=alert(2)>\"'&"
TOPIC = "poetic-techniques"


def question_form(**over):
    form = {
        "kind": "question",
        "topic": TOPIC,
        "slug": "q-new-1",
        "prompt": "Which word is a simile marker?",
        "option_A": "like",
        "option_B": "run",
        "option_C": "blue",
        "correct_option_id": "A",
        "explanation": '"Like" introduces a comparison; the others do not.',
        "hint_1": "Similes compare.",
        "hint_2": "Look for a comparing word.",
        "hint_3": "Not a colour.",
    }
    form.update(over)
    return form


def versions(slug):
    with db.session_scope() as s:
        item = s.scalar(select(ContentItem).where(ContentItem.slug == slug))
        return [(v.version, v.status) for v in item.versions]


class Workflow(unittest.TestCase):
    def setUp(self):
        testutil.fresh_db()
        testutil.reset_limits()
        global TOPIC
        with db.session_scope() as s:  # any English topic from the sample content
            TOPIC = s.scalar(
                select(Topic.slug).where(Topic.subject == "english").order_by(Topic.id)
            )
        self.admin = make_user("admin", "admin1")
        self.p1 = make_user("parent", "parent1")
        self.s1 = make_user("student", "student1", parent=self.p1)
        self.a = Client().login("admin1")

    def create(self, **over):
        r = self.a.submit("/admin/content/new", question_form(**over))
        self.assertEqual(r.status_code, 303, r.text[:500])
        return r

    def review(self, slug, version, **over):
        data = {
            "reviewer_name": "Ms Teacher",
            "review_date": "",
            "note": "Checked accuracy and wording.",
        }
        data.update(over)
        return self.a.submit(f"/admin/content/{slug}/v/{version}/review", data)

    def publish(self, slug, version):
        return self.a.submit(f"/admin/content/{slug}/v/{version}/publish")


class AuthoringTests(Workflow):
    def test_only_admins_reach_content_pages(self):
        self.create()
        others = {"parent1": 403, "student1": 403, None: 303}
        paths = [
            "/admin/content",
            f"/admin/content/new?kind=question&topic={TOPIC}",
            "/admin/content/q-new-1",
            "/admin/content/q-new-1/v/1/preview",
            "/admin/ratings",
        ]
        posts = [
            ("/admin/content/new", question_form(slug="q-sneaky")),
            ("/admin/content/q-new-1/edit", question_form()),
            ("/admin/content/q-new-1/v/1/review", {"reviewer_name": "X Y", "note": "sneaky note"}),
            ("/admin/content/q-new-1/v/1/publish", {}),
            ("/admin/content/q-new-1/retire", {}),
            ("/admin/content/q-new-1/v/1/preview", {"option": "A"}),
            ("/admin/topics/new", {"strand": "english", "slug": "sneaky", "title": "S"}),
            ("/admin/ratings/1/resolve", {}),
        ]
        for who, expected in others.items():
            c = Client().login(who) if who else Client()
            for path in paths:
                with self.subTest(who=who, path=path):
                    self.assertEqual(c.get(path, follow_redirects=False).status_code, expected)
            for path, data in posts:
                with self.subTest(who=who, post=path):
                    self.assertEqual(c.submit(path, data).status_code, expected)
        self.assertEqual(versions("q-new-1"), [(1, "draft")])
        with db.session_scope() as s:
            self.assertIsNone(s.scalar(select(ContentItem).where(ContentItem.slug == "q-sneaky")))
            self.assertIsNone(s.scalar(select(Topic).where(Topic.slug == "sneaky")))
        for path in paths:
            self.assertEqual(self.a.get(path).status_code, 200, path)

    def test_create_validates(self):
        for bad in (
            {"slug": "Bad Slug!"},
            {"option_C": ""},
            {"correct_option_id": "D"},
            {"hint_1": "", "hint_2": "", "hint_3": ""},
            {"explanation": ""},
            {"option_B": "like"},
        ):
            with self.subTest(bad=bad):
                r = self.a.submit("/admin/content/new", question_form(**bad))
                self.assertEqual(r.status_code, 400)
                self.assertIn('role="alert"', r.text)
        self.create()
        self.assertEqual(
            self.a.submit("/admin/content/new", question_form()).status_code, 400
        )  # duplicate slug

    def test_draft_review_publish_and_student_visibility(self):
        self.create()
        settings.allow_draft_practice = False
        st = Client().login("student1")

        def offered():
            with db.session_scope() as s:
                t = s.scalar(select(Topic).where(Topic.slug == TOPIC))
                return [v.item.slug for v in content.topic_versions(s, t, "question")]

        self.assertNotIn("q-new-1", offered())
        self.assertEqual(self.publish("q-new-1", 1).status_code, 400)  # review required first
        self.assertEqual(self.review("q-new-1", 1, reviewer_name="").status_code, 400)
        self.assertEqual(self.review("q-new-1", 1, note="").status_code, 400)
        self.assertEqual(self.review("q-new-1", 1, review_date="2999-01-01").status_code, 400)
        self.assertEqual(self.review("q-new-1", 1, review_date="not-a-date").status_code, 400)
        self.assertEqual(self.review("q-new-1", 1).status_code, 303)
        self.assertNotIn("q-new-1", offered())  # reviewed is not yet published
        self.assertEqual(self.review("q-new-1", 1).status_code, 400)  # only drafts are reviewed
        self.assertEqual(self.publish("q-new-1", 1).status_code, 303)
        self.assertIn("q-new-1", offered())
        with db.session_scope() as s:
            v = s.scalar(
                select(ContentVersion).join(ContentItem).where(ContentItem.slug == "q-new-1")
            )
            self.assertEqual(
                (v.status, v.reviewer_name, v.review_note),
                ("published", "Ms Teacher", "Checked accuracy and wording."),
            )
            self.assertIsNotNone(v.reviewed_at)
            actions = s.scalars(select(AuditLog.action)).all()
        for a in ("content_created", "content_reviewed", "content_published"):
            self.assertIn(a, actions)
        page = self.a.get("/admin/content/q-new-1").text
        self.assertIn("Ms Teacher", page)
        self.assertIn(st.get("/practice").status_code, (200,))

    def test_draft_practice_setting_shows_banner(self):
        self.create()
        settings.allow_draft_practice = True
        with db.session_scope() as s:
            t = s.scalar(select(Topic).where(Topic.slug == TOPIC))
            self.assertIn(
                "q-new-1", [v.item.slug for v in content.topic_versions(s, t, "question")]
            )
        st = Client().login("student1")
        r = st.submit(f"/practice/topic/{TOPIC}/start", {"confidence": ""})
        self.assertEqual(r.status_code, 303, r.text[:300])
        page = st.get(r.headers["location"]).text
        self.assertIn("Draft, not teacher-reviewed", page)

    def test_edit_creates_new_immutable_version(self):
        self.create()
        self.review("q-new-1", 1)
        self.publish("q-new-1", 1)
        r = self.a.submit(
            "/admin/content/q-new-1/edit",
            question_form(prompt="Which word usually signals a simile?"),
        )
        self.assertEqual(r.status_code, 303)
        self.assertEqual(versions("q-new-1"), [(1, "published"), (2, "draft")])
        r = self.a.submit(
            "/admin/content/q-new-1/edit",
            question_form(prompt="Which word usually signals a simile?"),
        )
        self.assertIn("unchanged=1", r.headers["location"])  # no-op edit makes no version
        self.assertEqual(
            self.a.submit("/admin/content/q-new-1/edit", question_form(option_A="")).status_code,
            400,
        )
        self.assertEqual(len(versions("q-new-1")), 2)
        with db.session_scope() as s:
            v1 = s.scalar(
                select(ContentVersion)
                .join(ContentItem)
                .where(ContentItem.slug == "q-new-1", ContentVersion.version == 1)
            )
            self.assertEqual(v1.data["prompt"], "Which word is a simile marker?")
        # students keep getting v1 until v2 is reviewed and published; then v1 retires
        settings.allow_draft_practice = False
        with db.session_scope() as s:
            item = s.scalar(select(ContentItem).where(ContentItem.slug == "q-new-1"))
            self.assertEqual(content.current_version(item).version, 1)
        self.review("q-new-1", 2)
        self.publish("q-new-1", 2)
        self.assertEqual(versions("q-new-1"), [(1, "retired"), (2, "published")])

    def test_lesson_authoring(self):
        r = self.a.submit(
            "/admin/content/new",
            {
                "kind": "lesson",
                "topic": TOPIC,
                "slug": "lesson-new",
                "title": "Similes",
                "body": "A simile compares using like or as.",
            },
        )
        self.assertEqual(r.status_code, 303)
        self.assertIn("A simile compares", self.a.get("/admin/content/lesson-new/v/1/preview").text)
        r = self.a.submit(
            "/admin/content/lesson-new/edit", {"title": "Similes", "body": "Changed."}
        )
        self.assertEqual(versions("lesson-new"), [(1, "draft"), (2, "draft")])

    def test_preview_as_student_records_nothing(self):
        self.create()
        page = self.a.get("/admin/content/q-new-1/v/1/preview").text
        self.assertIn("Draft, not teacher-reviewed", page)
        self.assertNotIn(
            "Look for a comparing word", page.split("<details>")[0]
        )  # hints folded away
        self.assertNotIn("introduces a comparison", page)  # no explanation before answering
        r = self.a.submit("/admin/content/q-new-1/v/1/preview", {"option": "B"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("Not this time", r.text)
        self.assertIn("introduces a comparison", html.unescape(r.text))
        self.assertEqual(
            self.a.submit("/admin/content/q-new-1/v/1/preview", {"option": "Z"}).status_code, 400
        )
        with db.session_scope() as s:
            self.assertEqual(s.scalars(select(PracticeItem)).all(), [])

    def test_retire_hides_from_new_practice_but_old_attempts_render(self):
        self.create()
        settings.allow_draft_practice = True
        st = Client().login("student1")
        r = st.submit(f"/practice/topic/{TOPIC}/start", {"confidence": ""})
        set_id = int(re.search(r"/practice/set/(\d+)/", r.headers["location"]).group(1))
        with db.session_scope() as s:
            items = s.scalars(
                select(PracticeItem)
                .where(PracticeItem.set_id == set_id)
                .order_by(PracticeItem.ordinal)
            ).all()
            n = next(i.ordinal for i in items if i.question.item.slug == "q-new-1")
        self.assertEqual(
            st.submit(f"/practice/set/{set_id}/q/{n}", {"option": "A"}).status_code, 200
        )
        self.assertEqual(self.a.submit("/admin/content/q-new-1/retire").status_code, 303)
        self.assertEqual(versions("q-new-1"), [(1, "retired")])
        with db.session_scope() as s:
            t = s.scalar(select(Topic).where(Topic.slug == TOPIC))
            self.assertNotIn(
                "q-new-1", [v.item.slug for v in content.topic_versions(s, t, "question", True)]
            )
        old = st.get(f"/practice/set/{set_id}/q/{n}")
        self.assertEqual(old.status_code, 200)
        self.assertIn("Which word is a simile marker?", old.text)
        self.assertEqual(self.a.get("/admin/content/q-new-1?v=1").status_code, 200)

    def test_authored_content_is_escaped_everywhere(self):
        self.create(
            prompt="P " + XSS, option_A="A " + XSS, explanation="E " + XSS, hint_1="H " + XSS
        )
        r = self.a.submit(
            "/admin/content/new",
            {
                "kind": "lesson",
                "topic": TOPIC,
                "slug": "lesson-xss",
                "title": "T " + XSS[:100],
                "body": "B " + XSS,
            },
        )
        self.assertEqual(r.status_code, 303)
        self.review("q-new-1", 1)
        self.publish("q-new-1", 1)
        st = Client().login("student1")
        loc = st.submit(f"/practice/topic/{TOPIC}/start", {"confidence": ""}).headers["location"]
        set_id = int(re.search(r"/practice/set/(\d+)/", loc).group(1))
        pages = [
            self.a.get(p).text
            for p in (
                "/admin/content",
                "/admin/content/q-new-1",
                "/admin/content/q-new-1/v/1/preview",
                "/admin/content/lesson-xss",
                "/admin/content/lesson-xss/v/1/preview",
            )
        ]
        pages.append(self.a.submit("/admin/content/q-new-1/v/1/preview", {"option": "A"}).text)
        for n in range(1, 8):
            q = st.get(f"/practice/set/{set_id}/q/{n}")
            if q.status_code != 200:
                break
            pages.append(q.text)
            st.submit(f"/practice/set/{set_id}/q/{n}/hint")
            pages.append(st.get(f"/practice/set/{set_id}/q/{n}").text)
            pages.append(st.submit(f"/practice/set/{set_id}/q/{n}", {"option": "A"}).text)
        joined = "\n".join(pages)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", joined)
        for page in pages:
            self.assertNotIn("<script", page.lower())
            self.assertNotIn("<img src=x", page.lower())


class RatingsQueueTests(Workflow):
    def rate(self, slug, rating, reason=None, n=1):
        with db.session_scope() as s:
            v = s.scalar(
                select(ContentVersion)
                .join(ContentItem)
                .where(ContentItem.slug == slug)
                .order_by(ContentVersion.version.desc())
            )
            for _ in range(n):
                content.record_rating(s, v, rating, reason)
            return v.id

    def test_sorted_by_downs_then_reason_and_resolved_by_version(self):
        with db.session_scope() as s:
            slugs = s.scalars(
                select(ContentItem.slug)
                .where(ContentItem.kind == "question")
                .order_by(ContentItem.slug)
            ).all()[:4]
        a, b, c, d = slugs
        self.rate(a, "down", "unclear", 2)
        self.rate(b, "down", "wrong", 2)
        self.rate(c, "down", "too_easy", 3)
        self.rate(d, "up", "helpful")
        page = self.a.get("/admin/ratings").text
        order = [m for m in re.findall(r'href="/admin/content/([^"?]+)\?v=', page)]
        self.assertEqual(order[:4], [c, b, a, d])  # most 👎 first; ties: 'wrong' before 'unclear'
        # fix b by publishing a new version, then resolve its ratings by that version
        with db.session_scope() as s:
            item = s.scalar(select(ContentItem).where(ContentItem.slug == b))
            data = item.versions[-1].data
            vid = item.versions[-1].id
        form = {
            "prompt": data["prompt"] + " (fixed)",
            "explanation": data["explanation"],
            "correct_option_id": data["correct_option_id"],
            "help_lesson_id": data.get("help_lesson_id") or "",
        }
        form.update({f"option_{o['id']}": o["text"] for o in data["options"]})
        form.update({f"hint_{i}": h for i, h in enumerate(data["hints"], 1)})
        self.assertEqual(self.a.submit(f"/admin/content/{b}/edit", form).status_code, 303)
        newest = versions(b)[-1][0]
        self.assertEqual(
            self.a.submit(f"/admin/ratings/{vid}/resolve", {"resolved_version": "1"}).status_code,
            400,
        )
        self.assertEqual(
            self.a.submit(
                f"/admin/ratings/{vid}/resolve", {"resolved_version": str(newest)}
            ).status_code,
            303,
        )
        open_page = self.a.get("/admin/ratings").text
        self.assertNotIn(f"/admin/content/{b}?v=", open_page)
        all_page = self.a.get("/admin/ratings?show=all").text
        self.assertIn(f"Resolved by version {newest}", all_page)
        with db.session_scope() as s:
            rows = s.scalars(select(ContentRating).where(ContentRating.version_id == vid)).all()
            self.assertTrue(all(r.resolved_at and r.resolved_version == newest for r in rows))
        # resolving without a fix
        other = self.rate(c, "down", "too_easy", 0)
        self.assertEqual(self.a.submit(f"/admin/ratings/{other}/resolve", {}).status_code, 303)
        self.assertIn("no change needed", self.a.get("/admin/ratings?show=all").text)


class WellbeingTests(unittest.TestCase):
    def test_public_wellbeing_page_links_official_supports(self):
        testutil.fresh_db()
        r = Client().get("/wellbeing")
        self.assertEqual(r.status_code, 200)
        for needle in (
            "https://www.gov.ie/en/department-of-education/publications/"
            "wellbeing-support-for-exam-students-parents-and-school-staff/",
            "https://jigsaw.ie/",
            "https://spunout.ie/",
            "50808",
            "1800 666 666",
            "116 123",
            "guidance counsellor",
        ):
            self.assertIn(needle, r.text)
        self.assertNotIn("<script", r.text.lower())


if __name__ == "__main__":
    unittest.main()
