"""On-page audit of a site you own — practice, not production.

Fetches a site's sitemap, reads every page, and reports the things that are
cheap to fix and expensive to miss: duplicate titles, missing descriptions,
broken heading structure, noindex accidents, thin pages, missing product schema,
and sitemaps that lie about when content changed.

Deliberately shallow and complete rather than clever: no JS rendering, no
ranking data, no crawling beyond the sitemap. It answers "is this page
publishable?" not "will this page rank?".

    python -m job_finder --site https://ekis.store --site-report audit.md
"""

from __future__ import annotations

import gzip
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html import unescape

TITLE_MIN, TITLE_MAX = 15, 60
DESC_MIN, DESC_MAX = 70, 160
THIN_WORDS = 300
PRODUCT_HINTS = ("/playbooks/", "/kits/", "/products/", "/shop/", "/digital/kits/")


@dataclass
class Page:
    url: str
    status: int = 0
    title: str = ""
    description: str = ""
    h1: list[str] = field(default_factory=list)
    canonical: str = ""
    noindex: bool = False
    words: int = 0
    internal_links: int = 0
    schema_types: list[str] = field(default_factory=list)
    lastmod: str = ""
    error: str = ""

    @property
    def path(self) -> str:
        parsed = urllib.parse.urlparse(self.url)
        return parsed.path or "/"


@dataclass
class Finding:
    severity: str      # high | medium | low
    page: str          # url or "*" for site-wide
    issue: str
    detail: str = ""


def _get(url: str, user_agent: str, timeout: int = 20) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return resp.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, b""
    except Exception:  # noqa: BLE001 - network errors are reported, not raised
        return 0, b""


