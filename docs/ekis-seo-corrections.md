# ekis.store — full SEO correction list

Everything to fix, in the order that produces results. Based on reading the live site (rendered text,
robots.txt, sitemap, five product/tool pages) on 2026-10-30. **Not** verified: Search Console data,
raw meta tags, Core Web Vitals, or index status — check those first (Part 1, step 0).

Priority key: **P0** breaks something · **P1** costs rankings or sales today · **P2** compounding
gains · **P3** nice to have.

---

## Part 0 — Fix before optimising anything

### P0 · Your product pages contradict themselves

The YouTube Strategy Playbook says, at the top of the page:

> "The sample is available now. Sales will open when checkout is ready."

…then shows **$69 USD**, a "Read a free sample" button, and a section headed "One-time purchase".
The Social Content System page links to Gumroad but ends with:

> "Checkout and delivery will be handled through Gumroad once the product checkout URL is connected."

That reads as unfinished to a buyer, and a page that never converts stops earning the engagement
signals that support rankings. Pick one state and be consistent:

- **Live now** → remove every "checkout coming" line, make the buy button the primary action.
- **Not live yet** → remove the price and the buy button, keep the page as a "coming soon" with an
  email capture, and **remove it from the sitemap** (or set `availability: PreOrder` if the waitlist
  is genuinely a pre-order).

### P0 · Remove the visible empty-state copy

`/digital` shows **"0kits · 0playbooks"** on two need cards. `/digital/needs/small-business` prints:

> "No Digital Kit for this need yet" · "No playbook for this need yet"

Two pages in your sitemap currently tell Google and every visitor that the site is half-built.

- Hide counts when they're zero.
- For needs with nothing behind them, either add the product or **remove the page from the sitemap
  and 301 it to `/digital`** until it has content. A 200-word page saying "nothing here yet" is a
  thin-content liability.

---

## Part 1 — Technical foundation

### P1 · Sitemap hygiene

Your `sitemap.xml` has 30+ URLs, all with `priority` 0.8/0.9 and `changefreq` **weekly**, and —
critically — **every `<lastmod>` is identical** (`2026-10-14T20:13:58`). That's a build timestamp.
Google discounts it, so it can't tell which pages actually changed.

```xml
<url>
  <loc>https://www.ekis.store/playbooks/youtube-strategy-playbook</loc>
  <lastmod>2026-10-30</lastmod>   <!-- real content date, per page -->
</url>
```

Remove `priority` and `changefreq` entirely. Emit `lastmod` from each page's actual content date
(front-matter field or file mtime at build time). In Next.js this is a `lastModified` field in
`sitemap.ts`, not `new Date()`.

### P1 · Verify index coverage in Search Console

Open **Pages** and answer three questions before anything else:

1. How many URLs are **Indexed** vs **Not indexed**?
2. Under "Not indexed", what are the reasons — *Crawled – currently not indexed* (thin/duplicate) or
   *Discovered – currently not indexed* (crawl budget)?
3. Are any product pages excluded because of a canonical or `noindex`?

Screenshot it. That's your baseline (see `docs/seo-practice-plan.md` Step 1).

### P1 · Canonical and host consistency

