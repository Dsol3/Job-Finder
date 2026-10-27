"""Telegram helpers: token validation, chat discovery, setup wizard, doctor.

The painful part of wiring up a bot is finding your numeric chat id. Rather than
making you read raw JSON from /getUpdates, the wizard long-polls the API until
you press Start in Telegram and picks the chat up automatically.
"""

from __future__ import annotations

import json
import os
import re
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TG_API = "https://api.telegram.org"  # overridable in tests
TOKEN_RE = re.compile(r"^\d{6,}:[A-Za-z0-9_-]{30,}$")
ENV_TOKEN = "TELEGRAM_BOT_TOKEN"
ENV_CHAT = "TELEGRAM_CHAT_ID"


# ---------------------------------------------------------------- http layer
def api(token: str, method: str, timeout: int = 20, **params) -> dict:
    """Call a Bot API method. Never raises for API-level errors; returns ok=false."""
    url = f"{TG_API}/bot{token}/{method}"
    data = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}).encode() or None
    req = urllib.request.Request(url, data=data)  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001
            return {"ok": False, "description": f"HTTP {exc.code} {exc.reason}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "description": f"{type(exc).__name__}: {exc}"}


def get_me(token: str) -> dict:
    return api(token, "getMe", timeout=15)


def send_message(token: str, chat_id: str | int, text: str, html: bool = True) -> dict:
    return api(
        token,
        "sendMessage",
        chat_id=chat_id,
        text=text,
        parse_mode="HTML" if html else None,
        disable_web_page_preview="false",
    )


def get_chat(token: str, chat_id: str | int) -> dict:
    return api(token, "getChat", chat_id=chat_id, timeout=15)


def _chats_from_updates(updates: list[dict]) -> list[dict]:
    """Pull every distinct chat out of a getUpdates payload, newest first."""
    found: dict[int, dict] = {}
    for update in updates or []:
        for key in ("message", "edited_message", "channel_post", "my_chat_member"):
            msg = update.get(key)
            if not msg or not isinstance(msg.get("chat"), dict):
                continue
            chat = msg["chat"]
            name = chat.get("title") or " ".join(
                filter(None, [chat.get("first_name"), chat.get("last_name")])
            ) or chat.get("username") or str(chat.get("id"))
            found[chat["id"]] = {
                "id": chat["id"],
                "type": chat.get("type", "private"),
                "name": name,
                "username": chat.get("username", ""),
            }
    return list(found.values())


def find_chats(token: str, timeout: int = 90, poll: int = 5, tick=None) -> list[dict]:
    """Long-poll getUpdates until at least one chat messages the bot."""
    deadline = time.time() + timeout
    seen: dict[int, dict] = {}
    while time.time() < deadline:
        resp = api(token, "getUpdates", timeout=poll + 10, offset=None, limit=50)
        if resp.get("ok"):
            for chat in _chats_from_updates(resp.get("result", [])):
                seen[chat["id"]] = chat
            if seen:
                return list(seen.values())
        elif "409" in str(resp.get("description", "")) or "Conflict" in str(resp.get("description", "")):
            return []  # another process is polling this bot (e.g. --loop is running)
        if tick:
            tick(int(max(0, deadline - time.time())))
        time.sleep(poll)
    return list(seen.values())


# ------------------------------------------------------------------ .env file
def parse_env(path: str | Path) -> dict[str, str]:
    out: dict[str, str] = {}
    p = Path(path)
    if not p.is_file():
        return out
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key:
            out[key] = value
    return out


def write_env(path: str | Path, values: dict[str, str]) -> Path:
    """Merge values into .env, preserving other keys and comments; chmod 600."""
    p = Path(path)
    wanted = {k: v for k, v in values.items() if v}
    lines: list[str] = []
    written: set[str] = set()

    if p.is_file():
        for raw in p.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            key = stripped.partition("=")[0].strip().removeprefix("export ").strip()
            if stripped and not stripped.startswith("#") and "=" in stripped and key in wanted:
                lines.append(f"{key}={wanted[key]}")
                written.add(key)
            else:
                lines.append(raw)
    else:
        lines = [
            "# job_finder secrets — never commit this file.",
            "# Loaded automatically; real environment variables take precedence.",
        ]

    for key, value in wanted.items():
        if key not in written:
            lines.append(f"{key}={value}")

    p.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    try:
        p.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600
    except OSError:
        pass
    return p


# ------------------------------------------------------------------- wizard
def _ask(prompt: str, default: str = "") -> str:
    try:
        answer = input(prompt).strip()
    except EOFError:
        return ""
    return answer or default


def mask(token: str) -> str:
    return f"…{token[-4:]}" if len(token) > 4 else "…"


def validate_token(token: str) -> tuple[bool, str]:
    if not token:
        return False, "no token given"
    if not TOKEN_RE.match(token):
        return False, "that doesn't look like a bot token (expected 123456789:AAH... — copy it from @BotFather)"
    return True, ""


def run_wizard(
    env_path: str | Path = ".env",
    preset_token: str = "",
    preset_chat: str = "",
    ask=_ask,
    out=print,
    wait_timeout: int = 120,
) -> int:
    """Interactive (or fully scripted) Telegram setup. Returns a process exit code."""
    out("\n── Telegram setup " + "─" * 46)

    # 1. token ------------------------------------------------------------
    token = (preset_token or os.environ.get(ENV_TOKEN, "") or "").strip()
    if not token:
        out("\n1/3  Get a bot token")
        out("     • Open Telegram → @BotFather → send /newbot")
        out("     • Pick a name, then a username ending in 'bot'")
        out("     • It replies with a token like 8123456789:AAH-xxxxxxxxxxxxxxxxxxxxxxxxx\n")
        token = ask("     Paste token (or press Enter to abort): ").strip()

    ok, problem = validate_token(token)
    if not ok:
        out(f"✗ {problem}")
        return 2

    me = get_me(token)
    if not me.get("ok"):
        out(f"✗ Telegram rejected that token: {me.get('description', 'unknown error')}")
        out("  Check you copied the whole token with no spaces, and that the bot still exists.")
        return 2

    bot = me["result"]
    username = bot.get("username", "")
    out(f"✓ Connected to @{username} (token {mask(token)})")

    # 2. chat id ----------------------------------------------------------
    chat_id = (preset_chat or os.environ.get(ENV_CHAT, "") or "").strip()
    if not chat_id:
        out("\n2/3  Find your chat id")
        out(f"     Open https://t.me/{username} and tap START (or send it any message).")
        out("     Waiting for your message…", )

        def tick(seconds_left: int) -> None:
            out(f"     …still waiting ({seconds_left}s left)")

        chats = find_chats(token, timeout=wait_timeout, tick=tick)

        if not chats:
            out("\n     Didn't see a message. Two options:")
            out(f"       • send /start to @{username} and run this again, or")
            out("       • paste your numeric chat id if you already know it")
            chat_id = ask("     Chat id (Enter to abort): ").strip()
            if not chat_id:
                out("✗ No chat id, stopping. Nothing was saved.")
                return 2
        elif len(chats) > 1:
            out("\n     Found several chats:")
            for index, chat in enumerate(chats, 1):
                kind = "group" if chat["type"] != "private" else "private"
                out(f"       {index}. {chat['name']} — {chat['id']} ({kind})")
            choice = ask(f"     Which one? [1-{len(chats)}] (default 1): ", "1")
            try:
                chat_id = str(chats[max(0, min(len(chats) - 1, int(choice) - 1))]["id"])
            except (ValueError, IndexError):
                chat_id = str(chats[0]["id"])
        else:
            chat = chats[0]
            chat_id = str(chat["id"])
            out(f"✓ Found chat: {chat['name']} ({chat_id})")

    who = get_chat(token, chat_id)
    if not who.get("ok"):
        out(f"✗ Could not use chat {chat_id}: {who.get('description', 'unknown error')}")
        out("  For a private chat you must message the bot first. For a group, add the bot to it.")
        return 2
    label = who["result"].get("title") or who["result"].get("first_name") or chat_id
    out(f"✓ Chat verified: {label}")

    # 3. test message + save ----------------------------------------------
    sent = send_message(
        token,
        chat_id,
        "✅ <b>job_finder test</b>\nYou're connected. This is what an alert will look like.",
    )
    if not sent.get("ok"):
        out(f"✗ Test message failed: {sent.get('description', 'unknown error')}")
        return 2
    out("✓ Test message sent — check Telegram.")

    path = write_env(env_path, {ENV_TOKEN: token, ENV_CHAT: chat_id})
    out(f"\nSaved to {path} (permissions 600). Secrets stay out of git.")
    out("Next: python3 -m job_finder --doctor   then   python3 -m job_finder --once")
    return 0


# ------------------------------------------------------------------- doctor
def run_doctor(cfg: dict, store=None, out=print) -> int:
    """Check config, Reddit reachability and Telegram credentials in one pass."""
    from . import reddit

    problems = 0

    def line(status: str, text: str) -> None:
        out(f"  {status}  {text}")

    out("\n── doctor " + "─" * 55)

    subs = cfg["reddit"]["subreddits"]
    line("✓", f"{len(subs)} subreddits configured: {', '.join(subs[:5])}"
         + (" …" if len(subs) > 5 else ""))
    line("✓", f"include rules: {len(cfg['matching'].get('include', []))}"
         f" · exclude rules: {len(cfg['matching'].get('exclude', []))}"
         f" · floors: {cfg['floors'].get('per_word')}/word")
    if store is not None:
        line("✓", f"{store.count()} posts remembered in {cfg['storage'].get('db_path')}")

    token = cfg["notify"].get("telegram_token", "")
    chat_id = cfg["notify"].get("telegram_chat_id", "")
    if not token or not chat_id:
        problems += 1
        line("✗", "Telegram credentials missing — run: python3 -m job_finder --setup-telegram")
    else:
        me = get_me(token)
        if me.get("ok"):
            line("✓", f"bot token valid (@{me['result'].get('username')}, {mask(token)})")
        else:
            problems += 1
            line("✗", f"bot token rejected: {me.get('description', 'unknown error')}")
        if me.get("ok"):
            chat = get_chat(token, chat_id)
            if chat.get("ok"):
                name = chat["result"].get("title") or chat["result"].get("first_name") or chat_id
                line("✓", f"chat reachable: {name} ({chat_id})")
            else:
                problems += 1
                line("✗", f"chat unreachable: {chat.get('description', 'unknown error')}")

    sample = subs[0] if subs else "forhire"
    posts = reddit.fetch_subreddit(sample, 5, cfg["reddit"].get("user_agent", "job-finder"))
    if posts:
        line("✓", f"reddit reachable — r/{sample} returned {len(posts)} posts")
    else:
        problems += 1
        line("✗", f"reddit unreachable from this network for r/{sample} "
                  f"(403/429/timeout — see Troubleshooting in README)")

    out("")
    if problems:
        out(f"{problems} problem(s) found.")
        return 1
    out("All good. Run: python3 -m job_finder --once")
    return 0
