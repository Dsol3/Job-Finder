"""Notification channels: console (free, always on) and Telegram (free, push)."""

from __future__ import annotations

import html
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from .filters import human_age
from .reddit import Post


def render(post: Post) -> str:
    """Plain-text version, used for the console and the JSONL log."""
    lines = [
        f"[{post.notify_score}/10] r/{post.subreddit} · {human_age(post.age_hours)} · u/{post.author}",
        post.title.strip(),
    ]
    if post.budget_text:
        lines.append(f"Budget: {post.budget_text}")
    if post.flair:
        lines.append(f"Flair: {post.flair}")
    lines.append(f"Why: {' | '.join(post.match_reasons)}")
    lines.append(f"{post.num_comments} comments · {post.link}")
    return "\n".join(lines)


def render_html(post: Post) -> str:
    """Telegram HTML (only <b>, <a>, <i> are allowed)."""
    score = post.notify_score
    flame = "🔥" if score >= 7 else ("✅" if score >= 4 else "•")
    head = (
        f"{flame} <b>{score}/10</b> · r/{html.escape(post.subreddit)} · "
        f"{human_age(post.age_hours)}"
    )
    parts = [head, f'<a href="{html.escape(post.link)}">{html.escape(post.title.strip())}</a>']
    if post.budget_text:
        parts.append(f"💰 <b>{html.escape(post.budget_text)}</b>")
    if post.flair:
        parts.append(f"<i>{html.escape(post.flair)}</i>")
    parts.append(f"<i>{html.escape(' | '.join(post.match_reasons))}</i>")
    parts.append(f"{post.num_comments} comments · u/{html.escape(post.author)}")
    return "\n".join(parts)


class Notifier:
    def __init__(self, cfg: dict, dry_run: bool = False, quiet: bool = False):
        self.cfg = cfg["notify"]
        self.dry_run = dry_run
        self.quiet = quiet
        self.log_path = cfg.get("storage", {}).get("log_path", "")
        self.sent = 0
        self.failed = 0

    # -- channels ---------------------------------------------------------
    def _console(self, text: str) -> None:
        if self.quiet:
            return
        print("\n" + "-" * 72)
        print(text)
        print("-" * 72)

    def _telegram(self, post: Post) -> bool:
        token = self.cfg.get("telegram_token", "")
        chat_id = self.cfg.get("telegram_chat_id", "")
        if not token or not chat_id:
            return False

        payload = urllib.parse.urlencode(
            {
                "chat_id": chat_id,
                "text": render_html(post),
                "parse_mode": "HTML",
                "disable_web_page_preview": "false",
            }
        ).encode()
        url = f"https://api.telegram.org/bot{token}/sendMessage"

        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=payload)  # noqa: S310
                with urllib.request.urlopen(req, timeout=20) as resp:
                    body = json.loads(resp.read().decode())
                if body.get("ok"):
                    return True
                print(f"  [warn] Telegram rejected the message: {body.get('description')}")
                return False
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < 2:
                    time.sleep(3 * (attempt + 1))
                    continue
                print(f"  [warn] Telegram HTTP {exc.code}: {exc.reason}")
                return False
            except Exception as exc:  # noqa: BLE001
                if attempt < 2:
                    time.sleep(2)
                    continue
                print(f"  [warn] Telegram send failed: {type(exc).__name__}: {exc}")
                return False
        return False

    def _log_jsonl(self, post: Post) -> None:
        if not self.log_path:
            return
        try:
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "ts": time.time(),
                            "id": post.id,
                            "subreddit": post.subreddit,
                            "title": post.title,
                            "link": post.link,
                            "budget": post.budget_text,
                            "score": post.notify_score,
                            "age_hours": round(post.age_hours, 2),
                        }
                    )
                    + "\n"
                )
        except OSError as exc:
            print(f"  [warn] could not write match log: {exc}")

    # -- public -----------------------------------------------------------
    def send(self, post: Post) -> None:
        text = render(post)
        self._console(text)
        self._log_jsonl(post)

        if self.dry_run or self.cfg.get("channel") == "console":
            self.sent += 1
            return

        if self._telegram(post):
            self.sent += 1
        else:
            self.failed += 1

    def message(self, text: str) -> None:
        """One-off status message (startup, errors, test) to the push channel."""
        if self.dry_run or self.cfg.get("channel") == "console":
            print(f"[status] {text}")
            return
        token = self.cfg.get("telegram_token", "")
        chat_id = self.cfg.get("telegram_chat_id", "")
        if not token or not chat_id:
            print(f"[status] {text}")
            return
        try:
            payload = urllib.parse.urlencode(
                {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
            ).encode()
            req = urllib.request.Request(  # noqa: S310
                f"https://api.telegram.org/bot{token}/sendMessage", data=payload
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                ok = json.loads(resp.read().decode()).get("ok")
            print(f"[status] {text}" + ("" if ok else " (delivery failed)"))
        except Exception as exc:  # noqa: BLE001
            print(f"[status] {text} (delivery failed: {type(exc).__name__})")