# --------------------------------------------------------------------- sitemap
_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)
_LASTMOD_RE = re.compile(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", re.I)
_SITEMAP_TAGS = ("sitemapindex", "sitemap")


def parse_sitemap(body: bytes, base: str = "") -> tuple[list[str], dict[str, str], list[str]]:
    """Return (urls, lastmod-by-url, child-sitemaps) from a sitemap or index."""
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
    urls, lastmods, children = [], {}, []

    if "<sitemapindex" in text.lower():
        for block in re.findall(r"<sitemap\b.*?</sitemap>", text, re.I | re.S):
            loc = _LOC_RE.search(block)
            if loc:
                children.append(unescape(loc.group(1)))
        return [], {}, children

    blocks = re.findall(r"<url\b.*?</url>", text, re.I | re.S) or [text]
    for block in blocks:
        loc = _LOC_RE.search(block)
        if not loc:
            continue
        url = unescape(loc.group(1)).strip()
        if not url.startswith(("http://", "https://")):
            url = urllib.parse.urljoin(base, url)
        urls.append(url)
        mod = _LASTMOD_RE.search(block)
        if mod:
            lastmods[url] = mod.group(1).strip()
    return urls, lastmods, children


def _count_priority_tags(body: bytes) -> tuple[int, int]:
    text = body.decode("utf-8", "replace").lower()
    return text.count("<priority>"), text.count("<changefreq>")


def discover(site: str, user_agent: str, out=print) -> tuple[list[str], dict[str, str], dict]:
    """Find the page list via robots.txt then /sitemap.xml. Returns (urls, lastmods, meta)."""
    site = site.rstrip("/")
    meta: dict = {"sitemaps": [], "priority_tags": 0, "changefreq_tags": 0}
    sitemaps: list[str] = []

    status, body = _get(f"{site}/robots.txt", user_agent)
    if status == 200:
        for line in body.decode("utf-8", "replace").splitlines():
            if line.lower().startswith("sitemap:"):
                sitemaps.append(line.split(":", 1)[1].strip())
        out(f"  robots.txt: {len(sitemaps)} sitemap(s) declared")
    else:
        out(f"  robots.txt -> HTTP {status}")

    if not sitemaps:
        sitemaps = [f"{site}/sitemap.xml"]

    urls: list[str] = []
    lastmods: dict[str, str] = {}
    queue = list(sitemaps)
    seen_maps: set[str] = set()

    while queue and len(seen_maps) < 10:
        current = queue.pop(0)
        if current in seen_maps:
            continue
        seen_maps.add(current)
        status, body = _get(current, user_agent)
        if status != 200 or not body:
            out(f"  {current} -> HTTP {status}")
            continue
        meta["sitemaps"].append(current)
        found, found_mods, children = parse_sitemap(body, site)
        prio, freq = _count_priority_tags(body)
        meta["priority_tags"] += prio
        meta["changefreq_tags"] += freq
        urls.extend(found)
        lastmods.update(found_mods)
        queue.extend(children)
        out(f"  {current}: {len(found)} urls" + (f", {len(children)} child sitemaps" if children else ""))

    if not urls and f"{site}/sitemap.xml" not in seen_maps:
        # declared sitemaps were unreachable or empty: try the conventional path
        status, body = _get(f"{site}/sitemap.xml", user_agent)
        if status == 200 and body:
            found, found_mods, children = parse_sitemap(body, site)
            urls.extend(found)
            lastmods.update(found_mods)
            meta["sitemaps"].append(f"{site}/sitemap.xml")
            out(f"  fallback {site}/sitemap.xml: {len(found)} urls")
            queue.extend(children)
            while queue:
                current = queue.pop(0)
                if current in seen_maps:
                    continue
                seen_maps.add(current)
                status, body = _get(current, user_agent)
                if status == 200 and body:
                    found, found_mods, children = parse_sitemap(body, site)
                    urls.extend(found)
                    lastmods.update(found_mods)
                    queue.extend(children)

    # stable de-dupe, keep order
    seen: set[str] = set()
    unique = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique, lastmods, meta


# ------------------------------------------------------------------------ page
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_DESC_RE = re.compile(r'<meta[^>]+name=["\']description["\'][^>]*content=["\'](.*?)["\']', re.I | re.S)
_DESC_RE_ALT = re.compile(r'<meta[^>]+content=["\'](.*?)["\'][^>]*name=["\']description["\']', re.I | re.S)
_CANON_RE = re.compile(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\'](.*?)["\']', re.I | re.S)
_ROBOTS_RE = re.compile(r'<meta[^>]+name=["\']robots["\'][^>]*content=["\'](.*?)["\']', re.I | re.S)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
_LDJSON_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)
_A_RE = re.compile(r"<a\s[^>]*href=[\"']([^\"'#]+)[\"']", re.I)
_SCRIPT_STYLE_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_TYPE_RE = re.compile(r'"@type"\s*:\s*"?([A-Za-z]+)"?')


def _text(html: str) -> str:
    return unescape(_WS_RE.sub(" ", _TAG_RE.sub(" ", html))).strip()


def extract(html: str, url: str) -> Page:
    """Pull the on-page basics out of one HTML document (regex only, no deps)."""
    page = Page(url=url)
    page.status = 200

    match = _TITLE_RE.search(html)
    page.title = _text(match.group(1)) if match else ""

    match = _DESC_RE.search(html) or _DESC_RE_ALT.search(html)
    page.description = unescape(match.group(1)).strip() if match else ""

    page.h1 = [_text(h) for h in _H1_RE.findall(html)]
    page.noindex = bool(_ROBOTS_RE.search(html) and "noindex" in _ROBOTS_RE.search(html).group(1).lower())

    canon = _CANON_RE.search(html)
    page.canonical = unescape(canon.group(1)).strip() if canon else ""

    body = _SCRIPT_STYLE_RE.sub(" ", html)
    page.words = len(_text(body).split())

    host = urllib.parse.urlparse(url).netloc
    links = _A_RE.findall(body)
    page.internal_links = sum(
        1 for link in links
        if link.startswith("/") or host in link
    )

    types: list[str] = []
    for block in _LDJSON_RE.findall(html):
        try:
            data = json.loads(unescape(block).strip())
        except ValueError:
            types.extend(_TYPE_RE.findall(block))  # salvage from malformed blocks
            continue
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                if "@type" in item:
                    value = item["@type"]
                    types.extend(value if isinstance(value, list) else [value])
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)
    page.schema_types = sorted({str(t) for t in types})
    return page