- `https://www.ekis.store` vs `https://ekis.store` — pick **www** (it's what robots and sitemap use),
  and 301 the apex to it at the Vercel domain level.
- Confirm trailing-slash behaviour is one redirect, not a loop.
- Every page needs a self-referencing canonical. Verify none point at another page.

### P1 · Core Web Vitals on mobile

Product pages carry several `.jpg` preview images (page-1, page-2, page-3, page-7, page-12). Run
PageSpeed Insights on:
`/playbooks/youtube-strategy-playbook`, `/digital`, `/digital/kits/social-content-system`.

Then:

- Convert previews to **WebP/AVIF** (your hero is already `.webp`, so the pipeline exists — apply it
  to `/previews/**`).
- Serve preview thumbnails at display size, not 2000px originals.
- `loading="lazy"` on everything below the fold; the cover image can stay eager.
- Reserve width/height on every image to stop layout shift (CLS).

### P2 · Structured data (see Part 5 for snippets)

Currently the pages appear to carry no `Product`, `Offer`, `FAQPage` or `BreadcrumbList` markup.
You're a shop — this is the highest-value markup you can add.

### P2 · Breadcrumbs

Your URL hierarchy is three levels deep but nothing on-page reflects it. Add visible breadcrumbs
(`Digital › Kits › Social Content System`) plus `BreadcrumbList` schema. It improves internal
linking, gives Google a cleaner hierarchy, and replaces the raw URL in search results.

### P2 · URL consistency

You mix three patterns:

```
/playbooks/youtube-strategy-playbook
/digital/kits/social-content-system
/digital/templates/social-content-planner
/digital/needs/content-planning
```

That's survivable. What matters is that **each product has exactly one URL**. Decide now, log every
change in the redirect table in `docs/seo-practice-plan.md`, and 301 in the same deploy. Don't
restructure until you have traffic worth protecting.

### P3 · Misc

- `robots.txt` is fine (`Allow: /` + sitemap). Keep it.
- Add an XML sitemap index if you exceed ~50 URLs (`/sitemap-pages.xml`, `/sitemap-products.xml`).
- Fix any 404s that get internal links; check the Pages report for *Soft 404*.

---

## Part 2 — Titles, meta descriptions, H1s

Right now most titles are `Page name · EKIS`, which targets nothing anyone types. Each title should
contain the query, and each page should have exactly one H1 that says what the page is.

| Page | Current title | Replace with | Meta description (155 chars) |
|---|---|---|---|
| `/` | Practical tools for learning, creating, and building online · EKIS | **Digital Playbooks & Templates for Creators and Small Businesses \| EKIS** | Ready-to-use playbooks, planners and templates for YouTube strategy, AI video and small business admin. Free tools to start, kits when you're ready. |
| `/playbooks/youtube-strategy-playbook` | YouTube Strategy Playbook · EKIS | **YouTube Strategy Playbook — Topics, Titles, Thumbnails & Retention** | A 6-module YouTube strategy playbook: find real demand, package titles and thumbnails, read retention graphs, and run 5-video tests. $69, PDF. |
| `/playbooks/ai-video-creator-playbook` | AI Video Creator Playbook · EKIS | **AI Video Creator Playbook — Beginner to Finished Videos** | Go from zero to coherent AI videos: workflow, character consistency, tools and a portfolio plan. 21 levels, beginner-friendly. |
| `/playbooks/ai-for-busy-adults` | AI for Busy Adults · EKIS | **AI for Busy Adults — Learn ChatGPT in 15-Minute Sessions** | A 6-module, 89-page playbook for non-technical adults: ChatGPT basics, AI images, and your first AI video, in 15–30 minute sessions. |
| `/digital` | Digital Skills Hub · EKIS | **Digital Templates, Kits & Playbooks — Browse by Need** | Free planners and trackers plus paid kits for content planning, AI workflows, creator income and small business operations. |
| `/digital/templates` | (templates hub) | **Free Templates & Planners — Content, Income & Productivity** | Download free planners and trackers: social content planner, creator income tracker, 30-day learning plan, sales tracker. No account needed. |
| `/digital/templates/social-content-planner` | Social Content Planner · Free Tool · EKIS | **Free Social Content Planner — Plan YouTube, TikTok & Instagram Posts** | A free browser planner for YouTube, TikTok, Instagram, LinkedIn, X and Facebook. Track topics, hooks, formats and status. Export CSV or print. |
| `/digital/templates/creator-income-tracker` | Creator Income Tracker · Free Tool · EKIS | **Free Creator Income Tracker — Track Revenue by Stream** | Track content, product, affiliate and sponsorship income in one place. Free spreadsheet and printable version, no account needed. |
| `/digital/templates/ai-learning-planner` | 30-Day AI Learning Planner · Free Tool · EKIS | **Free 30-Day AI Learning Plan — Learn AI in Small Daily Steps** | A free 30-day planner for learning practical AI skills without overwhelm. Daily prompts, weekly reviews, printable PDF. |
| `/digital/templates/small-business-sales-tracker` | Small Business Sales Tracker · Free Tool · EKIS | **Free Small Business Sales Tracker — Sales, Customers, Revenue** | Track daily sales, customers and revenue without accounting software. Free spreadsheet and printable version. |
| `/digital/templates/digital-skills-habit-tracker` | Digital Skills Habit Tracker · Free Tool · EKIS | **Free Digital Skills Habit Tracker — Build a Learning Routine** | A simple habit tracker for consistent digital-skills practice: daily streaks, weekly review, printable. Free, no signup. |
| `/digital/kits/social-content-system` | Social Content System · EKIS | **Social Content System — Content Pillars, Briefs & Repurposing Kit** | The paid upgrade to the free planner: pillars, hook library, briefs, repurposing workflow, 30-day system and a performance review. $12. |
| `/digital/kits/ai-prompt-workflow-kit` | AI Prompt & Workflow Kit · EKIS | **AI Prompt & Workflow Kit — Build Reusable AI Workflows** | Stop collecting prompts. Build clear AI requests, chain them into workflows, and review output with better judgment. Worksheets included. $12. |
| `/digital/kits/creator-income-monetization-kit` | Creator Income & Monetization Kit · EKIS | **Creator Income & Monetization Kit — Revenue, Costs, Profit, Next Test** | Turn income tracking into a business review: revenue by stream, costs, profit, and your next monetization experiment. $15. |

**Rules for every page:**

- **Title:** 50–60 characters, query first, brand last. One per page — no two pages may share one.
- **Meta description:** 140–155 characters, written to earn the click, not to stuff keywords. It does
  not affect rankings directly; it affects CTR, which does.
- **H1:** exactly one, different from the title, in the reader's language. "YouTube Strategy
  Playbook" as H1 is fine; the H2s should carry the query variants ("how to choose a topic",
  "how to read a retention graph").

