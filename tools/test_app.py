"""General HTTP tests: public pages, headers, error pages. Run with the project venv:
.venv/bin/python -m unittest discover -s tools -p 'test_*.py' -v
"""

import unittest

try:
    import testutil
    from testutil import Client
except ImportError as exc:  # system python without the venv
    raise unittest.SkipTest(f"dependencies unavailable: {exc}")


class PublicPageTests(unittest.TestCase):
    def setUp(self):
        testutil.fresh_db()
        self.client = Client()

    def test_public_pages_render(self):
        for path in ["/", "/login", "/health"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_security_headers(self):
        h = self.client.get("/").headers
        csp = h["Content-Security-Policy"]
        self.assertIn("script-src 'self'", csp)
        self.assertNotIn("unsafe-inline", csp)
        self.assertEqual(h["X-Frame-Options"], "DENY")
        self.assertEqual(h["X-Content-Type-Options"], "nosniff")
        self.assertEqual(h["Cache-Control"], "no-store")

    def test_no_inline_scripts_anywhere(self):
        import re

        for path in ["/", "/login"]:
            text = self.client.get(path).text.lower()
            self.assertIsNone(
                re.search(r"<script(?![^>]*\ssrc=)", text)
            )  # every script tag is external

    def test_unknown_routes_404(self):
        for path in ["/nope", "/practice/maths", "/static/app/missing.css"]:
            with self.subTest(path=path):
                self.assertIn(self.client.get(path, follow_redirects=False).status_code, (303, 404))
        self.assertEqual(self.client.get("/nope").status_code, 404)

    def test_csrf_cookie_flags(self):
        cookie = [
            c
            for c in self.client.get("/").headers.get_list("set-cookie")
            if c.startswith("scoilmate_csrf=")
        ][0]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=lax", cookie)


if __name__ == "__main__":
    unittest.main()
