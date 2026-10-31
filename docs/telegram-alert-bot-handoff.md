# Build your own Telegram alert bot — handoff notes

For anyone who saw this work and wants the same thing: a bot that watches a source (Reddit,
a website, an RSS feed, an API, a spreadsheet) and pings your phone within minutes when something
matches. **Everything below is free.** No server needed to start.

This is a write-up of the design decisions and the traps in
[this repo](../README.md), which is a working reference implementation in ~900 lines of Python with
no third-party dependencies.

---

## The short version

Three parts, in this order:

1. **A Telegram bot** — 2 minutes, free, no approval process
2. **A poller** — anything that can make an HTTP request on a timer
3. **A memory** — so you don't get the same alert twice

That's it. The hard parts are not the code; they're the six traps in
[Things that will bite you](#things-that-will-bite-you).

---

## Part 1 — Create the bot (2 minutes)

1. In Telegram, message **@BotFather** → send `/newbot`
2. Give it a name, then a username ending in `bot` (e.g. `MyJobsBot`)
3. It replies with a token: `8123456789:AAH-xxxxxxxxxxxxxxxxxxxxxxxx`
4. **Open `https://t.me/YourBotName` and press START.** This is the step everyone misses — a bot
   cannot message a chat that hasn't messaged it first.
5. Get your chat id:

```bash
curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
```

Look for `"chat":{"id":5150233841,...}` — that number is your chat id.

6. Test it:

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d chat_id=5150233841 \
  -d parse_mode=HTML \
  -d text="<b>It works.</b> This is what an alert will look like."
```

If a message appears on your phone, the hard part is done.

> **Security:** the token is a password. Anyone holding it controls the bot. Keep it in an
> environment variable or a `.env` file that is git-ignored — never in code, never in a screenshot.
> If it leaks, revoke it: `/mybots` → your bot → **API Token → Revoke**.

---

## Part 2 — A 40-line sender (Python, no dependencies)

```python
import json, urllib.parse, urllib.request

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send(text: str, html: bool = True) -> bool:
    payload = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML" if html else "",
        "disable_web_page_preview": "false",
    }).encode()
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        with urllib.request.urlopen(url, data=payload, timeout=20) as resp:
            return json.loads(resp.read()).get("ok", False)
    except Exception as exc:            # never let a failed alert kill the job
        print("send failed:", exc)
        return False
```

That function is the whole integration. Everything else is scheduling and filtering.

### Make the card readable

A wall of text gets ignored. What works, per alert:

```html
🔥 <b>9/10</b> · r/HireaWriter · 12m ago
<a href="https://reddit.com/...">B2B SaaS content writer — $0.12/word, ongoing</a>
💰 <b>$0.12/word</b>
<i>matched: content writ | budget: $0.12/word</i>
2 comments · u/lena_b2b
```

Four things, always: **a score** (so you can triage at a glance), **the title as a link**,
**the one fact that decides** (price, distance, deadline, stock), and **age** (freshness is the whole
point of an alert).

Allowed HTML tags: `b`, `i`, `u`, `s`, `code`, `pre`, `a`. Anything else is rejected with a 400.

---

## Part 3 — Scheduling

Pick by reliability, not by cleverness:

| Where | Setup | Reality |
|---|---|---|
| **GitHub Actions cron** | 10 min, free for public repos | Free forever, but cron is best-effort: `*/5` typically fires every 10–20 min. Needs the repo public (private repos drain the 2,000 free minutes fast). |
| **Any $4 VPS + systemd** | 15 min | Most reliable, checks every minute if you like, ~30 MB RAM |
| **Old Android phone + Termux** | 10 min | Free, survives on a charger, mobile IPs are rarely blocked |
| **Your laptop** | 2 min | Fine to test; useless overnight. A sleeping machine misses the window. |

**Deliberate trick if you use GitHub Actions:** ask for a *more frequent* schedule than you need.
`*/5` lands at 10–20 minutes; `*/15` lands at 25–35. You are compensating for known lateness.

Also required on GitHub Actions:

- Scheduled workflows **only run from the default branch**
- Schedules get **disabled after 60 days without a commit** — a monthly no-op commit prevents that
- `concurrency: group: <name>, cancel-in-progress: false`, or overlapping runs will double-alert

---

## Part 4 — Memory (don't alert twice)

Store the ids of everything you've already seen. SQLite is ideal:

```sql
CREATE TABLE IF NOT EXISTS seen (
    id TEXT PRIMARY KEY,
    first_seen REAL
);
```

```python
def is_new(conn, item_id) -> bool:
    return conn.execute("SELECT 1 FROM seen WHERE id = ?", (item_id,)).fetchone() is None