`docs/` note: descriptions above are drafts — rewrite in your voice before shipping.

---

## Part 3 — Thin content (the biggest ranking problem)

### P1 · Free tool pages are ~120 words

`/digital/templates/social-content-planner` is: one H1, one sentence, the tool, two download links,
and one upsell. A page like that cannot rank for "free social media content planner" — despite being
exactly what the searcher wants.

**Add 400–600 words below the tool**, in this shape:

```
H1  Free Social Content Planner

[tool — keep it above the fold]

H2  What this planner does
    2 short paragraphs: what problem it solves, who it's for.

H2  How to use it (4 steps)
    1. Add the platform and format for each idea
    2. Write the hook before the topic
    3. Set a status so nothing dies in drafts
    4. Export the CSV weekly and review what published

H2  Fields explained
    Topic / Format / Hook / CTA / Status / Published URL — one line each.
    This section targets long-tail queries ("what is a hook in content planning").

H2  Spreadsheet and printable versions
    Link both downloads, say what each is for.

H2  Frequently asked questions   (5–6 Q&As, with FAQPage schema)
    Is it really free? · Do I need an account? · Where is my data stored?
    Can I use it for client work? · Does it work on mobile? · Is there a Google Sheets version?

H2  What to do after you've planned
    Link to /digital/kits/social-content-system and one related article.
```

