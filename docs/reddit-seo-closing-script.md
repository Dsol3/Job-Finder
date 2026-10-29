# Reddit SEO Closing Script

A step-by-step script for closing SEO deals on Reddit, from the first public comment to the signed deal.

This script works within Reddit's rules. The closer only messages people who asked for help publicly, or
who replied to a helpful comment. Mass cold DMs get accounts banned and rarely close.

**Where the leads come from:** posts asking for SEO help in r/smallbusiness, r/Entrepreneur, r/SEO,
r/startups, r/ecommerce, r/forhire and niche subreddits (dentists, lawyers, Shopify stores). Watch for posts
like "my traffic dropped," "how do I rank on Google," or "is SEO worth it?"

> **Watching for these automatically:** `config.seo.toml` matches exactly these phrases and pings your
> Telegram when one appears — see [Finding the leads](#finding-the-leads-automatically) at the bottom.
> r/forhire is the exception; it does not work this way. See [Where each subreddit differs](#where-each-subreddit-differs).

Replace everything in [square brackets] with the prospect's real details.

---

## Stage 1: The public comment

This earns the right to message. Answer their question properly in the thread, with no link and no pitch.

> Traffic drops like this usually come down to one of three things: a Google update, a technical issue
> (pages being deindexed, slow load times), or competitors overtaking your main pages.
>
> Quick check you can do yourself: open Google Search Console → Pages and look for a jump in "not
> indexed" pages around the date your traffic fell. If that's clean, compare your top 5 pages' rankings
> before and after the drop.
>
> I do SEO for a living. If you want, I can take a quick look and tell you which of the three it is. No
> charge for that.

*Why it works: it proves expertise in public, gives them a free win, and lets them choose to reply.*

**Rules for this comment:** no link, no price, no "DM me". One comment per thread — editing it later to
add a pitch is how accounts get flagged.

---

## Stage 2: The DM opener

Send this only after they reply or say yes.

> Hey [name], thanks for getting back to me. Happy to take a look.
>
> Two quick questions so I check the right things:
>
> 1. What's the site?
>
> 2. What matters most to you right now: more traffic, more leads or calls, or getting back what you
>    lost?

*Keep it short. Ask questions instead of pitching.*

---

## Stage 3: Discovery

Find the pain and what it's costing them. Ask these over a few messages, or on a 15-minute call if they're
open to one:

1. "Roughly how many customers or leads does the website bring in each month now?"
2. "What's one new customer worth to you, on average?"
3. "What have you tried so far for SEO? What happened?"
4. "If Google brought you [X] more customers a month, what would that change for the business?"
5. "Is anyone else involved in deciding on this, or is it your call?"

*Closer's note: questions 2 and 4 matter most. They set the value in the customer's own numbers before any
price comes up.*

**Write the two numbers down before Stage 5.** You will use them verbatim when you quote, and you cannot
reconstruct them later from memory.

| Their number | Where it gets used |
|---|---|
| Value of one customer (Q2) | Pricing anchor in Stage 5.5 |
| What [X] more customers would change (Q4) | The scope conversation and the follow-ups |
| Decision-maker (Q5) | Whether the call needs a second person on it |

---

## Stage 4: The mini-audit

This is the free value that sets up the close. Spend 15–20 minutes on the site, then send 3 specific findings:

> Took a look at [site]. Here's what I found:
>
> 1. **[Specific issue]**: e.g. 40 of your service pages aren't indexed by Google, so they can't rank at all.
>
> 2. **[Specific opportunity]**: e.g. '[service] in [city]' gets about [X] searches a month, and you're on
>    page 3. The sites above you have thinner content than yours.
>
> 3. **[Quick win]**: e.g. your homepage takes 6 seconds to load on mobile. Google and visitors both
>    punish that.
>
> Number 1 alone is probably costing you real traffic. Want me to walk you through how I'd fix all
> three?

*Rule: be specific and use their real data. Generic findings like "you need better content" lose deals.*

**Time-box it.** 15–20 minutes, three findings, then send. An audit that takes you two days to deliver
teaches the prospect that you are slow, and it is unpaid work you cannot repeat at scale. If the site is
genuinely broken in ten places, pick the three that map to money.

**Where to look, in order:** Search Console coverage/indexing → rankings for their 5 money pages →
titles and H1s → mobile load time → competitor pages outranking them.

---

## Stage 5: Book the call (reply to schedule)

No booking link. You ask for two windows, they reply with one, you confirm. One thread, no friction, and it
keeps the conversation in the DM where they are already engaged.

> Happy to walk you through it properly — 15 minutes is enough for me to show you what I'd do first and
> what it would take.
>
> What does this week look like? I'm free [day] between [time] and [time], or [day] [time] — whichever
> is easier. I'm on WAT (UTC+1), so tell me your timezone and I'll make it work.
>
> Send me a time and I'll confirm here.

**Rules for this stage:**

- Offer **two specific windows**, not "whenever works for you". Open-ended scheduling loses a third of
  interested prospects.
- Always state your timezone and ask for theirs. If they are US-based, offer a slot in your evening —
  which is their morning.
- **Ask for their email only after the time is agreed**, and only for the call link or a calendar
  invite. Reddit DMs are where the deal lives; asking for an email first reads as a list-building move.
- If they push back on the call ("just send me pricing"), drop to Stage 5.5 in writing. Do not insist.

---

## Stage 5.5: Quote the work

The call ends with scope and price, or it ends with a follow-up. Do not leave a call without one of the two.

> Based on what you told me — [their Q4 in their own words] — here's what I'd start with:
>
> **Scope:** fix the indexing issue on the [X] service pages, rebuild titles and H1s on your 5 money
> pages, and target '[service] in [city]' plus [N] related terms.
>
> **Timeline:** first fixes live in 2 weeks, indexing and early movement typically visible in 6–8 weeks.
>
> **Price:** [price] for the first month, then [price]/month if you want to keep going. 50% upfront,
> 50% on delivery. Wise or Payoneer.
>
> Want me to send that over as a one-page summary?
>
> One thing I won't promise: specific rankings or a specific traffic number. Anyone who guarantees
> that is either guessing or lying. What I can commit to is the work and the reporting.

**Anchor to their number, not yours.** If one customer is worth $800 to them and you quote $1,200/month,
say it out loud: "you need two customers a month for this to pay for itself." That sentence closes more
deals than any percentage.

**Say the guarantee line out loud.** It is the fastest way to look like the only honest person in their
inbox, because everyone else on Reddit is guaranteeing page one.

---

## Stage 6: Follow-up if they go quiet

**Day 3** — surface a question, not a nudge:

> Hey [name], just checking whether you had any questions about the plan for [site].

**Day 7** — add new value:

> Noticed [competitor] just published a page targeting '[keyword]'. Worth moving on that before
> they get ahead. Still happy to help if the timing works.

**Day 14** — close the loop:

> I'll stop following up so I'm not cluttering your inbox. If SEO becomes a priority later, my DMs are
> open. Good luck with [business]!

*Stop after three follow-ups. Messaging more than that on Reddit gets accounts reported.*

**The Day 14 message is not a loss.** A meaningful share of these reply weeks later — "we're ready now" —
because you left a clean exit instead of pestering them. Set a reminder for 60 days and one for 6 months.

---

## Rules for the closer

1. **Always answer the question first in public.** The comment is the advertisement.
2. **Only DM people who replied or asked.** Unsolicited DMs are the fastest way to get banned.
3. **Use their numbers, not yours.** Customer value, lost traffic, competitors.
4. **Be specific in the audit.** Real issues on their real site win the deal.
5. **Never guarantee rankings.**
6. **Use one real account.** It builds a public post history that proves expertise.

### Two more that keep the account alive

7. **One DM per prospect, then only replies.** Never send a second unsolicited message to the same person.
8. **Move payment off Reddit before any work starts.** Reddit DMs are not a contract; a one-page scope
   with a price, a start date and 50% upfront is. Wise / Payoneer / Deel, agreed in writing.

---

## Where each subreddit differs

| Subreddit | How this script applies |
|---|---|
| r/smallbusiness | Stage 1 works exactly as written. Best source of "my traffic dropped" posts. Check the sub's self-promo rules before commenting — some require a minimum account age or karma. |
| r/SEO | Stage 1 works, but the audience is peers. Answer at a higher technical level or you will be corrected in public. Good for credibility, slower for leads. |
| r/Entrepreneur, r/startups | Stage 1 works. Lower SEO intent — these posters often want growth generally. Qualify fast on Stage 3 Q2. |
| r/ecommerce | Stage 1 works. Lead with product/category page issues, not blog content. |
| Niche subs (dentists, lawyers, local services) | Highest close rate and least competition. Stage 1 works, and the sub is small enough that a good answer gets remembered. |
| **r/forhire** | **Different entirely.** It is a job board: posts must be tagged `[Hiring]` or `[For Hire]`. The comment-then-DM play does not apply, and unprompted DMs there get reported. Post a `[For Hire]` ad instead — one per week, niche in the title, 2 samples, rate range, turnaround. Answer `[Hiring]` posts that ask for SEO. |

**Before commenting anywhere new:** read the sub's rules page. Many ban self-promotion in comments outright,
and a removal is a public signal to every prospect who searches your name.

---

## Finding the leads automatically

The watcher in this repo can hunt these lead posts for you, separately from job posts:

```bash
py -m job_finder --config config.seo.toml --dry-run   # see what it would ping
py -m job_finder --config config.seo.toml --once      # start pinging
```

One profile watches both kinds of post, and labels each alert so you know which stage to open with:

- **💼 GIG** — someone offering to pay for SEO or content work (r/forhire, r/HireaWriter, r/SEO).
  Reply with a pitch, samples and a rate.
- **🔎 SIGNAL** — someone describing the problem this script solves ("traffic dropped", "not
  indexed", "is seo worth it", "rank on google"). Open with the public Stage 1 comment.
- **💼🔎 GIG + SIGNAL** — they have the problem *and* want to hire. Rarest, highest scoring: one
  comment can do both jobs.

It watches r/smallbusiness, r/SEO, r/Entrepreneur, r/startups, r/ecommerce, r/shopify, r/forhire and
r/HireaWriter, and drops for-hire ads, other people pitching SEO, agency spam, backlink/PBN offers
and course sellers. GitHub Actions runs this profile every few minutes, so the alerts arrive while
the post still has two comments.

**The tool gets you there while the post has 2 comments. The comment, the audit and the call are still
yours.**
