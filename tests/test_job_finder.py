"""Offline tests — no network, no credentials. Run: python3 -m unittest discover -s tests"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from job_finder import cli, reddit, telegram  # noqa: E402
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


GOOD_TOKEN = "8123456789:" + "AAH" + "x" * 32


class TestTelegram(unittest.TestCase):
    """Drives the real wizard code against a fake Bot API."""

    @classmethod
    def setUpClass(cls):
        import json as _json
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        cls.calls: list[str] = []
        cls.update_polls = 0

        class Handler(BaseHTTPRequestHandler):
            def _send(self, payload):
                body = _json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):  # noqa: N802
                self.do_POST()

            def do_POST(self):  # noqa: N802
                method = self.path.rsplit("/", 1)[-1].split("?")[0]
                cls.calls.append(method)
                if method == "getMe":
                    if "bad" in self.path:
                        self._send({"ok": False, "description": "Unauthorized"})
                    else:
                        self._send({"ok": True, "result": {"id": 1, "username": "test_jobwatch_bot"}})
                elif method == "getUpdates":
                    cls.update_polls += 1
                    if cls.update_polls < 2:
                        self._send({"ok": True, "result": []})
                    else:
                        self._send({"ok": True, "result": [{"update_id": 7, "message": {
                            "chat": {"id": 123456789, "type": "private",
                                     "first_name": "Ada", "username": "ada"}}}]})
                elif method == "getChat":
                    self._send({"ok": True, "result": {"id": 123456789, "first_name": "Ada"}})
                elif method == "sendMessage":
                    self._send({"ok": True, "result": {"message_id": 1}})
                else:
                    self._send({"ok": False, "description": "unknown method"})

            def log_message(self, *args):
                pass

        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.original_api = telegram.TG_API
        telegram.TG_API = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        telegram.TG_API = cls.original_api
        cls.server.shutdown()

    def test_token_validation(self):
        self.assertTrue(telegram.validate_token(GOOD_TOKEN)[0])
        for bad in ("", "abc", "12345:short"):
            self.assertFalse(telegram.validate_token(bad)[0])

    def test_discovers_chat_then_writes_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            out = []
            code = telegram.run_wizard(
                env_path=env,
                preset_token=GOOD_TOKEN,
                ask=lambda *a, **k: "",
                out=out.append,
                wait_timeout=10,
            )
            self.assertEqual(code, 0, "\n".join(out))
            text = env.read_text()
            self.assertIn(f"TELEGRAM_BOT_TOKEN={GOOD_TOKEN}", text)
            self.assertIn("TELEGRAM_CHAT_ID=123456789", text)
            self.assertEqual(oct(env.stat().st_mode)[-3:], "600")
            self.assertIn("Found chat: Ada", "\n".join(out))
            self.assertIn("sendMessage", self.calls)

    def test_env_is_merged_not_clobbered(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text("# keep me\nOTHER_KEY=keep\nTELEGRAM_CHAT_ID=old\n")
            telegram.write_env(env, {"TELEGRAM_CHAT_ID": "999"})
            parsed = telegram.parse_env(env)
            self.assertEqual(parsed["OTHER_KEY"], "keep")
            self.assertEqual(parsed["TELEGRAM_CHAT_ID"], "999")
            self.assertIn("keep me", env.read_text())

    def test_bad_token_exits_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = []
            code = telegram.run_wizard(
                env_path=Path(tmp) / ".env",
                preset_token="12345:short",
                out=out.append,
            )
            self.assertEqual(code, 2)
            self.assertFalse((Path(tmp) / ".env").exists())

    def test_auto_mode_picks_telegram_when_creds_exist(self):
        from job_finder.notify import Notifier

        cfg = cfg_dict()
        cfg["notify"].update(channel="auto", telegram_token=GOOD_TOKEN, telegram_chat_id="1")
        self.assertEqual(Notifier(cfg).mode, "telegram")
        cfg["notify"].update(telegram_token="", telegram_chat_id="")
        self.assertEqual(Notifier(cfg).mode, "console")
        cfg["notify"].update(channel="console", telegram_token=GOOD_TOKEN, telegram_chat_id="1")
        self.assertEqual(Notifier(cfg).mode, "console")

    def test_doctor_reports_missing_creds(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = cfg_dict()
            cfg["notify"].update(channel="auto", telegram_token="", telegram_chat_id="")
            original = reddit.fetch_subreddit
            reddit.fetch_subreddit = lambda *a, **k: []
            out = []
            try:
                code = telegram.run_doctor(cfg, None, out=out.append)
            finally:
                reddit.fetch_subreddit = original
            self.assertEqual(code, 1)
            joined = "\n".join(out)
            self.assertIn("--setup-telegram", joined)
            self.assertIn("reddit unreachable", joined)


class TestDemo(unittest.TestCase):
    def test_demo_sends_sample_without_storing(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = Path(tmp) / "config.toml"
            cfg_path.write_text(f"""
[notify]
channel = "console"