Do the same for all five free tools. These five pages are your **best chance to rank** — low
competition, real search demand ("free content planner", "creator income spreadsheet", "sales tracker
template"), and they feed the paid products.

### P1 · Category hub pages are near-duplicates

`/digital/kits`, `/digital/templates` and `/digital/playbooks` are all grids of the same items with
one sentence of intro. Google can't tell them apart, so they compete with each other.

Differentiate by **intent**, and write 150–250 words on each:

| Hub | Job | Lead with |
|---|---|---|
| `/digital/templates` | "solve this one task now, free" | "Start here if you need a planner today, not a course" |
| `/digital/kits` | "systemise a routine I already do" | "For when the free tool isn't enough and you want the framework around it" |
| `/digital/playbooks` | "learn a skill properly, module by module" | "For when you want a sequenced path, not a template" |

### P2 · Product pages: add the missing sections

The YouTube Strategy Playbook page is genuinely strong (modules, projects, previews, honest costs,
fit check — that's better than most paid product pages). The other product pages are shorter. Bring
them to the same standard, adding:

- **Who it's for / not for** (you already do this on one page — copy the pattern)
- **Sample lesson** with 3 bullets, plus a link to the sample PDF
- **"Why pay when this is free elsewhere"** — this objection section converts, and it's linkable
- **FAQ with 4–6 questions**, marked up with `FAQPage` schema

---

## Part 4 — Content: 6 articles per product

You have 7 resource articles across 3 products. Each playbook needs 6–10 supporting articles, each
answering **one** question a buyer would type before buying. These are the traffic engines; product
pages convert, articles rank.

### YouTube Strategy Playbook (target: creators)

| Article | Query it targets | Links to |
|---|---|---|
| How to choose a YouTube topic that already has demand | `how to choose youtube topics` | playbook |
| How to read a YouTube retention graph (with examples) | `youtube retention graph` | playbook |
| Why your thumbnail isn't getting clicks (7 fixes) | `youtube thumbnail not getting clicks` | playbook |
| YouTube outlier analysis: how to find proven ideas | `youtube outlier analysis` | playbook |
| Title formulas that earn clicks without clickbait | `youtube title formulas` | playbook |
| How many videos before YouTube starts recommending you | `how many videos before youtube promotes you` | playbook |
| A 5-video experiment cycle for small channels | `youtube growth experiment` | playbook |

### AI Video Creator Playbook

Existing four articles are a good start; add: `ai video tools comparison for beginners`,
`how long does an ai video take to make`, `ai video character consistency`, `cheapest way to make ai
videos`, `ai video for youtube monetization rules`.

### AI for Busy Adults

Add: `chatgpt for beginners over 60`, `what to ask chatgpt first`, `is chatgpt safe for personal
data`, `how to make an ai image free`, `ai glossary for non-technical people`.

### Rules

- **One query per article**, in the H1 and the first 100 words.
- 900–1,400 words. Answer the question in the first paragraph, then expand.
- Each article ends with **one** internal link to its product, with a descriptive anchor
  ("the YouTube Strategy Playbook covers this in module 3"), not "click here".
- No AI-generated filler at scale — that's what core updates punish.

---

## Part 5 — Structured data

Add these as JSON-LD. They're cheap and unlock rich results.

### Product + Offer (every playbook and kit)

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "YouTube Strategy Playbook",
  "description": "A 6-module playbook for finding demand, packaging titles and thumbnails, reading retention and running test cycles.",
  "image": "https://www.ekis.store/previews/youtube-strategy/page-1.jpg",
  "brand": { "@type": "Brand", "name": "EKIS" },
  "sku": "ekis-youtube-strategy",
  "offers": {
    "@type": "Offer",
    "url": "https://www.ekis.store/playbooks/youtube-strategy-playbook",
    "price": "69.00",
    "priceCurrency": "USD",
    "availability": "https://schema.org/InStock"
  }
}
```

> If checkout isn't live, use `"availability": "https://schema.org/PreOrder"` — **never** `InStock`
> when a buyer can't complete a purchase. Mismatched availability is a manual-action risk.

### FAQPage (free tools and product pages)

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "Is the Social Content Planner really free?",
    "acceptedAnswer": { "@type": "Answer", "text": "Yes. The browser planner, the spreadsheet and the printable PDF are all free with no account required." }
  }]
}
```

### BreadcrumbList (every page below the homepage)

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Digital", "item": "https://www.ekis.store/digital" },
    { "@type": "ListItem", "position": 2, "name": "Kits", "item": "https://www.ekis.store/digital/kits" },
    { "@type": "ListItem", "position": 3, "name": "Social Content System" }
  ]
}
```

### Organization + WebSite (homepage, once)

Include `name`, `url`, `logo`, and `sameAs` for your real social profiles. Skip `SearchAction`
unless you actually have site search.

**Validate every snippet** at `search.google.com/test/rich-results` before shipping.

---

## Part 6 — Internal linking

Your strongest pages get no link equity from each other. Fix the architecture:

**Hub and spoke, for each product:**

```
/digital/templates/social-content-planner   (free, ranks for the query)
        ↕
/digital/kits/social-content-system          (paid upgrade, $12)
        ↕
/playbooks/youtube-strategy-playbook          (deeper skill, $69)
        ↕
