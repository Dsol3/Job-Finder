"""Fetch new posts from public subreddit listings.

No OAuth and no API key: we read the same public feeds a logged-out browser
sees. Reddit aggressively rate-limits (403, then 429) and sometimes blocks
datacenter IPs, so two rules govern everything here:

  1. COALESCE. Reddit serves a multi-sub listing at /r/a+b+c/new.json, so all
     of your boards arrive in ONE request instead of one request per board.
     Eight boards used to mean up to 24 requests once retries kicked in; that
     is what tripped the throttle.
  2. BACK OFF. On 403/429 wait 15s, 30s, 60s (with jitter) before retrying the
     next endpoint, instead of hammering immediately and digging deeper.

Each batch tries three endpoints before giving up:

    1. https://www.reddit.com/r/<a+b+c>/new.json      (richest: flair, scores)
    2. https://old.reddit.com/r/<a+b+c>/new.json
    3. https://www.reddit.com/r/<a+b+c>/new.rss       (Atom, still served when JSON is blocked)

A User-Agent that identifies the tool is required by Reddit and materially
reduces 403/429 responses.
"""

from __future__ import annotations

import json
import random
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ENDPOINTS = (
    "https://www.reddit.com/r/{sub}/new.json?limit={limit}&raw_json=1",
    "https://old.reddit.com/r/{sub}/new.json?limit={limit}&raw_json=1",
    "https://www.reddit.com/r/{sub}/new.rss?limit={limit}",
)

MULTI_BATCH = 8      # boards per request (Reddit caps a multi-sub at 100)
LIMIT_MAX = 100      # Reddit caps a listing at 100 posts
BACKOFF_BASE = 15.0  # seconds; doubled per retry
BACKOFF_CAP = 90.0
RETRY_CODES = (403, 429, 500, 502, 503)


@dataclass
class Post:
    id: str
    subreddit: str
    title: str
    body: str
    author: str
    url: str
    permalink: str
    created_utc: float
    flair: str = ""
    score: int = 0
    num_comments: int = 0
    match_reasons: list[str] = field(default_factory=list)
    budget_text: str = ""
    notify_score: int = 0

    @property
    def age_hours(self) -> float:
        return max(0.0, (time.time() - self.created_utc) / 3600)

    @property
    def link(self) -> str:
        return f"https://www.reddit.com{self.permalink}" if self.permalink else self.url


def _now() -> float:
    return datetime.now(timezone.utc).timestamp()


