"""Fetch new posts from public subreddit listings.

No OAuth and no API key: we read the same public feeds a logged-out browser
sees. Reddit aggressively rate-limits and sometimes blocks datacenter IPs, so
we try three endpoints per subreddit before giving up on it:

    1. https://www.reddit.com/r/<sub>/new.json      (richest: flair, scores)
    2. https://old.reddit.com/r/<sub>/new.json
    3. https://www.reddit.com/r/<sub>/new.rss       (Atom, still served when JSON is blocked)

A User-Agent that identifies the tool is required by Reddit and materially
reduces 403/429 responses.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone

ENDPOINTS = (
    "https://www.reddit.com/r/{sub}/new.json?limit={limit}&raw_json=1",
    "https://old.reddit.com/r/{sub}/new.json?limit={limit}&raw_json=1",
    "https://www.reddit.com/r/{sub}/new.rss?limit={limit}",
)


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


def fetch_all(subreddits: list[str], limit: int, user_agent: str, delay: float = 2.0) -> list[Post]:
    """Fetch every subreddit politely, one at a time, with a pause between calls."""
    out: list[Post] = []
    for index, sub in enumerate(subreddits):
        posts = fetch_subreddit(sub, limit, user_agent)
        print(f"  fetched r/{sub}: {len(posts)} new posts")
        out.extend(posts)
        if index < len(subreddits) - 1:
            time.sleep(max(0.0, delay))
    return out


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
