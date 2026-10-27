# Job Finder — Reddit watcher for content writing & YouTube strategy roles

Watches the subreddits where content and YouTube work actually gets posted, filters out
the noise (for-hire posts, rev-share, unpaid "exposure", AI-slop mills, below-floor rates),
and pings your phone with the few posts worth replying to in the first 30 minutes.

No API key. No Reddit account. No dependencies — Python 3.11+ standard library only.

```
$ python3 -m job_finder --once

[14:02:11] checking 8 subreddits: HireaWriter, forhire, writersforhire, ...
  fetched r/HireaWriter: 100 new posts
  fetched r/forhire: 100 new posts
  6 matched filters · 2 unseen

------------------------------------------------------------------------
[10/10] r/forhire · 18m ago · u/HistoryChannelOps
[Hiring] YouTube Channel Strategist for faceless history channel ($1,200/month retainer)
Budget: $1,200/month
Flair: Hiring
Why: matched: channel strateg, youtube | budget: $1,200/month
6 comments · https://www.reddit.com/r/forhire/comments/...
------------------------------------------------------------------------
```

## Why this exists

On Reddit the first 5 replies get read. A good `[Hiring]` post collects 40–100 replies in a
day and the shortlist is built before you wake up. Manually refreshing `/new` doesn't scale,
so this does the refreshing and the triage, and you do the writing.

## Quickstart (5 minutes)

```bash
git clone <this repo> && cd Job-Finder
cp config.example.toml config.toml     # edit the subreddit + keyword lists if you like
python3 -m unittest discover -s tests  # 32 offline tests, no network
python3 -m job_finder --fixture tests/fixtures/forhire_new.json --dry-run   # see it work offline
python3 -m job_finder --once           # first real run
```

**The first run is a baseline.** It records everything currently on the boards as "seen" so
you don't get 200 alerts at once. You'll start getting pings from the next new post onward.
(Set `bootstrap = false` under `[storage]` if you'd rather see the current backlog.)

## Telegram setup (2 minutes)

```bash
python3 -m job_finder --setup-telegram
```

It walks you through three steps and finds your chat id for you:

```
── Telegram setup ──────────────────────────────────────────────
1/3  Get a bot token
     • Open Telegram → @BotFather → send /newbot
     • Pick a name, then a username ending in 'bot'
     • It replies with a token like 8123456789:AAH-xxxxxxxxxxxxxxxxxxxxx

     Paste token (or press Enter to abort): 8123456789:AAH-…
✓ Connected to @YourJobsBot (token …x9f2)

2/3  Find your chat id
     Open https://t.me/YourJobsBot and tap START (or send it any message).
     Waiting for your message…
✓ Found chat: Tunde (5150233841)
✓ Chat verified: Tunde
✓ Test message sent — check Telegram.

Saved to .env (permissions 600). Secrets stay out of git.
Next: python3 -m job_finder --doctor   then   python3 -m job_finder --once
```

Then prove everything works end to end:

```
$ python3 -m job_finder --doctor
── doctor ──────────────────────────────────────────────────────
  ✓  8 subreddits configured: HireaWriter, forhire, writersforhire, …
  ✓  include rules: 20 · exclude rules: 30 · floors: 0.05/word
  ✓  0 posts remembered in seen.sqlite3
  ✓  bot token valid (@YourJobsBot, …x9f2)
  ✓  chat reachable: Tunde (5150233841)
  ✓  reddit reachable — r/HireaWriter returned 5 posts

All good. Run: python3 -m job_finder --once
```

### If you'd rather do it by hand

1. @BotFather → `/newbot` → copy the token.
2. **Message your bot anything** (bots cannot DM you first).
3. `https://api.telegram.org/bot<TOKEN>/getUpdates` → copy the `id` inside `"chat":{"id":123456789,...}`.
4. `export TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...` or put both in `.env`.

Notes:

- Credentials live in **`.env`** (chmod 600, git-ignored) or in real environment variables,
  which take precedence. `config.toml` stays safe to share.
- `notify.channel = "auto"` means: push to Telegram once credentials exist, otherwise print
  to the console. Set it to `"console"` to force terminal-only.
- Non-interactive setup for a server: `--setup-telegram --token 123:ABC --chat-id 987654321`.
- Want a group instead of a DM? Add the bot to the group, send a message there, and the wizard
  will list it as an option.

## Running it 24/7

**Simplest — cron every 5 minutes** (each run is a short-lived process):

```cron
*/5 * * * * cd /home/you/Job-Finder && TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... /usr/bin/python3 -m job_finder --once --quiet >> jobfinder.log 2>&1
```

**Long-lived — systemd** (see `deploy/jobfinder.service`):

```bash
sudo cp deploy/jobfinder.service /etc/systemd/system/
sudo systemctl enable --now jobfinder        # edit paths + secrets first
journalctl -u jobfinder -f
```

**Cheapest host:** any $0 tier VPS, a Raspberry Pi, or a spare laptop. Memory use is a few MB.
Datacenter IPs sometimes get 403s from Reddit; the watcher falls back to `old.reddit.com`
then to the Atom feed automatically, and a home connection is never a problem.

## How it decides what to show you

Every candidate post goes through four steps (`job_finder/filters.py`):

| Step | What happens |
|---|---|
| **Age gate** | anything older than `max_age_hours` (default 36) is ignored — you can't win a 3-day-old post |
| **Exclusions** | `[For Hire]` posts, rev-share, equity-only, unpaid/internship, "free sample", commission-only, AI-rewrite mills, crypto/casino/adult |
| **Include match** | must contain at least one of your role phrases — `content writ`, `youtube strateg`, `channel manag`, `scriptwrit`, `seo content`, `newsletter`, … |
| **Rate floor** | if the post states a rate and *every* stated rate is below your floor ($0.05/word, $15/hr, $50/article, $50/video) it's dropped as a lowball |

Survivors get a **0–10 score** used only for ordering alerts:

```
+2  your priority role is in the TITLE      ("youtube strateg", "channel strateg", …)
+2  any include term in the title
+2  they named a number (they have a budget)
+1  [Hiring] in title or flair
+1  urgent / asap / immediately
+2  posted < 2h ago   (+1 if < 6h)
+2  boost language (retainer, retention, packaging, long-term, monthly, audit …)
-1  already 25+ comments (crowded)
-2  empty body (usually a one-liner or a scam)
```

Budget parsing understands `$0.12/word`, `15 cents per word`, `$1,200/month`,
`$150 per video`, `$50–$80 per article`, and `5,000 words for $25` (normalised to per-word).

## Tuning it to your actual pitch

All in `config.toml`. The two lists that matter:

- **`matching.include`** — add the exact phrases clients in your niche use. Watch what the
  watcher misses for a week and add those words. Prefix with `re:` for a regex.
- **`matching.exclude`** — add anything that keeps showing up and annoys you. Exclusions beat
  every other rule, and they're checked against the whole post, so be specific ("entry level"
  is fine; bare "entry" would nuke legitimate posts).