def crawl(urls: list[str], user_agent: str, lastmods: dict[str, str], limit: int = 60,
          delay: float = 1.0, out=print) -> list[Page]:
    """Fetch each URL politely and extract on-page basics."""
    pages: list[Page] = []
    for index, url in enumerate(urls[:limit]):
        status, body = _get(url, user_agent)
        page = extract(body.decode("utf-8", "replace"), url) if status == 200 and body else Page(url=url)
        page.status = status
        if not status:
            page.error = "no response"
        page.lastmod = lastmods.get(url, "")
        pages.append(page)
        if out and (index + 1) % 10 == 0:
            out(f"  … {index + 1}/{min(len(urls), limit)} pages")
        if delay and index < len(urls[:limit]) - 1:
            time.sleep(delay)
    return pages


# -------------------------------------------------------------------- findings
def analyse(pages: list[Page], meta: dict) -> list[Finding]:
    """Turn raw page data into a prioritised fix list."""
    findings: list[Finding] = []
    titles: dict[str, list[str]] = {}
    descs: dict[str, list[str]] = {}

    for page in pages:
        if page.status != 200:
            findings.append(Finding("high", page.url, f"page returns HTTP {page.status or 'no response'}"))
            continue

        if page.noindex:
            findings.append(Finding("high", page.url, "noindex", "this page cannot rank"))
        if not page.title:
            findings.append(Finding("high", page.url, "missing title"))
        elif len(page.title) > TITLE_MAX:
            findings.append(Finding("low", page.url, f"title too long ({len(page.title)} chars)",
                                    page.title[:80]))
        elif len(page.title) < TITLE_MIN:
            findings.append(Finding("medium", page.url, f"title too short ({len(page.title)} chars)",
                                    page.title))
        if page.title:
            titles.setdefault(page.title.lower(), []).append(page.url)

        if not page.description:
            findings.append(Finding("medium", page.url, "missing meta description"))
        elif len(page.description) > DESC_MAX:
            findings.append(Finding("low", page.url, f"description too long ({len(page.description)} chars)"))
        elif len(page.description) < DESC_MIN:
            findings.append(Finding("low", page.url, f"description short ({len(page.description)} chars)"))
        if page.description:
            descs.setdefault(page.description.lower(), []).append(page.url)

        if len(page.h1) == 0:
            findings.append(Finding("high", page.url, "no H1"))
        elif len(page.h1) > 1:
            findings.append(Finding("medium", page.url, f"{len(page.h1)} H1 tags", " | ".join(page.h1[:3])))

        if page.words < THIN_WORDS:
            findings.append(Finding("medium", page.url, f"thin content ({page.words} words)",
                                    f"target at least {THIN_WORDS}"))

        if page.canonical and page.canonical.rstrip("/") != page.url.rstrip("/"):
            findings.append(Finding("medium", page.url, "canonical points elsewhere", page.canonical))

        if page.internal_links == 0:
            findings.append(Finding("low", page.url, "no internal links out of this page"))

        if any(hint in page.path for hint in PRODUCT_HINTS) and not page.schema_types:
            findings.append(Finding("medium", page.url, "no structured data",
                                    "add Product/Offer or Course schema"))

    for title, urls in titles.items():
        if len(urls) > 1:
            findings.append(Finding("high", urls[0], f"duplicate title on {len(urls)} pages", title[:80]))
    for desc, urls in descs.items():
        if len(urls) > 1:
            findings.append(Finding("medium", urls[0], f"duplicate description on {len(urls)} pages",
                                    desc[:80]))

    mods = {p.lastmod for p in pages if p.lastmod}
    if len(mods) == 1 and len(pages) > 3:
        findings.append(Finding("medium", "*", "every page shares one lastmod",
                                f"{mods.pop()} — Google discounts build-time timestamps"))
    if meta.get("priority_tags"):
        findings.append(Finding("low", "*", f"{meta['priority_tags']} <priority> tags",
                                "ignored by Google; safe to remove"))
    if meta.get("changefreq_tags"):
        findings.append(Finding("low", "*", f"{meta['changefreq_tags']} <changefreq> tags",
                                "ignored by Google; safe to remove"))

    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(findings, key=lambda f: (order.get(f.severity, 3), f.page))


