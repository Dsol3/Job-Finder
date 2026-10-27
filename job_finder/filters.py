"""Filtering, budget parsing and scoring.

The job of this module is to answer three questions about a post:
  1. Is it a job at all, for work I do?      -> match()
  2. Does it pay, and does it pay enough?    -> budget()
  3. How fast should I reply?                -> score()
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .reddit import Post

# Posts where somebody is selling their own services, never a job for you.
ALWAYS_EXCLUDE = ("[for hire]", "[forhire]", "for hire -")


@dataclass
class Budget:
    amount: float
    unit: str  # word | hour | video | article | month
    raw: str
    lowball: bool = False


_NUM = r"(\d[\d,]*(?:\.\d+)?)"
_UNIT = r"(words?|1,?000\s+words?|hrs?|hours?|articles?|posts?|videos?|shorts?|months?|mo)"

# Order matters: most specific first. Each pattern's first group is the amount
# (except the bulk pattern, where it's the word count).
_BUDGET_PATTERNS = (
    # 5,000 words for $25        -> price per word
    re.compile(rf"\d[\d,]*\s*words?\s*(?:for|at)\s*\$\s*{_NUM}", re.I),
    # 15 cents per word / 8c/word
    re.compile(rf"{_NUM}\s*(?:cents?|c)\s*(?:/|per\s+)\s*words?", re.I),
    # $0.10 - $0.15/word, $50–$80 per article
    re.compile(rf"\$\s*{_NUM}\s*(?:-|–|—|to)\s*\$?\s*\d[\d,]*(?:\.\d+)?\s*(?:/|per\s+|each\s+){_UNIT}", re.I),
    # $0.12/word, $150 per video, $1,200/month
    re.compile(rf"\$\s*{_NUM}\s*(?:/|per\s+|each\s+){_UNIT}", re.I),
)

_UNIT_MAP = {
    "word": "word", "words": "word",
    "1,000 words": "per1000", "1000 words": "per1000",
    "hr": "hour", "hrs": "hour", "hour": "hour", "hours": "hour",
    "article": "article", "articles": "article", "post": "article", "posts": "article",
    "video": "video", "videos": "video", "short": "video", "shorts": "video",
    "month": "month", "months": "month", "mo": "month",
}


def _to_float(raw: str) -> float:
    return float(raw.replace(",", ""))


def parse_budgets(text: str, floors: dict) -> list[Budget]:
    """Pull every pay rate mentioned in the post out of free text."""
    seen: set[tuple[float, str]] = set()
    out: list[Budget] = []

    for index, pattern in enumerate(_BUDGET_PATTERNS):
        for match in pattern.finditer(text):
            groups = match.groups()
            amount_raw = groups[0]

            if index == 0:  # "5,000 words for $25" -> normalise to per-word
                word_count = _to_float(re.search(r"(\d[\d,]*)", match.group(0)).group(1))
                if word_count <= 0:
                    continue
                amount, unit = _to_float(amount_raw) / word_count, "word"
            else:
                unit_raw = (groups[1] if len(groups) > 1 else "words") or ""
                unit_raw = re.sub(r"\s+", " ", unit_raw.strip().lower())
                unit = _UNIT_MAP.get(unit_raw)
                if unit is None:
                    continue
                amount = _to_float(amount_raw)
                if index == 1:  # "15 cents per word" -> dollars
                    amount /= 100

            if unit == "per1000":
                amount, unit = amount / 1000, "word"
            if unit == "month" and amount < 10:  # "4 posts/month" is not a rate
                continue

            key = (round(amount, 4), unit)
            if key in seen:
                continue
            seen.add(key)

            floor = floors.get(f"per_{unit}")
            lowball = bool(floor and amount < float(floor))
            out.append(Budget(amount=amount, unit=unit, raw=match.group(0).strip(), lowball=lowball))
    return out


def format_rate(budget: Budget) -> str:
    if budget.unit == "word":
        if budget.amount < 1:
            return f"${budget.amount:.2f}/word"
        return f"${budget.amount:,.0f}/word"
    return f"${budget.amount:,.0f}/{budget.unit}"


def budget_summary(budgets: list[Budget]) -> str:
    if not budgets:
        return ""
    good = [b for b in budgets if not b.lowball]
    shown = good or budgets
    return " · ".join(format_rate(b) for b in shown[:3])


def _term_hits(text: str, terms: list[str]) -> list[str]:
    hits = []
    for term in terms:
        term = str(term).strip()
        if not term:
            continue
        if term.startswith("re:"):
            try:
                if re.search(term[3:], text, re.I):
                    hits.append(term[3:])
            except re.error:
                continue
        elif term.lower() in text:
            hits.append(term)
    return hits


def match(post: Post, cfg: dict) -> tuple[bool, list[str]]:
    """Return (should_notify, reasons)."""
    text = f"{post.title}\n{post.body}\n{post.flair}".lower()
    lowered_title = post.title.lower()

    for term in ALWAYS_EXCLUDE:
        if term in lowered_title:
            return False, [f"excluded: {term}"]

    exclude_hits = _term_hits(text, cfg["matching"].get("exclude", []))
    if exclude_hits:
        return False, [f"excluded: {h}" for h in exclude_hits[:3]]

    include = cfg["matching"].get("include", [])
    hits = _term_hits(text, include)
    if include and not hits:
        return False, []

    budgets = parse_budgets(text, cfg.get("floors", {}))
    if budgets and all(b.lowball for b in budgets):
        cheapest = min(budgets, key=lambda b: b.amount)
        return False, [f"below rate floor: {format_rate(cheapest)}"]

    post.budget_text = budget_summary(budgets)

    reasons = [f"matched: {', '.join(dict.fromkeys(hits))}"] if hits else ["all posts"]
    if post.budget_text:
        reasons.append(f"budget: {post.budget_text}")
    return True, reasons


def score(post: Post, cfg: dict) -> int:
    """Higher = reply sooner. Capped at 10 so the alert shows a readable signal."""
    total = 0
    title = post.title.lower()
    matching = cfg["matching"]
    budgets = parse_budgets(f"{post.title}\n{post.body}", cfg.get("floors", {}))

    if _term_hits(title, matching.get("priority", [])):
        total += 2  # the actual role you want is in the title
    if _term_hits(title, matching.get("include", [])):
        total += 2
    if budgets:
        total += 2  # they named a number = they have a budget
    if "hiring" in title or "[h]" in title or "hiring" in post.flair.lower():
        total += 1
    if any(w in title for w in ("urgent", "asap", "immediately", "starting today")):
        total += 1
    if post.age_hours <= 2:
        total += 2
    elif post.age_hours <= 6:
        total += 1
    total += min(len(_term_hits(f"{post.title}\n{post.body}", matching.get("boost", []))), 2)
    if post.num_comments > 25:
        total -= 1  # crowded: everyone already replied
    if not post.body.strip():
        total -= 2  # no details = usually a scam or a one-line spam post
    return max(min(total, 10), 0)


def human_age(hours: float) -> str:
    if hours < 1:
        return f"{int(hours * 60)}m ago"
    if hours < 24:
        return f"{hours:.0f}h ago"
    return f"{hours / 24:.0f}d ago"


def process(posts: list[Post], cfg: dict) -> list[Post]:
    """Filter to a scored, best-first list of posts worth notifying about."""
    max_age = float(cfg["reddit"].get("max_age_hours", 36))
    kept = []
    for post in posts:
        if post.age_hours > max_age:
            continue
        ok, reasons = match(post, cfg)
        if not ok:
            continue
        post.match_reasons = reasons
        post.notify_score = score(post, cfg)
        kept.append(post)
    return sorted(kept, key=lambda p: (p.notify_score, -p.age_hours), reverse=True)
