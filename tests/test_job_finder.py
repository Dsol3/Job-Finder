"""Offline tests — no network, no credentials. Run: python3 -m unittest discover -s tests"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from job_finder import cli, reddit  # noqa: E402
from job_finder.config import load_config  # noqa: E402
from job_finder.filters import match, parse_budgets, process, score  # noqa: E402
from job_finder.store import Store  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "forhire_new.json"
FLOORS = {"per_word": 0.05, "per_hour": 15.0, "per_article": 50.0, "per_video": 50.0}


def cfg_dict() -> dict:
    cfg = load_config(ROOT / "config.example.toml")
    cfg["reddit"]["max_age_hours"] = 36
    return cfg


def fixture_posts():
    return reddit.load_fixture(str(FIXTURE))


class TestBudgets(unittest.TestCase):
    def test_per_word(self):
        b = parse_budgets("Rate is $0.12/word, paid on delivery", FLOORS)
        self.assertEqual((b[0].amount, b[0].unit), (0.12, "word"))
        self.assertFalse(b[0].lowball)

    def test_cents_per_word(self):
        b = parse_budgets("we pay 15 cents per word", FLOORS)
        self.assertEqual((b[0].amount, b[0].unit), (0.15, "word"))

    def test_per_hour_and_month(self):
        self.assertEqual(parse_budgets("$15/hour", FLOORS)[0].unit, "hour")
        self.assertEqual(parse_budgets("$1,200/month retainer", FLOORS)[0].amount, 1200.0)

    def test_per_video(self):
        b = parse_budgets("$150 per video, 2 per week", FLOORS)
        self.assertEqual((b[0].amount, b[0].unit), (150.0, "video"))
        self.assertFalse(b[0].lowball)

    def test_bulk_price_flagged_lowball(self):
        b = parse_budgets("Need 20 blog posts, 5,000 words for $25 total", FLOORS)
        self.assertTrue(any(x.unit == "word" and x.lowball for x in b))

    def test_no_rate(self):
        self.assertEqual(parse_budgets("Looking for a strategist, DM me", FLOORS), [])


class TestMatching(unittest.TestCase):
    def setUp(self):
        self.cfg = cfg_dict()
        self.posts = {p.id: p for p in fixture_posts()}

    def test_youtube_strategist_kept(self):
        ok, reasons = match(self.posts["fx_ytstrat"], self.cfg)
        self.assertTrue(ok, reasons)
        self.assertIn("$1,200/month", self.posts["fx_ytstrat"].budget_text)

    def test_writing_gig_kept(self):
        ok, _ = match(self.posts["fx_saas_write"], self.cfg)
        self.assertTrue(ok)

    def test_for_hire_dropped(self):
        self.assertFalse(match(self.posts["fx_forhire"], self.cfg)[0])

    def test_lowball_dropped(self):
        ok, reasons = match(self.posts["fx_lowball"], self.cfg)
        self.assertFalse(ok)
        self.assertTrue(any("floor" in r for r in reasons), reasons)

    def test_revenue_share_dropped(self):
        self.assertFalse(match(self.posts["fx_revshare"], self.cfg)[0])

    def test_unpaid_dropped(self):
        self.assertFalse(match(self.posts["fx_unpaid"], self.cfg)[0])

    def test_unrelated_dropped(self):
        self.assertFalse(match(self.posts["fx_dev"], self.cfg)[0])

    def test_strategy_ranks_first(self):
        ranked = process(fixture_posts(), self.cfg)
        self.assertEqual(ranked[0].id, "fx_ytstrat")
        self.assertGreater(ranked[0].notify_score, ranked[-1].notify_score)

    def test_old_post_dropped(self):
        ranked = process(fixture_posts(), self.cfg)
        self.assertNotIn("fx_old", [p.id for p in ranked])  # 40h > 36h window

    def test_editor_post_scores_below_strategy(self):
        ranked = {p.id: p.notify_score for p in process(fixture_posts(), self.cfg)}
        self.assertLess(ranked["fx_editor"], ranked["fx_ytstrat"])

    def test_score_capped(self):
        for post in fixture_posts():
            self.assertLessEqual(score(post, self.cfg), 10)


class TestStore(unittest.TestCase):
    def test_dedupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "seen.sqlite3")
            self.assertTrue(store.is_new("abc"))
            store.mark("abc", "forhire", "title", 5)
            self.assertFalse(store.is_new("abc"))
            self.assertEqual(store.count(), 1)
            store.close()


RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>[Hiring] Content strategist for a YouTube channel</title>
    <link href="https://www.reddit.com/r/forhire/comments/abc123/hiring_content_strategist/"/>
    <id>t3_abc123</id>
    <published>2026-10-27T09:00:00+00:00</published>
    <author><name>/u/someone</name></author>
    <category term="Hiring"/>
    <content type="html">&lt;!-- SC_OFF --&gt;&lt;div&gt;Paying $0.20/word&lt;/div&gt;&lt;!-- SC_ON --&gt;</content>
  </entry>
</feed>
"""