def _http_get(url: str, user_agent: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json, application/atom+xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def _parse_json(payload: bytes, subreddit: str) -> list[Post]:
    data = json.loads(payload.decode("utf-8", "replace"))
    posts: list[Post] = []
    for child in data.get("data", {}).get("children", []):
        d = child.get("data", {})
        if not d.get("id"):
            continue
        posts.append(
            Post(
                id=d["id"],
                subreddit=d.get("subreddit", subreddit),
                title=d.get("title", ""),
                body=d.get("selftext", "") or "",
                author=d.get("author", ""),
                url=d.get("url", ""),
                permalink=d.get("permalink", ""),
                created_utc=float(d.get("created_utc", _now())),
                flair=d.get("link_flair_text", "") or "",
                score=int(d.get("score", 0) or 0),
                num_comments=int(d.get("num_comments", 0) or 0),
            )
        )
    return posts


_ATOM = "{http://www.w3.org/2005/Atom}"


def _parse_rss(payload: bytes, subreddit: str) -> list[Post]:
    root = ET.fromstring(payload.decode("utf-8", "replace"))
    posts: list[Post] = []
    for entry in root.findall(f"{_ATOM}entry"):
        link_el = entry.find(f"{_ATOM}link")
        link = link_el.get("href", "") if link_el is not None else ""
        post_id = (entry.findtext(f"{_ATOM}id") or "").rsplit("_", 1)[-1]
        if not post_id:
            continue
        published = entry.findtext(f"{_ATOM}published") or ""
        try:
            created = datetime.fromisoformat(published.replace("Z", "+00:00")).timestamp()
        except ValueError:
            created = _now()
        category = entry.find(f"{_ATOM}category")
        posts.append(
            Post(
                id=post_id,
                subreddit=subreddit,
                title=_clean_html(entry.findtext(f"{_ATOM}title") or ""),
                body=_clean_html(entry.findtext(f"{_ATOM}content") or ""),
                author=(entry.findtext(f"{_ATOM}author/{_ATOM}name") or "").removeprefix("/u/"),
                url=link,
                permalink=link.removeprefix("https://www.reddit.com"),
                created_utc=created,
                flair=category.get("term", "") if category is not None else "",
            )
        )
    return posts


_TAG_RE = re.compile(r"<[^>]+>")
_ENTITIES = (
    ("&amp;", "&"),
    ("&lt;", "<"),
    ("&gt;", ">"),
    ("&quot;", '"'),
    ("&#39;", "'"),
    ("&#32;", " "),
)


def _clean_html(text: str) -> str:
    text = re.sub(r"<!--\s*SC_OFF\s*-->|<!--\s*SC_ON\s*-->", " ", text)
    text = _TAG_RE.sub(" ", text)
    for entity, char in _ENTITIES:
        text = text.replace(entity, char)
    return re.sub(r"\s+", " ", text).strip()


def fetch_subreddit(subreddit: str, limit: int, user_agent: str) -> list[Post]:
    """Try each endpoint until one yields posts. Returns [] if all fail."""
    errors = []
    for template in ENDPOINTS:
        url = template.format(sub=subreddit, limit=limit)
        try:
            payload = _http_get(url, user_agent)
            if not payload.strip():
                errors.append(f"{url} -> empty body")
                continue
            is_rss = ".rss" in url.split("?")[0]
            posts = _parse_rss(payload, subreddit) if is_rss else _parse_json(payload, subreddit)
            if posts:
                return posts
            errors.append(f"{url} -> 0 posts")
        except urllib.error.HTTPError as exc:
            errors.append(f"{url} -> HTTP {exc.code}")
            if exc.code == 429:
                time.sleep(5)
        except Exception as exc:  # noqa: BLE001 - network/parse errors are all non-fatal
            errors.append(f"{url} -> {type(exc).__name__}: {exc}")
    print(f"  [warn] r/{subreddit}: every endpoint failed ({'; '.join(errors)})")
    return []


@dataclass
class FetchResult:
    """What a sweep actually managed to read, so silence can be explained."""

    posts: list[Post] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)   # board -> posts seen
    attempted: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)      # boards that returned nothing
    requests: int = 0

    @property
    def boards_ok(self) -> int:
        return sum(1 for s in self.attempted if self.counts.get(s.lower(), 0) > 0)

    @property
    def complete(self) -> bool:
        return bool(self.attempted) and not self.failures

    def summary(self) -> str:
        line = f"{len(self.posts)} posts from {self.boards_ok}/{len(self.attempted)} boards"
        if self.failures:
            line += f" · silent: {', '.join(self.failures)}"
        return line


def _backoff(attempt: int) -> float:
    """Sleep before the next endpoint attempt. Returns the delay (for tests)."""
    delay = min(BACKOFF_CAP, BACKOFF_BASE * (2 ** attempt))
    delay *= 1.0 + random.random() * 0.3  # jitter: retries must not synchronise
    time.sleep(delay)
    return delay


def batch_urls(group: list[str], limit: int) -> tuple[str, str, str]:
    """The three endpoint URLs for one batch of boards (multi-sub syntax)."""
    joined = "+".join(group)
    return tuple(t.format(sub=joined, limit=limit) for t in ENDPOINTS)  # type: ignore[return-value]


def _fetch_batch(group: list[str], limit: int, user_agent: str) -> tuple[list[Post], int, list[str]]:
    """Fetch one batch, trying each endpoint with backoff. Returns (posts, requests, errors)."""
    requests_made = 0
    errors: list[str] = []

    for attempt, url in enumerate(batch_urls(group, limit)):
        short = url.split("?")[0]
        requests_made += 1
        try:
            payload = _http_get(url, user_agent)
            if not payload.strip():
                errors.append(f"{short} -> empty body")
                continue
            is_rss = ".rss" in short
            posts = _parse_rss(payload, "+".join(group)) if is_rss else _parse_json(payload, "+".join(group))
            if posts:
                return posts, requests_made, []
            errors.append(f"{short} -> 0 posts")
        except urllib.error.HTTPError as exc:
            errors.append(f"{short} -> HTTP {exc.code}")
            if exc.code in RETRY_CODES:
                _backoff(attempt)
        except Exception as exc:  # noqa: BLE001 - network/parse errors are all non-fatal
            errors.append(f"{short} -> {type(exc).__name__}: {exc}")

    return [], requests_made, errors


