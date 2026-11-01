# Value system — how we decide what worked, and what to post next

Three subsystems, deliberately small and auditable. Nothing here calls an
LLM: a ranking weight that changes silently is worse than no ranking.

## 1. Anti-duplication (`src/ghos_v6/dedup.py`)

Runs inside `publish_slot` before the gate, on the enriched candidate.

| Layer | Catches | Cost |
|---|---|---|
| Repo key (`full_name`, else `id:`) | The same repo twice | O(1) |
| Description shingles (word bigrams, containment ≥ 0.55) | A renamed fork or a repost | O(n) |
| README fingerprint (first 400 words, badges stripped) | A copy-paste README under a new name | O(n) |
| Milestone check | Re-visits | O(1) |

A re-visit is allowed **only after 90 days** *and* **only** with a measurable
event: stars grew ≥ 50 %, or a major release tag appeared. The record then
carries `revisit_of` and `revisit_reason`, so the post is an update, not a
repeat.

Owner decision, 2026-11-01: re-visits are milestone-only.

## 2. Measurement (`src/ghos_v6/insights.py`)

Telegram gives a bot no analytics. There are exactly two free signals:

**Views** come from the public embed widget
`https://t.me/<channel>/<id>?embed=1&mode=tme`. Verified live on
`@GitHub_Open_Source` (posts 3545→17, 3544→41, 3543→52 on 2026-11-01).

**Votes** come from `stopPoll` on a poll the bot itself created, before it
expires. Telegram caps polls at 10 days and cannot create them
retroactively — which is why the weekly poll must be opened on schedule.

**Clicks** are not available from Telegram at all. The optional redirect
layer (`infra/redirect/`) supplies them; when `REDIRECT_BASE_URL` is unset
the score simply omits that term.

### Age normalisation — the part that matters

Views accumulate for about a week. Measured on the live channel:

| Age | Views/hour | Cumulative |
|---|---|---|
| 1 h | ~12 | 17 |
| 4 h | ~6 | 24 |
| 24 h | ~2.6 | 62 |
| 40 h | ~2.2 | 88 |
| 250 h | ~0.7 | 208 (2 weeks) |

Comparing raw counts would call every fresh post a flop. Every score is
therefore rescaled to a **24-hour reference age** (`views_at_reference`),
clamped to 0.3×–6× so a single outlier cannot dominate.

### Score

```
value = 50·(views@24h / median_views) · 1.0
      + min(20, votes_share·20) ├ 6.0
      + min(15, click_rate·100) ├ 4.0
      + min(10, reactions)      ├ 2.0
```

Views carry the baseline because they exist for every post; votes and
clicks are bonuses that only exist when the loop is healthy.

## 3. Learning (`learn` command, Thursdays after the poll closes)

For each language and topic it compares the median value score of posts
having it against the overall median, and writes a multiplier:

```
multiplier = clamp(0.85 … 1.15, 1 + (local_median − overall_median) / overall_median × 0.5)
```

`select_candidate` multiplies the editorial score by the language and topic
multipliers (final clamp 0.8–1.25). With fewer than 5 measured posts the
model is not written at all — a two-sample "insight" is noise.

**Review rule:** if a multiplier sits at a clamp for two consecutive weeks,
the model is fighting the editorial score. Read the raw posts before
trusting it.

## 4. Weekly cycle

| When (UTC) | What | Where |
|---|---|---|
| Sun 16:10 | Digest of the week's top 5, poll opens (96 h) | `digest` |
| Daily 19:50 | Views snapshot for 12 recent posts | `metrics` |
| Thu 18:10 | Poll closes, tally stored, then `learn` | `poll-close` + `learn` |
| Sun 16:40 | Owner report | `report` |

The close and the learn run on the **same cron, in that order**, so `learn`
never reads a poll that has not been closed yet.

## 5. What is deliberately absent

- No LLM in the ranking loop.
- No retroactive polls (impossible via the Bot API).
- No MTProto session (needs a phone number, risks the account).
- No silent weight changes: every model update lands in `state.json` and in
  `events.jsonl`, both committed by the workflow.