```

**On a disposable runner** (GitHub Actions), `state/` must survive between runs:
`actions/cache/restore` at the start, `actions/cache/save` at the end, with
`key: seen-${{ github.run_id }}` and `restore-keys: seen-`. Never commit the database.

**The baseline rule:** on the very first run, record everything currently visible as "seen" and send
nothing. Otherwise your first sweep fires 200 alerts and you mute the bot on day one. Every
implementation in this repo does that with a `bootstrap` flag.

---

## Part 5 — The part that makes it useful: filtering

An alert feed is only as good as what it throws away. Of 100 posts on a job board, roughly 80 are
noise. Filter in this order, cheapest first:

1. **Age gate** — ignore anything older than N hours. An alert on a 3-day-old post is trivia.
2. **Hard exclusions** — words that mean "not for me" (`unpaid`, `for hire`, `revenue share`,
   `already sold`, `out of stock`). Case-insensitive substring matching is fine; regex for word
   boundaries (`\bintern\b` not `intern`, or you'll nuke "international").
3. **Include match** — must contain at least one of your phrases, matched against *title + body +
   tags*, not just the title.
4. **A score** for ordering, not filtering — freshness, keyword in the title, a price being stated,
   comment count (crowded = too late), urgency words.

Example of what scoring buys you: the same feed sorted by score put a $1,200/month strategy role at
9/10 and a $200 video-editing gig at 6/10, with no extra rules — the "budget stated + right role in
the title" signals did the work.

### Parse the money, don't just regex for `$`

Rates arrive as `$0.12/word`, `15 cents per word`, `$150 per video`, `$1,200/month`,
`5,000 words for $25`. Normalise everything to one unit before comparing to a floor, or you'll drop
good work as "lowball" and keep bad work. The parser in
[`filters.py`](../job_finder/filters.py) handles these five shapes and converts bulk pricing to
per-word.

---

## Things that will bite you

Every one of these cost real debugging time on this project.

| # | Trap | What happens | Fix |
|---|---|---|---|
| 1 | **A bot can't message you first** | `sendMessage` returns `400: chat not found` | You must open `t.me/YourBot` and press START before the bot can DM you |
| 2 | **`getUpdates` conflict** | `409: Conflict: terminated by other getUpdates` | Two pollers on one token. Stop the other one (a `--loop` process and a cron job, typically) |
| 3 | **Rate limits** | `429: Too Many Requests` with `retry_after` | Read `retry_after` from the JSON body and sleep exactly that long; exponential backoff with jitter otherwise. Expect ~30 messages/second to one chat max |
| 4 | **HTML escaping** | `400: can't parse entities` | Escape user content: `html.escape(title)`. Titles with `<`, `&` or unbalanced `*` break the message |
| 5 | **Source throttling** | `403` then `429` from the site you scrape; some boards just go silent | Space requests (1–2 s), retry with backoff, and **detect silent sources explicitly** — a source that returns nothing after two consecutive sweeps is broken, not empty |
| 6 | **Silent fetcher fallback** | You pass a config path, it's missing, and defaults quietly apply — you're watching 2 sources instead of 8 and don't notice | A missing explicit config path must be a hard error |
| 7 | **Secrets in config** | Token lands in git history | Env vars / `.env` (git-ignored, chmod 600). `config.toml` should be safe to share |
| 8 | **Unreadable errors** | A TOML/config typo dumps a 20-line traceback | Catch it and print the file, line, and likely cause |
| 9 | **Alert fatigue** | 30 notifications a day, muted by day three | Score, don't just filter. Put the score and age in the card. One alert per item, ever |

### Also worth knowing

- **Long polling vs webhooks.** For a client-side bot, long polling (`getUpdates` with a timeout) is
  simpler and needs no public URL. Webhooks need HTTPS and a stable host.
- **Don't scrape logged-in pages.** Public feeds only. For Reddit specifically, `/r/<sub>/new.json`
  and `/new.rss` are public; a descriptive `User-Agent` materially reduces 403s.
- **Combine requests where the API allows it.** Reddit serves `/r/a+b+c/new.json`, so 8 boards can be
  one request instead of 8 × 3 endpoint attempts. That single change fixed the throttling on this
  project.
- **Idempotency.** If a run crashes halfway, the next run must not re-send what already went out.
  Mark as seen *after* a successful send, and keep the write cheap.

---

## Minimum viable build, in order

1. Copy the 40-line sender, hardcode your chat id, send "hello" — **prove delivery works**
2. Fetch your source, print the results to the terminal — no Telegram yet
3. Add SQLite dedupe, print only new items
4. Send those to Telegram, plain text
5. Add the first exclusion rule (the one thing that annoys you most)
6. Format the card (score, link, key fact, age)
7. Schedule it, then walk away for a week before adding anything else

Most people do this in one evening. The filtering gets good only after you've watched it for a week —
the first `exclude` list is always wrong.

---

## Reference implementation

This repo, all of it free to copy:

| File | What it does |
|---|---|
| [`telegram.py`](../job_finder/telegram.py) | Bot API calls, chat-id discovery wizard, `.env` handling, `--doctor` checks |
| [`notify.py`](../job_finder/notify.py) | Alert card rendering (plain text + Telegram HTML), retry on 429 |
| [`reddit.py`](../job_finder/reddit.py) | Three-tier fetch with fallback, multi-source batching, backoff |
| [`filters.py`](../job_finder/filters.py) | Rate parsing, include/exclude rules, 0–10 scoring |
| [`store.py`](../job_finder/store.py) | SQLite dedupe |
| [`.github/workflows/watch.yml`](../.github/workflows/watch.yml) | Free scheduling with cached state |

```bash
git clone https://github.com/Dsol3/Job-Finder.git
cd Job-Finder
python3 -m job_finder --setup-telegram     # wizard: token → chat id → test message
python3 -m job_finder --doctor             # verify everything
python3 -m job_finder --once               # first sweep
```

Python 3.11+, no `pip install`, ~900 lines.

---

## If you'd rather not build it

The same pattern applies to anything with a public feed or an API: new listings in a niche,
price drops, restocks, new papers on a topic, tender notices, local planning applications,
competitor page changes, GitHub releases, RSS feeds. The bot is 20 lines; the value is entirely in
what you choose to filter out.

Tell me the source you want watched and what "worth interrupting me for" means, and the rest is an
afternoon.