def fetch_all(
    subreddits: list[str],
    limit: int,
    user_agent: str,
    delay: float = 2.0,
) -> FetchResult:
    """Read every board in as few requests as possible.

    All boards are requested together (r/a+b+c/new.json), so eight subreddits
    cost one request instead of eight — the fix for the 403/429 throttle.
    """
    subs = [s.strip().removeprefix("r/") for s in subreddits if s and s.strip()]
    result = FetchResult(attempted=subs)
    if not subs:
        return result

    per_call = max(25, min(int(limit), LIMIT_MAX))
    batches = [subs[i:i + MULTI_BATCH] for i in range(0, len(subs), MULTI_BATCH)]

    for index, group in enumerate(batches, 1):
        posts, requests_made, errors = _fetch_batch(group, per_call, user_agent)
        result.requests += requests_made
        result.posts.extend(posts)

        for post in posts:
            key = post.subreddit.lower()
            result.counts[key] = result.counts.get(key, 0) + 1

        seen_here = {p.subreddit.lower() for p in posts}
        missing = [s for s in group if s.lower() not in seen_here]
        result.failures.extend(missing)

        label = f"batch {index}/{len(batches)}"
        if posts:
            extra = f" · nothing new in: {', '.join(missing)}" if missing else ""
            print(f"  {label}: {len(posts)} posts{extra}")
        else:
            print(f"  {label}: FAILED — {'; '.join(errors) or 'no posts'}")

        if index < len(batches):
            time.sleep(max(0.0, delay))

    print(f"  {result.summary()}")
    return result


def health_path(cfg: dict) -> Path:
    """Where per-board coverage is remembered, next to the dedupe database."""
    db = Path(cfg.get("storage", {}).get("db_path", "seen.sqlite3"))
    return db.parent / "fetch_health.json"


def write_health(cfg: dict, result: FetchResult) -> None:
    """Record the last time each board returned posts, so silent boards are visible."""
    path = health_path(cfg)
    now = _now()
    state: dict[str, dict] = {}
    try:
        if path.is_file():
            state = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        state = {}

    for board in result.attempted:
        key = board.lower()
        entry = state.get(key, {"last_ok": 0, "misses": 0})
        if result.counts.get(key, 0) > 0:
            entry["last_ok"] = now
            entry["misses"] = 0
        else:
            entry["misses"] = int(entry.get("misses", 0)) + 1
        state[key] = entry

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    except OSError as exc:
        print(f"  [warn] could not write fetch health: {exc}")


def stale_boards(cfg: dict, hours: float = 12.0) -> list[tuple[str, float]]:
    """Boards that have not returned posts within `hours`. Returns (board, hours_silent)."""
    path = health_path(cfg)
    if not path.is_file():
        return []
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    now = _now()
    out = []
    for board, entry in state.items():
        last_ok = float(entry.get("last_ok", 0) or 0)
        silent = (now - last_ok) / 3600 if last_ok else 999.0
        if silent >= hours:
            out.append((board, silent))
    return sorted(out, key=lambda item: -item[1])


def load_fixture(path: str, subreddit: str = "fixture", rebase: bool = True) -> list[Post]:
    """Read a saved .json/.rss payload so the pipeline can be tested offline.

    Fixture JSON may carry a `_age_hours` field per post; when present (and
    rebase is on) timestamps are rewritten relative to now so the file never
    goes stale for age-based filters.
    """
    with open(path, "rb") as fh:
        payload = fh.read()
    if path.endswith(".rss"):
        return _parse_rss(payload, subreddit)

    posts = _parse_json(payload, subreddit)
    if not rebase:
        return posts

    ages: dict[str, float] = {}
    try:
        data = json.loads(payload.decode("utf-8", "replace"))
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            if "_age_hours" in d:
                ages[d["id"]] = float(d["_age_hours"])
    except (ValueError, TypeError):
        pass

    newest = max((p.created_utc for p in posts), default=0)
    for post in posts:
        if post.id in ages:
            post.created_utc = _now() - ages[post.id] * 3600
        elif newest:
            post.created_utc = _now() - max(0.0, (newest - post.created_utc) / 3600 + 0.1) * 3600
    return posts
