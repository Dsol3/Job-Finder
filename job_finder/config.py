"""Config loading. TOML in, a plain dict out, with sensible defaults."""

from __future__ import annotations

import os
import re
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # Python 3.10 and older (e.g. Ubuntu 22.04)
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover - interpreter dependent
        tomllib = None  # type: ignore[assignment]


class ConfigError(RuntimeError):
    pass

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
    # Your own site: `--site` with no argument audits whatever is set here.
    "practice": {"site": ""},
    "storage": {"db_path": "seen.sqlite3", "bootstrap": True},
    # "auto" = Telegram when credentials exist, otherwise console.
    "notify": {"channel": "auto", "telegram_token": "", "telegram_chat_id": ""},
}


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load_env_file(*candidates: str | Path) -> None:
    """Load KEY=VALUE pairs from .env into os.environ (real env vars win)."""
    from .telegram import parse_env

    paths = list(candidates) or [
        Path(".env"),
        Path(__file__).resolve().parents[1] / ".env",
    ]
    for candidate in paths:
        for key, value in parse_env(candidate).items():
            os.environ.setdefault(key, value)


def load_config(path: str | Path | None = None) -> dict:
    """Load TOML config, falling back to DEFAULTS for anything missing.

    Secrets are read from the environment so the config file can be committed:
      TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    """
    load_env_file()
    cfg = _merge(DEFAULTS, {})

    if path:
        # An explicit --config is a promise: if it is missing or unreadable we
        # must fail loudly. Silently falling back to built-in defaults once hid
        # a missing --config file and made the watcher check only 2 boards.
        explicit = Path(path)
        if not explicit.is_file():
            raise ConfigError(
                f"config file not found: {explicit}\n"
                f"  (looked in {explicit.resolve().parent})\n"
                "  Check the path, or run 'git pull' if it should have been committed."
            )
        candidates = [explicit]
    else:
        candidates = [Path("config.toml"), Path("config.example.toml")]

    for candidate in candidates:
        if candidate.is_file():
            if tomllib is None:
                raise ConfigError(
                    f"{candidate} exists but this Python cannot read TOML.\n"
                    f"  Python {os.sys.version_info.major}.{os.sys.version_info.minor} has no tomllib.\n"
                    "  Fix with either:\n"
                    "    python3 -m pip install --user tomli\n"
                    "    or upgrade to Python 3.11+"
                )
            try:
                with candidate.open("rb") as fh:
                    loaded = tomllib.load(fh)
            except ConfigError:
                raise
            except Exception as exc:  # noqa: BLE001 - tomllib's error type varies
                raise ConfigError(_toml_help(candidate, exc)) from None
            cfg = _merge(cfg, loaded)
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


def _toml_help(path: Path, exc: Exception) -> str:
    """Turn a TOML parser error into something a human can act on."""
    message = str(exc)
    location = ""
    match = re.search(r"line (\d+), column (\d+)", message)
    if match:
        line_no = int(match.group(1))
        try:
            line = path.read_text(encoding="utf-8").splitlines()[line_no - 1].strip()
            location = f"\n  line {line_no}: {line}"
        except (OSError, IndexError):
            location = f"\n  line {line_no}"
    hint = ""
    if "twice" in message or "already exists" in message:
        hint = ("\n  A [section] appears more than once. Merge them, or start fresh:\n"
                f"    copy config.example.toml {path.name}")
    elif "Expected" in message or "Unclosed" in message:
        hint = "\n  Usually a missing or unbalanced quote somewhere near that line."
    return (
        f"{path} is not valid TOML:{location}\n"
        f"  {message.splitlines()[0]}{hint}"
    )


def visible_config(cfg: dict) -> dict:
    """Config with secrets masked, for logging."""
    safe = _merge(cfg, {})
    token = safe["notify"].get("telegram_token") or ""
    if token:
        safe["notify"]["telegram_token"] = f"***{token[-4:]}"
    return safe
