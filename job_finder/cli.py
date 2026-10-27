"""Command line entry point.

    python -m job_finder --once              one sweep, notify on new matches
    python -m job_finder --loop              sweep forever (interval from config)
    python -m job_finder --dry-run           print matches, touch nothing else
    python -m job_finder --fixture file.json replay a saved payload offline
    python -m job_finder --demo              push one sample alert (no store writes)
    python -m job_finder --setup-telegram    interactive telegram setup
    python -m job_finder --doctor            check config, reddit, telegram
    python -m job_finder --test-telegram     verify credentials
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

from . import reddit, telegram
from .config import ConfigError, load_config
from .filters import process
from .notify import Notifier
from .store import Store

BANNER = "reddit job watcher"


def sweep(cfg: dict, args, notifier: Notifier, store: Store) -> int:
    if args.fixture:
        posts = reddit.load_fixture(args.fixture)
        print(f"  loaded {len(posts)} posts from {args.fixture}")
    else:
        cfg_reddit = cfg["reddit"]
        if args.subreddits:
            subs = [s.strip().removeprefix("r/") for s in args.subreddits.split(",") if s.strip()]
        else:
            subs = cfg_reddit["subreddits"]
        print(f"[{time.strftime('%H:%M:%S')}] checking {len(subs)} subreddits: {', '.join(subs)}")
        result = reddit.fetch_all(
            subs,
            limit=int(cfg_reddit.get("limit", 100)),
            user_agent=cfg_reddit.get("user_agent", "job-finder"),
            delay=float(cfg_reddit.get("request_delay_sec", 2.0)),
        )
        posts = result.posts
        if result.attempted:
            reddit.write_health(cfg, result)

    bootstrap = cfg["storage"].get("bootstrap", True) and store.count() == 0
    matches = process(posts, cfg)

    if bootstrap and not args.fixture and not args.dry_run:
        store.mark_many(posts)
        print(
            f"  baseline run: recorded {len(posts)} existing posts as seen "
            f"(sources {len(matches)} that would match). Only NEW posts from now on."
        )
        return 0

    new = [p for p in matches if store.is_new(p.id)]
    print(f"  {len(matches)} matched filters · {len(new)} unseen")

    for post in new:
        notifier.send(post)
        if not args.dry_run:
            store.mark(post.id, post.subreddit, post.title, post.notify_score)

    if not new and not args.quiet:
        print("  nothing new.")
    return len(new)


def _utf8_console() -> None:
    """Windows consoles default to cp1252/cp437, which chokes on ✓ and box drawing
    when output is redirected to a file. Force UTF-8 and degrade instead of crash."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - not available on every stream type
            pass


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    parser = argparse.ArgumentParser(prog="job_finder", description=f"{BANNER} for Reddit")
    parser.add_argument("--config", default=None, help="path to config.toml")
    parser.add_argument("--once", action="store_true", help="one sweep then exit (default)")
    parser.add_argument("--loop", action="store_true", help="keep sweeping forever")
    parser.add_argument("--interval", type=int, default=0, help="seconds between sweeps (loop mode)")
    parser.add_argument("--dry-run", action="store_true", help="print matches, send nothing, save nothing")
    parser.add_argument("--fixture", default=None, help="read a saved .json/.rss payload instead of the network")
    parser.add_argument("--subreddits", default=None, help="comma separated override, e.g. HireaWriter,forhire")
    parser.add_argument("--demo", action="store_true", help="send one sample alert from the fixture to your push channel")
    parser.add_argument("--setup-telegram", action="store_true", help="interactive Telegram setup (writes .env)")
    parser.add_argument("--doctor", action="store_true", help="check config, Reddit and Telegram")
    parser.add_argument("--test-telegram", action="store_true", help="send a test message and exit")
    parser.add_argument("--token", default="", help="bot token for --setup-telegram (non-interactive)")
    parser.add_argument("--chat-id", default="", help="chat id for --setup-telegram (skips discovery)")
    parser.add_argument("--stats", action="store_true", help="show how many posts are stored")
    parser.add_argument("--quiet", action="store_true", help="no console output per match")
    parser.add_argument("--prune", type=int, default=0, metavar="DAYS", help="drop seen posts older than DAYS")
    args = parser.parse_args(argv)

    if args.setup_telegram:
        env_path = Path(args.config).parent / ".env" if args.config else Path(".env")
        return telegram.run_wizard(
            env_path=env_path,
            preset_token=args.token,
            preset_chat=args.chat_id,
        )

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"\n  config problem:\n  {exc}\n", file=sys.stderr)
        return 2

    store = Store(cfg["storage"].get("db_path", "seen.sqlite3"))
    notifier = Notifier(cfg, dry_run=args.dry_run, quiet=args.quiet)

    if args.demo:
        try:
            demo_cfg = load_config(args.config)
        except ConfigError as exc:
            print(f"\n  config problem:\n  {exc}\n", file=sys.stderr)
            store.close()
            return 2
        demo_cfg["notify"]["channel"] = "telegram"
        demo_notifier = Notifier(demo_cfg, dry_run=False, quiet=False)
        posts = reddit.load_fixture(str(Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "forhire_new.json"))
        ranked = process(posts, demo_cfg)
        if not ranked:
            print("no fixture post matched — check your include rules in config.toml")
            store.close()
            return 1
        sample = ranked[0]
        sample.title = "[SAMPLE — not a real post] " + sample.title
        demo_notifier.send(sample)
        print(f"\n  demo sent via {demo_notifier.mode} "
              f"({demo_notifier.sent} ok, {demo_notifier.failed} failed). Nothing was saved to the seen store.")
        store.close()
        return 0 if demo_notifier.failed == 0 else 1

    if args.doctor:
        code = telegram.run_doctor(cfg, store)
        store.close()
        return code

    if args.stats:
        print(f"{store.count()} posts in {cfg['storage'].get('db_path')}")
        store.close()
        return 0

    if args.prune:
        store.prune(args.prune)
        print(f"pruned; {store.count()} posts remain")

    if args.test_telegram:
        notifier.message(
            "✅ <b>job_finder</b> is wired up. Test alert — if you can read this, "
            "your Telegram credentials work."
        )
        store.close()
        return 0

    interval = args.interval or int(cfg["reddit"].get("poll_interval_sec", 300))

    if not args.loop:
        try:
            count = sweep(cfg, args, notifier, store)
        finally:
            store.close()
        return 0 if count >= 0 else 1

    print(f"{BANNER} started · polling every {interval}s · ctrl-c to stop")
    notifier.message("🟢 <b>job_finder</b> started — watching Reddit for new roles.")
    try:
        while True:
            try:
                sweep(cfg, args, notifier, store)
            except KeyboardInterrupt:
                raise
            except Exception:  # noqa: BLE001 - one bad sweep must not kill the watcher
                print("  [error] sweep failed:")
                traceback.print_exc()
            time.sleep(max(30, interval))
    except KeyboardInterrupt:
        print("\nstopped.")
        notifier.message("🔴 <b>job_finder</b> stopped.")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
