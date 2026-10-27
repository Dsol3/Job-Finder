"""Config loading. TOML in, a plain dict out, with sensible defaults."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

DEFAULTS = {
    "reddit": {
        "subreddits": ["HireaWriter", "forhire"],
        "limit": 100,
        "max_age_hours": 36,
        "request_delay_sec": 2.0,
        "user_agent": "script:job-finder:v1.0 (reddit job watcher)",
    },
    # Curated for content writing + YouTube strategy. Override in config.toml.
    "matching": {
        "include": [
            "content writ", "copywrit", "content strateg", "youtube strateg",
            "channel manag", "channel strateg", "video strateg", "scriptwrit",
            "script writ", "youtube script", "video script", "seo writ",
            "seo content", "blog post", "ghostwrit", "newsletter", "editorial",
            "youtube", "faceless channel", r"re:content\s+(creator|specialist|lead)",
        ],
        # Extra weight when the role itself is in the title — your two lanes.
        "priority": [
            "youtube strateg", "channel strateg", "content strateg",
            "video strateg", "growth", "scriptwrit",
        ],
        "boost": [
            "strateg", "retention", "thumbnail", "packaging", "ctr",
            "full-time", "full time", "retainer", "ongoing", "long term",
            "monthly", "series", "growth", "audit",
        ],
        "exclude": [
            "for hire", "revenue share", "rev-share", "equity only", "equity-only",
            "unpaid", "no pay", "free test", "free sample", "commission only",
            r"re:\bintern(ship)?s?\b", "volunteer", "exposure", "college credit",
            "ai content", "rewrite with ai", "chatgpt", "ai-generated",
            "student", "entry level", "beginner", "essay", "academic", "thesis",
            "crypto", "nft", "betting", "casino", "adult", "onlyfans", "gambling",
        ],
    },
    "floors": {
        "per_word": 0.05,
        "per_hour": 15.0,
        "per_article": 50.0,
        "per_video": 50.0,
    },
    "storage": {"db_path": "seen.sqlite3", "bootstrap": True},
    "notify": {"channel": "console", "telegram_token": "", "telegram_chat_id": ""},
}


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: str | Path | None = None) -> dict:
    """Load TOML config, falling back to DEFAULTS for anything missing.

    Secrets are read from the environment so the config file can be committed:
      TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    """
    cfg = _merge(DEFAULTS, {})
    candidates = [Path(path)] if path else [Path("config.toml"), Path("config.example.toml")]

    for candidate in candidates:
        if candidate.is_file():
            with candidate.open("rb") as fh:
                cfg = _merge(cfg, tomllib.load(fh))
            break

    notify = cfg["notify"]
    notify["telegram_token"] = (
        os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or notify.get("telegram_token", "")
    )
    notify["telegram_chat_id"] = (
        os.environ.get("TELEGRAM_CHAT_ID", "").strip() or notify.get("telegram_chat_id", "")
    )

    subs = [s.strip().removeprefix("r/") for s in cfg["reddit"]["subreddits"] if s.strip()]
    cfg["reddit"]["subreddits"] = subs
    return cfg


def visible_config(cfg: dict) -> dict:
    """Config with secrets masked, for logging."""
    safe = _merge(cfg, {})
    token = safe["notify"].get("telegram_token") or ""
    if token:
        safe["notify"]["telegram_token"] = f"***{token[-4:]}"
    return safe