[storage]
db_path = "{Path(tmp) / 'seen.sqlite3'}"
bootstrap = false
""")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(["--config", str(cfg_path), "--demo"])
            out = buf.getvalue()
            self.assertEqual(code, 0, out)
            self.assertIn("SAMPLE", out)
            store = Store(Path(tmp) / "seen.sqlite3")
            self.assertEqual(store.count(), 0)  # demo must not pollute dedupe
            store.close()


class TestDeploy(unittest.TestCase):
    def test_ci_config_is_valid_and_isolated(self):
        import tomllib

        with open(ROOT / "config.ci.toml", "rb") as fh:
            data = tomllib.load(fh)
        self.assertTrue(data["storage"]["db_path"].startswith("state/"))
        self.assertFalse(data["storage"]["bootstrap"])  # cache miss must not swallow posts
        self.assertLessEqual(data["reddit"]["max_age_hours"], 6)
        self.assertIn("youtube strateg", data["matching"]["priority"])

    def test_missing_toml_parser_gives_actionable_error(self):
        from job_finder import config as cfg_mod

        original = cfg_mod.tomllib
        cfg_mod.tomllib = None
        try:
            with self.assertRaises(cfg_mod.ConfigError) as ctx:
                cfg_mod.load_config(ROOT / "config.example.toml")
        finally:
            cfg_mod.tomllib = original
        self.assertIn("pip install --user tomli", str(ctx.exception))

    def test_install_script_is_syntactically_valid(self):
        import shutil
        import subprocess

        script = ROOT / "deploy" / "install.sh"
        self.assertTrue(script.is_file())
        text = script.read_text()
        self.assertIn("systemctl enable --now", text)
        self.assertIn("chmod 600", text)  # secrets file must not be world-readable
        self.assertNotIn("REPLACE_ME", text)  # no half-finished placeholders
        if shutil.which("bash"):
            proc = subprocess.run(["bash", "-n", str(script)], capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode())

    def test_dockerfile_and_compose_present(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        self.assertIn("/app/state/seen.sqlite3", dockerfile)
        self.assertIn("PYTHONUNBUFFERED", dockerfile)
        compose = (ROOT / "docker-compose.yml").read_text()
        self.assertIn("jobfinder-data", compose)


class TestWorkflow(unittest.TestCase):
    """No YAML parser in the stdlib, so assert on the things that matter."""

    def setUp(self):
        self.text = (ROOT / ".github" / "workflows" / "watch.yml").read_text()

    def test_schedule_is_frequent_enough(self):
        self.assertIn('cron: "*/5 * * * *"', self.text)
        self.assertIn("workflow_dispatch", self.text)  # manual test run

    def test_uses_both_secrets(self):
        self.assertIn("secrets.TELEGRAM_BOT_TOKEN", self.text)
        self.assertIn("secrets.TELEGRAM_CHAT_ID", self.text)

    def test_state_is_cached_not_committed(self):
        self.assertIn("actions/cache/restore", self.text)
        self.assertIn("actions/cache/save", self.text)
        self.assertNotIn("git add state", self.text)  # never commit the dedupe db

    def test_keepalive_actually_commits(self):
        self.assertIn(".keepalive", self.text)
        self.assertIn("git push", self.text)
        self.assertIn("contents: write", self.text)

    def test_fails_loudly_on_missing_secrets(self):
        self.assertIn("::error::Missing repository secrets", self.text)


class TestBatching(unittest.TestCase):
    """The throttle fix: many boards, one request."""

    def test_single_request_for_a_normal_watchlist(self):
        group = ["HireaWriter", "forhire", "CreatorServices"]
        urls = reddit.batch_urls(group, 100)
        self.assertIn("/r/HireaWriter+forhire+CreatorServices/new.json", urls[0])
        self.assertIn("limit=100", urls[0])
        self.assertTrue(urls[2].split("?")[0].endswith(".rss"))

    def test_watchlist_split_into_batches(self):
        boards = [f"sub{i}" for i in range(9)]
        batches = [boards[i:i + reddit.MULTI_BATCH] for i in range(0, len(boards), reddit.MULTI_BATCH)]
        self.assertEqual([len(b) for b in batches], [8, 1])

    def test_fetch_all_uses_one_request_for_three_boards(self):
        import json as _json
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        hits: list[str] = []
        boards = ["HireaWriter", "forhire", "CreatorServices"]
        children = []
        for index, board in enumerate(boards):
            children.append({"kind": "t3", "data": {
                "id": f"p{index}", "subreddit": board, "title": "[Hiring] content writer",
                "selftext": "paid", "author": "x", "url": "u", "permalink": "/p",
                "created_utc": 1, "link_flair_text": "Hiring", "score": 1, "num_comments": 0,
            }})
        posts = {"kind": "Listing", "data": {"children": children}}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                hits.append(self.path)
                body = _json.dumps(posts).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        original = reddit.ENDPOINTS
        reddit.ENDPOINTS = (f"http://127.0.0.1:{server.server_address[1]}/r/{{sub}}/new.json?limit={{limit}}",)
        try:
            result = reddit.fetch_all(["HireaWriter", "forhire", "CreatorServices"], 100, "unittest")
        finally:
            reddit.ENDPOINTS = original
            server.shutdown()

        self.assertEqual(len(hits), 1)                      # one request, not three
        self.assertIn("HireaWriter+forhire+CreatorServices", hits[0])
        self.assertEqual(len(result.posts), 3)
        self.assertEqual(result.boards_ok, 3)
        self.assertTrue(result.complete)
        self.assertEqual(result.requests, 1)

    def test_backs_off_then_falls_back_to_the_next_endpoint(self):
        import json as _json
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        calls: list[str] = []
        payload = _json.dumps({"kind": "Listing", "data": {"children": [
            {"kind": "t3", "data": {"id": "p1", "subreddit": "forhire", "title": "t",
                                    "selftext": "b", "author": "a", "url": "u", "permalink": "/p",
                                    "created_utc": 1, "link_flair_text": "", "score": 0, "num_comments": 0}},
        ]}}).encode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                calls.append(self.path)
                if "/r/" in self.path and "old" not in self.path:
                    self.send_response(429)          # throttled
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_address[1]
        original_endpoints, original_sleep, original_base = reddit.ENDPOINTS, time.sleep, reddit.BACKOFF_BASE
        slept: list[float] = []
        reddit.ENDPOINTS = (
            f"http://127.0.0.1:{port}/r/{{sub}}/new.json?limit={{limit}}",
            f"http://127.0.0.1:{port}/old/r/{{sub}}/new.json?limit={{limit}}",
        )
        reddit.BACKOFF_BASE = 1.0
        reddit.time.sleep = lambda s: slept.append(s)   # don't actually wait
        try:
            result = reddit.fetch_all(["forhire"], 100, "unittest", delay=0)
        finally:
            reddit.ENDPOINTS, reddit.time.sleep, reddit.BACKOFF_BASE = (
                original_endpoints, original_sleep, original_base)
            server.shutdown()

        self.assertEqual(len(calls), 2, calls)              # throttled once, then recovered
        self.assertTrue(slept and 1.0 <= slept[0] <= 1.31, slept)  # backoff with jitter
        self.assertEqual(len(result.posts), 1)

    def test_reports_boards_that_returned_nothing(self):
        import json as _json
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        payload = _json.dumps({"kind": "Listing", "data": {"children": [
            {"kind": "t3", "data": {"id": "p1", "subreddit": "HireaWriter", "title": "t",
                                    "selftext": "b", "author": "a", "url": "u", "permalink": "/p",
                                    "created_utc": 1, "link_flair_text": "", "score": 0, "num_comments": 0}},
        ]}}).encode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        original = reddit.ENDPOINTS
        reddit.ENDPOINTS = (f"http://127.0.0.1:{server.server_address[1]}/r/{{sub}}/new.json?limit={{limit}}",)
        try:
            result = reddit.fetch_all(["HireaWriter", "forhire"], 100, "unittest")
        finally:
            reddit.ENDPOINTS = original
            server.shutdown()

        self.assertEqual(result.failures, ["forhire"])
        self.assertFalse(result.complete)
        self.assertIn("silent: forhire", result.summary())


class TestHealth(unittest.TestCase):
    def test_health_tracks_last_success_and_staleness(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = cfg_dict()
            cfg["storage"]["db_path"] = str(Path(tmp) / "seen.sqlite3")
            result = reddit.FetchResult(attempted=["HireaWriter", "forhire"], counts={"hireawriter": 3})
            reddit.write_health(cfg, result)

            self.assertEqual(reddit.stale_boards(cfg, hours=1), [("forhire", 999.0)])
            reddit.write_health(cfg, reddit.FetchResult(attempted=["HireaWriter"], counts={"hireawriter": 1}))
            self.assertEqual(reddit.stale_boards(cfg, hours=1), [("forhire", 999.0)])


class TestConfigErrors(unittest.TestCase):
    def test_missing_explicit_config_is_fatal(self):
        from job_finder.config import ConfigError

        with self.assertRaises(ConfigError) as ctx:
            load_config("definitely-not-here.toml")
        self.assertIn("config file not found", str(ctx.exception))

    def test_duplicate_section_explains_itself(self):
        from job_finder.config import ConfigError

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text("[reddit]\nlimit = 5\n\n[storage]\nbootstrap = true\n\n[reddit]\nlimit = 6\n")
            with self.assertRaises(ConfigError) as ctx:
                load_config(path)
            message = str(ctx.exception)
            self.assertIn("not valid TOML", message)
            self.assertIn("line 7", message)
            self.assertIn("appears more than once", message)
            self.assertIn("config.example.toml", message)

    def test_broken_quote_is_explained(self):
        from job_finder.config import ConfigError

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text('[reddit]\nsubreddits = ["a", "b]\n')
            with self.assertRaises(ConfigError) as ctx:
                load_config(path)
            self.assertIn("not valid TOML", str(ctx.exception))

    def test_cli_exits_2_with_message_not_traceback(self):
        err = io.StringIO()
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["--config", "nope.toml", "--once"])
        self.assertEqual(code, 2)
        self.assertIn("config problem", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())
