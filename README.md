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

## Windows quickstart (no terminal experience needed)

> **Windows gotchas up front:** there is no `python3` command on Windows (that's macOS/Linux —
> typing it opens the Microsoft Store, which is what the "Python was not found" message means).
> Use **`py`** or **`python`**. And this repo is private, so `git clone` without signing in will
> fail with *"Invalid username or token"* — download the ZIP instead.

**1. Install Python**

```powershell
winget install -e --id Python.Python.3.12
```

No `winget`? Get it from https://www.python.org/downloads/ and **tick "Add python.exe to PATH"**
on the first installer screen. Then **close every terminal window** and open a new one (PATH only
updates for new windows). Check it worked:

```powershell
py --version        # -> Python 3.12.x
```

**2. Get the code** (browser, no git needed — you're already signed in to GitHub):

Open https://github.com/Dsol3/Job-Finder → branch dropdown → select
`arena/7c5b793b-job-finder` → **Code ▾ → Download ZIP** → right-click the downloaded
file → **Extract All**. You get a folder `Job-Finder-arena-7c5b793b-job-finder`.

```powershell
cd "$env:USERPROFILE\Downloads\Job-Finder-arena-7c5b793b-job-finder"
```

*(Prefer git? `winget install --id GitHub.cli`, then `gh auth login` — choose "Login with a web
browser" — then `gh repo clone Dsol3/Job-Finder` and `git checkout arena/7c5b793b-job-finder`.)*

**3. Run setup — double-click `setup.bat` in that folder**, or from the terminal:

```powershell
.\setup.bat
```

It finds Python (ignoring the Store stub), creates `config.toml`, runs the Telegram wizard, then
runs `--doctor`. Paste the **new** bot token when asked, then tap START on `https://t.me/YourBot`
when it tells you to.

**4. Start watching — double-click `run-watcher.bat`.** Leave the window open (minimise it).

**Keep it running at logon** (Task Scheduler): Create Task → *Run only when user is logged on* →
Trigger *At log on* → Action *Start a program* → Program: `C:\path	o
un-watcher.bat` →
tick *Start in* and set it to the same folder. Or, simpler, drop a shortcut to `run-watcher.bat`
into `shell:startup` (Win+R → `shell:startup`).

Troubleshooting the Windows path:

| Message | Fix |
|---|---|
| `Python was not found; run without arguments to install...` | You typed `python3`. Install Python (step 1), use `py`. |
| `'python' is not recognized` | PATH not set, or you didn't open a **new** window after installing. |
| `Invalid username or token` on clone | Repo is private. Use the ZIP (step 2) or `gh auth login` first. |
| `setup.bat` flashes and closes instantly | Right-click → *Edit* to check the path, or run it from a terminal to see the error. |
| Unicode/`UnicodeEncodeError` when redirecting output | Already handled (`PYTHONIOENCODING` is set by the .bat), otherwise `set PYTHONIOENCODING=utf-8`. |

## Quickstart (5 minutes)

```bash
git clone <this repo> && cd Job-Finder
cp config.example.toml config.toml     # edit the subreddit + keyword lists if you like
python3 -m unittest discover -s tests  # 52 offline tests, no network
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

## Run it off your PC (always-on)

A sleeping laptop misses every post in its window, and on these boards the first hour decides
everything. Three ways to keep it running, cheapest first.

### Option A — GitHub Actions · free, no server, no card  ← recommended starter

GitHub's own servers run the sweep for you. Your laptop can be off. No card, no maintenance.
This repo is **public**, so Actions minutes are unlimited.

**1. Merge this branch into `main`** — scheduled workflows only fire from the default branch.
Open the Pull Request on GitHub and click *Merge*.

**2. Add the two secrets** — repo → **Settings → Secrets and variables → Actions → New repository
secret**:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | the token from @BotFather |
| `TELEGRAM_CHAT_ID` | from `.env` in your Job-Finder folder |

**3. Test it once** — **Actions** tab → **watch** (left sidebar) → **Run workflow ▾** → *Run
workflow*. A green run within ~30s means it's live. If the run is red, open it — the failing step
says exactly what's wrong (the usual one is a missing secret).

**4. Walk away.** It now runs every 5 minutes, forever, whether your PC is on or not.

**What the schedule actually feels like:** GitHub's cron is best-effort and runs late — asking
for `*/5` typically fires every 10–20 minutes. That's why the workflow asks for 5 and not 15: you
asked for 10–15 minutes of latency, and this lands there.

**State between runs:** `state/` (the dedupe database and alert log) is cached by
`actions/cache`, so you don't get duplicates. `config.ci.toml` limits it to posts from the last
2 hours, so even if a cache is evicted you can't be blasted with old listings.

**Two things to know:**

- GitHub disables schedules on repos with no commits for 60 days. The `keepalive` job makes a
  tiny monthly commit so that never happens.
- Public repo, so the workflow logs are public. Your token is a repository *secret* — GitHub
  masks it in logs and never exposes it to forks. Your `config.toml` and `.env` are git-ignored.
  The one thing visible is which jobs matched (titles in the run summary) — if that bothers you,
  delete the "Show what was sent" step.

**Changing keywords later:** edit `config.ci.toml` (not `config.toml` — the runner uses the CI
one), commit, done. No restart needed.

**Cost check:** public repos → free, unlimited. You'll see ~288 runs/day in the Actions tab; that
is expected and free.

### Option B — a $4–5/month VPS · most reliable

Hetzner CX22 (~€3.79), DigitalOcean (~$4), Vultr, or Lightsail. Pick **Ubuntu 24.04** and the
smallest size; the watcher uses ~30 MB of RAM.

```bash
ssh root@YOUR_IP
apt-get update && apt-get install -y git
git clone -b arena/7c5b793b-job-finder https://github.com/Dsol3/Job-Finder.git
cd Job-Finder
sudo bash deploy/install.sh
```

`install.sh` installs Python if needed, writes `config.toml`, stores your Telegram credentials
in `/etc/jobfinder.env` (chmod 600), verifies the bot with a live API call, installs a hardened
`systemd` unit, enables it at boot, and runs the first sweep. Re-running it is safe.

```bash
systemctl status jobfinder --no-pager   # is it alive
journalctl -u jobfinder -f              # live log
sudo systemctl restart jobfinder        # after editing config.toml
```

Non-interactive (cloud-init, Ansible, Oracle):

```bash
sudo TELEGRAM_BOT_TOKEN=123:ABC TELEGRAM_CHAT_ID=456 bash deploy/install.sh
```

### Option C — Oracle Cloud Always Free · $0, some patience

Oracle's **Always Free** tier includes an ARM Ampere VM (up to 4 cores / 24 GB) that never
expires. It's the cheapest truly-always-on option, but signup requires a card for verification
(not charged) and ARM capacity in busy regions can take a few tries.

1. Create an **Always Free** Ampere A1 instance, image **Ubuntu 24.04** (ARM64 is fine).
2. In the security list, allow outbound (default) — no inbound port needed; it only talks out.
3. Then the same three commands as Option B.

Watch for Oracle reclaiming *idle* Always Free instances — a small always-on service like this
one is exactly what keeps it classified as active.

### Option D — Docker, anywhere

```bash
cp .env.example .env   # TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...
docker compose up -d   # state persists in the jobfinder-data volume
docker compose logs -f
```

Works on a NAS, a home server, Railway, or any VPS with Docker.

### Option E — an old Android phone · $0

Install **Termux** (from F-Droid, not the Play Store), then:

```bash
pkg install python git -y
git clone -b arena/7c5b793b-job-finder https://github.com/Dsol3/Job-Finder.git
cd Job-Finder
python -m job_finder --setup-telegram
termux-wake-lock     # keeps Android from killing it
python -m job_finder --loop --quiet
```

Leave it charging with Wi-Fi on. Ugly, but it's free and it's already in your drawer.

### Which should you pick?

| | Cost | Speed | Effort | Reliability |
|---|---|---|---|---|
| GitHub Actions | free | 10–20 min | 5 min setup | good |
| $4 VPS | ~$4–5/mo | every 5 min, on time | 10 min setup | best |
| Oracle Always Free | $0 | every 5 min, on time | 20–40 min setup | good |
| Old phone | $0 | every 5 min, on time | 10 min setup | depends on the phone |

If you're serious about this for a few months, the $4 VPS pays for itself the first time you
reply to a post before anyone else. Start with GitHub Actions if you want to test the waters
for free.

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

## Throttling, and why most boards used to go silent

Reddit refuses unauthenticated requests hard: `403` first, then `429` once you keep knocking.
The original implementation asked each board separately and tried three endpoints per board, so
an 8-board watchlist could fire up to 24 requests in a few seconds — and the boards at the end of
the list returned nothing at all. Symptom in the log:

```
fetched r/forhire: 0 new posts      <- actually "403, 403, 429"
fetched r/NewTubers: 0 new posts
```

Two changes fix it:

1. **One request per batch.** Reddit serves a combined listing at
   `/r/HireaWriter+forhire+CreatorServices/new.json`, so all eight boards arrive in a single
   call. Eight requests become one, which is far below the limit instead of far above it.
2. **Exponential backoff with jitter.** On 403/429/5xx it waits 15s → 30s → 60s (capped at 90s,
   randomised) before trying the next endpoint, rather than retrying instantly.

Every sweep now ends with a coverage line, so silence is never ambiguous:

```
  batch 1/1: 87 posts · nothing new in: PartneredYoutube
  87 posts from 7/8 boards · silent: PartneredYoutube
  4 matched filters · 2 unseen
```

- `8/8 boards` + `0 matched` → genuinely nothing in your window matched. Normal.
- `silent: X` → that board was throttled or empty. `--doctor` reports boards silent for 12h+ and
  remembers the last successful read per board in `state/fetch_health.json`.

**Still throttled?** Raise `request_delay_sec`, lower `limit`, shorten the watchlist, or run less
often. GitHub's runner IPs are throttled harder than a home connection — that's the trade-off of
the free option.

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
| `python3 -m job_finder --demo` | push one sample alert card so you can see the format (writes nothing) |
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
tests/          52 offline tests (fixtures + a local HTTP server for the fetch path)
deploy/         install.sh (Ubuntu/Debian one-shot) + systemd unit
Dockerfile      container image for Railway/Fly/NAS/any VPS
docker-compose.yml
.github/workflows/watch.yml   free serverless option (GitHub Actions)
setup.bat       Windows one-click setup (finds Python, wizard, doctor)
run-watcher.bat Windows one-click watcher (leave window open)
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `every endpoint failed -> HTTP 403` | Reddit is blocking your IP. The RSS fallback usually still works. If all three fail, try from another network, or run it on a home connection. |
| `HTTP 429` | Rate limited. Raise `request_delay_sec` to 5, drop `limit` to 50, fewer subreddits. |
| `silent: forhire` in the summary | That board was throttled this sweep. It retries automatically; if it stays silent for 12h+, `--doctor` flags it. |
| `config file not found: …` | `--config` is strict now — the path you gave must exist. Run `git pull`, or drop the flag to use `config.toml`. |
| `is not valid TOML` | The message names the line and the likely cause (usually a `[section]` pasted twice). Fix it or `copy config.example.toml config.toml`. |
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