/resources/how-to-plan-youtube-content        (article that ranks)
```

Rules:

1. **Every article links to its product** with one descriptive anchor.
2. **Every product links to its free tool and 2–3 related articles** ("read more about X").
3. **Every free tool links to its paid kit** (you already do this — keep it, and make the anchor
   descriptive).
4. **Homepage links to the three playbooks and the five free tools** — right now it links only to
   three category cards, so your most valuable page passes authority to three hubs and nothing else.
5. Never use "click here" or "learn more" as an anchor. Use the target's subject.

---

## Part 7 — Make the pages convert (SEO that pays)

Rankings that don't convert are a hobby. On every product page:

- **Price and what's included above the fold** — you do this well on the playbook page.
- **Remove every "checkout coming soon" line** (Part 0).
- **Show the refund policy inline**, one sentence, not just a footer link.
- **Email capture on free tools** — "email me the spreadsheet + a 5-day planning sequence". Free
  tools bring traffic; the list is what makes that traffic repeatable.
- **Add one testimonial or your own result** as soon as you have it. Even "I used this on my own
  channel" with a screenshot beats nothing.
- **Make the Gumroad link obvious and in-tab** — don't hide the buy path behind a secondary button.

---

## Part 8 — Links and off-page

You don't need many links; you need a few relevant ones. Realistic, free options:

1. **Make the free tools the link magnet.** A genuinely useful free planner gets cited by
   newsletters, Reddit threads, Discord communities and "tools for creators" roundups.
2. **Answer where your buyers already are** — r/NewTubers, r/youtubers, r/ContentCreators,
   r/smallbusiness, r/Entrepreneur, Indie Hackers, creator Discords. Answer properly, link only when
   it's genuinely the answer (most subs allow it in context; check each).
3. **Get listed in free directories**: AlternativeTo, Product Hunt (one launch), AI-tool and
   template directories for your niche.
4. **Publish one original small study** — "we analysed 100 YouTube outliers" — that's the kind of
   thing that earns links without asking.
5. **Never buy links or guest-post packages.** It's the fastest way to lose the store.

---

## Part 9 — Measurement

Set up once, check weekly:

- **Google Search Console** — verify `www` and apex; submit the sitemap; check Pages + Performance weekly
- **Bing Webmaster Tools** — import from GSC in two clicks, free extra traffic
- **GA4 or Vercel Analytics** — events for `tool_used`, `download_clicked`, `kit_viewed`,
  `checkout_started`, `purchase`
- **A spreadsheet** with one row per week: impressions, clicks, avg position, indexed pages, orders,
  organic revenue

Review rule: compare **week over week** for positions, **month over month** for traffic. Don't judge
a change for 28 days.

---

## Part 10 — Order of operations

### This week (P0 + P1, ~4 hours)

- [ ] Decide the checkout state for each product; remove contradictory copy
- [ ] Fix the "0kits · 0playbooks" empty state
- [ ] Screenshot GSC baseline: impressions, clicks, indexed vs not-indexed, top 20 queries
- [ ] Regenerate the sitemap without `priority`/`changefreq`, with real per-page `lastmod`
- [ ] Confirm apex → www 301 and self-referencing canonicals
- [ ] Run `py -m job_finder --config config.seo.toml --site --site-report audit.md` and work the HIGH list

### Next 30 days

- [ ] Rewrite all titles, descriptions and H1s (Part 2)
- [ ] Add 400–600 words + FAQ to all five free tool pages
- [ ] Add Product/Offer, FAQPage and BreadcrumbList schema
- [ ] Differentiate the three hub pages
- [ ] Link the homepage to all products and free tools
- [ ] Publish 4 articles (one per week) from Part 4

### Days 30–60

- [ ] Publish 8 more articles
- [ ] Convert preview images to WebP and fix mobile Core Web Vitals
- [ ] Add email capture to free tools
- [ ] Redirect/consolidate any page that still has no purpose

### Days 60–90

- [ ] One original study or free tool that earns links
- [ ] Outreach to 20 newsletters/communities that would use the free tools
- [ ] Rewrite product pages with the first testimonials
- [ ] Write the case study (`docs/seo-practice-plan.md` Step 5)

---

## The one thing that matters most

If you do only one thing from this list: **give the five free tool pages 400–600 words of real,
useful explanation each, plus an FAQ.**

They target queries with genuine demand and weak competition, they're the natural entry point for
your buyers, and right now they're 120-word shells. Everything else on this page is refinement
compared to that.