# ---------------------------------------------------------------------- report
def render_report(site: str, pages: list[Page], findings: list[Finding], meta: dict) -> str:
    """Markdown report: summary, priorities, then a table of every page."""
    lines = [f"# On-page audit — {site}", ""]
    ok = [p for p in pages if p.status == 200]
    counts = {sev: sum(1 for f in findings if f.severity == sev) for sev in ("high", "medium", "low")}

    lines += [
        f"- pages found in sitemap: **{len(pages)}**",
        f"- pages fetched OK: **{len(ok)}**",
        f"- high / medium / low issues: **{counts['high']} / {counts['medium']} / {counts['low']}**",
        "",
        "## Fix these first",
        "",
    ]

    if counts["high"] == 0:
        lines.append("Nothing critical. Work the medium list.")
    for finding in [f for f in findings if f.severity == "high"][:15]:
        where = finding.page if finding.page == "*" else urllib.parse.urlparse(finding.page).path
        lines.append(f"- **{finding.issue}** — `{where}`" + (f" · {finding.detail}" if finding.detail else ""))

    lines += ["", "## Then these", ""]
    for finding in [f for f in findings if f.severity == "medium"][:25]:
        where = finding.page if finding.page == "*" else urllib.parse.urlparse(finding.page).path
        lines.append(f"- {finding.issue} — `{where}`" + (f" · {finding.detail}" if finding.detail else ""))

    lines += ["", "## Every page", "",
              "| page | status | words | title | desc | h1 | schema |",
              "|---|---|---|---|---|---|---|"]
    for page in pages:
        lines.append(
            f"| `{page.path}` | {page.status or '—'} | {page.words} | "
            f"{'ok' if page.title else '**missing**'} | {'ok' if page.description else '**missing**'} | "
            f"{len(page.h1)} | {', '.join(page.schema_types) or '—'} |"
        )

    lines += ["", "---", "",
              "Generated by `job_finder --site`. Shallow by design: it answers *is this page",
              "publishable*, not *will it rank*. Pair it with Search Console for positions and",
              "with PageSpeed Insights for field performance.", ""]
    return "\n".join(lines)


def run(site: str, user_agent: str = "script:job-finder:v1.0 (site audit)",
        limit: int = 60, delay: float = 1.0, report_path: str = "", out=print) -> int:
    """Full audit for one site. Returns a process exit code."""
    out(f"\n── auditing {site} " + "─" * max(0, 44 - len(site)))
    urls, lastmods, meta = discover(site, user_agent, out=out)
    if not urls:
        out("  no URLs found — is there a sitemap?")
        return 1

    out(f"  {len(urls)} URLs, fetching up to {min(limit, len(urls))} (delay {delay}s)")
    pages = crawl(urls, user_agent, lastmods, limit=limit, delay=delay, out=out)
    findings = analyse(pages, meta)

    counts = {sev: sum(1 for f in findings if f.severity == sev) for sev in ("high", "medium", "low")}
    out("")
    out(f"  HIGH {counts['high']}   MEDIUM {counts['medium']}   LOW {counts['low']}")
    for finding in [f for f in findings if f.severity == "high"][:10]:
        where = finding.page if finding.page == "*" else urllib.parse.urlparse(finding.page).path
        out(f"   ✗ {finding.issue} — {where}")

    if report_path:
        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write(render_report(site, pages, findings, meta))
        out(f"\n  report written to {report_path}")
    return 0