class TestRss(unittest.TestCase):
    def test_parse_rss(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feed.rss"
            path.write_text(RSS_SAMPLE)
            posts = reddit.load_fixture(str(path), rebase=False)
        self.assertEqual(len(posts), 1)
        post = posts[0]
        self.assertEqual(post.id, "abc123")
        self.assertEqual(post.flair, "Hiring")
        self.assertEqual(post.author, "someone")
        self.assertIn("Paying $0.20/word", post.body)
        self.assertTrue(post.link.startswith("https://www.reddit.com/r/forhire/"))


class TestCli(unittest.TestCase):
    def _config_file(self, tmp: Path, bootstrap: bool) -> Path:
        path = tmp / "config.toml"
        path.write_text(
            f"""
[reddit]
max_age_hours = 36

[notify]
channel = "console"

[storage]
db_path = "{tmp / 'seen.sqlite3'}"
bootstrap = {str(bootstrap).lower()}
"""
        )
        return path

    def test_dry_run_sends_but_does_not_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cfg_path = self._config_file(tmp_path, bootstrap=False)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(
                    ["--config", str(cfg_path), "--fixture", str(FIXTURE), "--dry-run"]
                )
            out = buf.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("YouTube Channel Strategist", out)
            self.assertIn("[10/10]", out)  # score rendered
            self.assertLess(
                out.index("YouTube Channel Strategist"), out.index("Video Editor")
            )  # strategy outranks editor work
            store = Store(tmp_path / "seen.sqlite3")
            self.assertEqual(store.count(), 0)  # dry run persists nothing
            store.close()

    def test_second_run_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cfg_path = self._config_file(tmp_path, bootstrap=False)
            first = io.StringIO()
            with redirect_stdout(first):
                cli.main(["--config", str(cfg_path), "--fixture", str(FIXTURE)])
            second = io.StringIO()
            with redirect_stdout(second):
                cli.main(["--config", str(cfg_path), "--fixture", str(FIXTURE)])
            self.assertIn("YouTube Channel Strategist", first.getvalue())
            self.assertIn("nothing new", second.getvalue())

    def test_bootstrap_swallows_first_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cfg_path = self._config_file(tmp_path, bootstrap=True)
            store = Store(tmp_path / "seen.sqlite3")
            posts = fixture_posts()
            store.mark_many(posts)
            store.close()
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main(["--config", str(cfg_path), "--fixture", str(FIXTURE)])
            self.assertIn("nothing new", buf.getvalue())


class TestConfig(unittest.TestCase):
    def test_env_overrides_token(self):
        os.environ["TELEGRAM_BOT_TOKEN"] = "123:abc"
        try:
            cfg = load_config(ROOT / "config.example.toml")
            self.assertEqual(cfg["notify"]["telegram_token"], "123:abc")
        finally:
            del os.environ["TELEGRAM_BOT_TOKEN"]

    def test_subreddit_prefix_stripped(self):
        cfg = load_config(ROOT / "config.example.toml")
        self.assertTrue(all(not s.startswith("r/") for s in cfg["reddit"]["subreddits"]))
        self.assertIn("HireaWriter", cfg["reddit"]["subreddits"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestNetworkLayer(unittest.TestCase):
    """Exercises the real HTTP + parser path against a local server, no Reddit."""

    @classmethod
    def setUpClass(cls):
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        payload = FIXTURE.read_bytes()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                if "json" in self.path:
                    self.send_response(403)  # simulate the JSON endpoint being blocked
                    self.end_headers()
                    self.wfile.write(b"blocked")
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/atom+xml")
                    self.end_headers()
                    self.wfile.write(RSS_SAMPLE.encode())

            def log_message(self, *args):
                pass

        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_falls_back_to_rss_when_json_blocked(self):
        original = reddit.ENDPOINTS
        reddit.ENDPOINTS = (
            f"http://127.0.0.1:{self.port}/r/test/new.json?limit=100",
            f"http://127.0.0.1:{self.port}/r/test/new.rss?limit=100",
        )
        try:
            posts = reddit.fetch_subreddit("test", 100, "unittest")
        finally:
            reddit.ENDPOINTS = original
        self.assertEqual(len(posts), 1)
        self.assertIn("content strategist", posts[0].title.lower())

    def test_all_endpoints_failing_returns_empty(self):
        original = reddit.ENDPOINTS
        reddit.ENDPOINTS = ("http://127.0.0.1:1/nothing.json",)
        try:
            self.assertEqual(reddit.fetch_subreddit("test", 100, "unittest"), [])
        finally:
            reddit.ENDPOINTS = original
