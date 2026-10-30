# SEO practice plan — ekis.store

A 90-day plan for learning SEO by fixing your own store. The store earns money, so this doubles as
a portfolio case study with real numbers attached.

**Why your own site is the right place to practise:** you can see Search Console without asking
permission, you can break things and roll back, and — most importantly — you cannot fool yourself
about whether it worked. Orders either move or they don't.

---

## Ground rules

1. **Never experiment on production.** Vercel gives you a preview deploy per branch; do URL, schema
   and copy changes there first, then promote.
2. **One change per week**, so a result can be attributed to something.
3. **Every URL change ships with a 301 in the same deploy.** Keep an old→new log in this file
   (see [Redirect log](#redirect-log)).
4. **No `noindex` "just to test".** One forgotten tag can wipe months of indexing.
5. **Don't delete thin pages yet.** Improve or consolidate, and only redirect once the replacement
   is live and indexed.

---

## Step 1 — Baseline (do this before touching anything)

Without "before", you have opinions, not a case study. Fill this in today and screenshot each one.

### Search Console — Performance

| Metric | Last 3 months | Last 28 days | Notes |
|---|---|---|---|
| Impressions | | | |
| Clicks | | | |
| Average CTR | | | |
| Average position | | | |
| Pages indexed / discovered-not-indexed | | | Pages report |

Top 10 queries by impressions (paste the table):

| Query | Impressions | Clicks | Position |
|---|---|---|---|
| | | | |

### Store performance

| Metric | Last 30 days | Notes |
|---|---|---|
| Orders | | |
| Revenue | | |
| Conversion rate | | |
| Traffic source: organic | | |
| Top 3 products by revenue | | |

### Screenshots to save

- GSC performance graph, 3-month view, dated
- GSC Pages report (indexed vs not indexed)
- Each product page as it looks today

---

## Step 2 — Keyword map (10 buyer-intent + 20 free-tool queries)

One query per page. If two pages target the same query, you've built a competitor to yourself.

### Buyer intent (map to playbooks and kits)

| Query | Intent | Page | Status |
|---|---|---|---|
| youtube strategy playbook | commercial | `/playbooks/youtube-strategy-playbook` | exists |
| ai video creator playbook | commercial | `/playbooks/ai-video-creator-playbook` | exists |
| learn ai video editing beginners | commercial | `/playbooks/ai-video-creator-playbook` | exists |
| chatgpt for beginners over 50 | commercial | `/playbooks/ai-for-busy-adults` | exists |
| social media content planner template | commercial | `/digital/kits/social-content-system` | exists |
| creator income tracker | commercial | `/digital/kits/creator-income-monetization-kit` | exists |
| ai prompt library for work | commercial | `/digital/kits/ai-prompt-workflow-kit` | exists |
| how to plan youtube content | informational → playbook | new resource article | **missing** |
| youtube retention tips beginners | informational → playbook | new resource article | **missing** |
| how much do ai video editors charge | informational → playbook | new resource article | **missing** |

### Free-tool queries (your best ranking opportunity)

These are the highest-intent, lowest-competition words you own — a free tool page can rank where a
product page can't.

| Query | Page | Status |
|---|---|---|
| free social media content planner | `/digital/templates/social-content-planner` | exists, thin copy |
| free creator income tracker spreadsheet | `/digital/templates/creator-income-tracker` | exists, thin copy |
| free 30-day learning plan template | `/digital/templates/ai-learning-planner` | exists, thin copy |
| free small business sales tracker | `/digital/templates/small-business-sales-tracker` | exists, thin copy |
| free habit tracker pdf | `/digital/templates/digital-skills-habit-tracker` | exists, thin copy |
| printable content calendar template | — | **missing** |
| youtube content calendar template | — | **missing** |
| ai prompt template for email writing | — | **missing** |
| small business bookkeeping spreadsheet free | — | **missing** |
| digital skills checklist | — | **missing** |

> Fill in four more from Search Console: filter to *Queries*, sort by impressions, and look at
> positions 8–25. Those are pages Google already thinks are relevant — the cheapest wins available.

---

## Step 3 — Findings so far

From a rendered read of the live site on 2026-10-30 (text, robots.txt and sitemap only — **not**
Search Console, meta tags, schema or speed). Verify each before acting.

| # | Finding | Fix | Verify with |
|---|---|---|---|
| 1 | Homepage has no products, prices or links to individual items; H1 targets no query | Give the homepage one searchable job and surface the 3 playbooks + 5 free tools | GSC: has the homepage ever ranked for a commercial query? |
| 2 | `/digital` shows "0kits · 0playbooks" on two needs cards | Hide zero counts, or merge/fill those needs | Screenshot before/after |
| 3 | No resource articles supporting two of three playbooks (7 articles total across 3 products) | 6–10 supporting articles per playbook | New URLs in GSC Pages report |
| 4 | Free-tool pages are download pages, not answers | 300–500 words of searchable copy + FAQ per tool | Position on the free-tool queries |
| 5 | `/digital/kits`, `/digital/templates`, `/digital/playbooks` overlap | Differentiate by intent, not by grid | Impressions per hub page |
| 6 | Mixed URL conventions (`/digital/kits/x` vs `/playbooks/x`) | Pick one, 301 the rest — only after logging them | Redirect log below |
| 7 | Sitemap uses `priority`/`changefreq` (ignored) and one shared `lastmod` for all URLs | Strip priority/changefreq; emit real per-page lastmod | Screaming Frog / this tool |

### Run the audit yourself

```bash
py -m job_finder --config config.seo.toml --site --site-report audit-$(date +%F).md
```

`[practice].site` is set to `https://www.ekis.store`, so `--site` with no argument audits the store.
It follows robots.txt → sitemap → every page and reports:

- missing / short / **duplicate titles and descriptions**
- H1 missing or multiplied
- accidental `noindex`
- thin pages (under 300 words)
- canonical mismatches
- product pages with **no structured data**
- sitemaps that lie about `lastmod`, and `priority`/`changefreq` tags

Keep each week's report in the repo (or a folder) — that dated sequence *is* the case study evidence.

---

## Step 4 — The 30-day plan

| Week | Skill | Do | Proof to capture |
|---|---|---|---|
| 1 | Technical baseline | GSC + Bing Webmaster connected; fix sitemap tags; check every URL's index status; fix the "0kits" bug | "discovered-not-indexed: N → 4" screenshot |
| 2 | Keyword mapping | Fill in Step 2 completely. Nothing unassigned | The filled table |
| 3 | On-page | Rewrite homepage, 3 playbooks, 5 free-tool pages: one intent each, FAQ block, descriptive internal links | Position on 10 target queries, before/after |
| 4 | Schema + speed | Product/Offer on 3 playbooks + 3 kits, FAQPage, BreadcrumbList; fix mobile Core Web Vitals | Rich Results Test pass; PSI mobile score |

**Month 2 — content.** Two articles a week, each answering one question from a playbook module.
Internal-link every article to its playbook with a descriptive anchor.

**Month 3 — links.** Digital PR around the free tools: outreach to newsletters and communities that
would genuinely use a free content planner. No buying, no guest-post packages, ever.

---

## Step 5 — Turn it into a portfolio case study

Publish at `/resources/case-study-ekis` (or `/work`). On your own domain: content practice plus a
permanent asset you can link from Reddit replies.

```markdown
# How I grew organic traffic on my own store by X% in 90 days

## Starting point
Dated screenshot. Real numbers: impressions, clicks, indexed pages, orders from organic.

## What was broken
Three specific findings — the ones in Step 3 of this plan are a good start.
Name the mechanism, not just the symptom: "40 service pages were discovered but
not indexed because the sitemap listed URLs that 404'd".

## What I changed and why
One short paragraph per fix. Reasoning matters more than the action.

## What happened
Impressions, clicks, clicks per article, orders attributed to organic. Charts.

## What didn't work
One honest paragraph. This is the section that makes the rest believable,
and almost nobody includes it.

## What I'd do next
The next three moves.
```

**Framing rule:** say "my own store", never "client results". On a call, own it directly — *"This is
my store, I run it. Here's exactly what I'd do first on yours."* That's more persuasive than borrowed
case studies, and it can't be caught out later.

### Then client proof

Take **2 free projects** (a dentist, a Shopify store, someone from r/smallbusiness with a real
traffic loss). Free once, in exchange for GSC access and a written testimonial. Those become case
studies #2 and #3 — and *then* you raise your rate.

---

## Weekly rhythm

| Day | 90 minutes |
|---|---|
| Mon | Study one topic, then apply it to the store that same week |
| Tue–Thu | 30 min/day reading *problems* in r/SEO and r/smallbusiness — that's diagnosis practice |
| Fri | Ship one fix or one audit |
| Weekend | Answer 3 questions in the subs where your leads live (practice + pipeline) |

---

## Redirect log

Every URL change, dated. If traffic dips, this is the first place you look.

| Date | From | To | Reason | Status code |
|---|---|---|---|---|
| | | | | |

---

## Reading, in order

1. Google Search Central — *SEO Starter Guide* (the primary source; everything else interprets it)
2. Ahrefs YouTube — Sam Oh's beginner playlist (watch, then do it on the store)
3. learningseo.io — the roadmap, to see what you don't know yet
4. Search Off the Record — Google's own podcast, for how they reason
5. r/TechSEO and r/bigseo — real debugging, once the basics land