Common adjustments:

```toml
# Only want strategy, not general writing?
include = ["youtube strateg", "channel strateg", "content strateg", "audience growth"]

# Done with $0.05 words entirely — raise the floor
[floors]
per_word = 0.10

# Watch more boards
[reddit]
subreddits = ["HireaWriter", "forhire", "CreatorServices", "PartneredYoutube", "NewTubers"]
```

## Commands

| Command | What it does |
|---|---|
| `python3 -m job_finder --once` | single sweep, alert on new matches (cron-friendly) |
| `python3 -m job_finder --loop --interval 300` | poll forever in one process |
| `python3 -m job_finder --dry-run` | print matches, send/persist nothing |
| `python3 -m job_finder --fixture tests/fixtures/forhire_new.json` | replay saved posts offline |
| `python3 -m job_finder --subreddits HireaWriter,forhire` | override boards for one run |
| `python3 -m job_finder --setup-telegram` | interactive wizard: token → chat id → test message → `.env` |
| `python3 -m job_finder --doctor` | check config, Reddit reachability and Telegram in one pass |
| `python3 -m job_finder --test-telegram` | just re-send a test message |
| `python3 -m job_finder --stats` | how many posts are in the dedupe store |
| `python3 -m job_finder --prune 90` | drop seen-post history older than 90 days |

## Layout

```
job_finder/
  reddit.py     fetch new posts (JSON -> old.reddit -> Atom fallback), dataclasses
  filters.py    budget parsing, include/exclude rules, 0-10 scoring
  store.py      SQLite dedupe so you never see the same post twice
  notify.py     Telegram HTML cards + console output + matches.jsonl log
  telegram.py   setup wizard, chat discovery, .env handling, --doctor
  config.py     TOML loading with defaults, env-var secrets
  cli.py        argument parsing, sweep loop, baseline run
tests/          32 offline tests (fixtures + a local HTTP server for the fetch path)
deploy/         systemd unit
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `every endpoint failed -> HTTP 403` | Reddit is blocking your IP. The RSS fallback usually still works. If all three fail, try from another network, or run it on a home connection. |
| `HTTP 429` | Rate limited. Raise `request_delay_sec` to 5, drop `limit` to 50, fewer subreddits. |
| No alerts at all | Run `--dry-run` first. If it prints "0 matched filters", your `include` list doesn't match the wording clients actually use — loosen it. |
| Huge flood of alerts | Tighten `include`, raise `per_word` floor, or drop the broad `youtube` term. |
| Telegram says 400/403 | Wrong chat id (must be your numeric id, not `@username`), or you never messaged the bot first. |
| Duplicate alerts after moving machines | Copy `seen.sqlite3` with the project, or accept one re-run of the backlog. |

## Using it well

The tool gets you there first; the reply is still yours. What converts on Reddit:

- **Comment publicly with proof, then DM.** "DM'd" is invisible. A 3-line public comment with
  one relevant sample makes the DM get opened.
- **Lead with a specific observation about their channel/post**, then 2 links, then logistics
  (timezone, turnaround, payment method).
- **Offer a small free audit** — 3 retention/packaging notes on their last 5 videos. It is the
  single highest-converting opener on these boards.
- **Repost a `[For Hire]` once a week** in `r/forhire` and `r/HireaWriter` with a different
  angle each time; retainers come from inbound, not from replies.
- **50% upfront** on first projects. Agree payment rails (Wise/Payoneer/Deel) before you
  deliver anything, in writing.

## Notes

- Public feeds only, the same ones a logged-out browser sees. No login, no scraping behind auth,
  no voting/commenting automation.
- One request per subreddit per sweep with a 2s pause — well under Reddit's documented limits.
  Please don't lower the delay to hammer them.
- Rate floors are *your* policy, not Reddit's; `r/HireaWriter` enforces its own (5c/word entry,
  10c general, 15c+ advanced).
