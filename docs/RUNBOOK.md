# Runbook — GitHub Open Source v6

> **In the current repository the publishing workflows are off.**
> `usawolfseller-a11y/github-open-source-v6` is a test account and the owner
> instructed that nothing be published from it. `pipeline.yml` and
> `doctor.yml` are `disabled_manually`. Use this runbook for a fresh account,
> not to re-enable this one.

## Environments and target lock

The test rollout uses:

```text
APP_ENV=test
PUBLISH_TARGET=test
TELEGRAM_TEST_CHANNEL_ID=<private test channel numeric ID>
```

Main-channel publishing requires **all three** changes together:

```text
APP_ENV=production
PUBLISH_TARGET=main
TELEGRAM_MAIN_CHANNEL_ID=<main channel ID or @GitHub_Open_Source>
```

`TELEGRAM_MAIN_CHANNEL_ID` is the canonical name and is configured in Actions Variables. The legacy `MAIN_TELEGRAM_CHANNEL` is still read by `config.py` and passed by both workflows, but new setups must use the canonical name.

If the test ID is empty, publishing fails closed. It never falls back to
the main channel.

## Discovering Telegram IDs

1. Owner opens the bot and presses **Start**.
2. Owner adds the bot as admin to the private test channel.
3. Owner posts `setup` in the test channel.
4. Run the **Doctor** workflow. Its `telegram_discovery` check prints
   candidate owner/channel/group IDs.
5. Set repository Variables:
   - `TELEGRAM_TEST_CHANNEL_ID`
   - `TELEGRAM_OWNER_CHAT_ID`
6. Re-run Doctor with **hello** enabled.

Telegram retains unconfirmed bot updates for a limited period. If the
discovery lists are empty, repeat steps 1–3 and run Doctor again.

## Weekly operations (new in this cycle)

| Command | What it does | Safe to re-run |
|---|---|---|
| `ghos-v6 metrics --limit 12` | Reads views for recent posts from the public widget | yes |
| `ghos-v6 poll-close` | Stops the active poll, stores the tally | no-op when no poll is open |
| `ghos-v6 learn` | Recomputes language/topic multipliers | yes, overwrites the model |
| `ghos-v6 facebook-handoff --limit 1` | Appends one row to the make.com sheet | no-op when already queued |

The scheduled workflow runs them automatically: Sun 16:10 digest + poll,
daily 19:50 metrics, Thu 18:10 close + learn.

### Reading the state

- `state.json → published[*]` — one record per post: `value_score`,
  `views`, `views_at_24h`, `revisit_of`, `description_fp`.
- `state.json → poll_history` — every closed poll with per-option shares.
- `state.json → value_model` — the multipliers currently influencing
  selection, with the sample size that produced them.
- `state/events.jsonl` — append-only audit trail; every duplicate skip and
  every model update is a line here.

### If a duplicate slips through

1. Find it in `events.jsonl` (`project_published`).
2. Add the missed variant to `dedup.check` only if it is a *new class* of
   duplicate — otherwise the fingerprints already cover it.
3. Never delete from `published`: the anti-dup keys off it.

## Required Secrets

| Secret | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot API publishing and owner reports |
| `GEMINI_API_KEY` | Structured generation and news verification |
| `IMGBB_API_KEY` | Primary public host for rendered card images (direct CDN URL) |
| `TELEGRAPH_ACCESS_TOKEN` | Full-breakdown (Telegraph) pages |
| `DEV_API_KEY` | Optional article-of-day |
| `BLUESKY_APP_PASSWORD` | Optional Bluesky crossposts |
| `MASTODON_ACCESS_TOKEN` | Optional Mastodon crossposts |
| `FACEBOOK_PAGE_ACCESS_TOKEN` | Optional direct Facebook Page posts (needs a Page token, not a user token) |

Facebook is published by make.com from a Google Sheet. v6 feeds that sheet
with `ghos-v6 facebook-handoff`; full setup in `docs/FACEBOOK_PIPELINE.md`.

Click tracking was evaluated and **rejected** by the owner: it would route
every GitHub link through a third-party domain. Links stay `github.com`.

## Setup from scratch (a fresh account or repository)

1. `python -m pip install -e '.[test]'` in the repo.
2. Add the ten **Secrets** listed above under Settings → Secrets → Actions.
3. Add the **Variables** listed further down under Settings → Variables.
4. Start with every feature flag false and `APP_ENV=test`,
   `PUBLISH_TARGET=test`.
5. Owner presses Start on the bot, adds it as admin to the test channel and
   posts `setup` there; run **Doctor** to discover `TELEGRAM_TEST_CHANNEL_ID`.
6. Run `ghos-v6 doctor` until 13/13 answer.
7. Enable one surface at a time: `FEATURE_DEVTO` → `FEATURE_BLUESKY` →
   `FEATURE_MASTODON` → `FEATURE_FACEBOOK` → `FEATURE_AI_BRIEF`.
8. Only after the acceptance checklist passes: `APP_ENV=production`,
   `PUBLISH_TARGET=main`, `TELEGRAM_MAIN_CHANNEL_ID=<main channel>`.

Note the exact spelling `FEATURE_FACEBOOK`. The legacy `FEATURE_Facebook`
spelling is still read for backward compatibility, but new setups must use
the canonical name; the two spellings are no longer mixed in the workflows.

## Post types on the test channel

All four card families have been posted as real messages (1 Nov 2026):

| Card | When it is used | Message |
|---|---|---|
| Editorial | default for library/app/web projects | 9 |
| Neon Terminal | CLI/TUI projects | 6 |
| AI Brief | verified AI news, 3×/week | 7 |
| Sunday Digest | weekly Top 5 + poll | 8 |

The week poll (message 10) was opened and closed in the same session to
prove the `sendPoll` → `stopPoll` path. Note: **channel polls must be
anonymous** — Telegram rejects named polls in channels, which the first
attempt hit.

`IMGBB_API_KEY` is optional at runtime: without it, cards fall back to
the monthly GitHub release host, then to Telegraph upload, then to
GitHub OpenGraph. Media hosting is only needed until each platform has
copied the image: Telegram stores the photo on its own CDN, Bluesky and
Mastodon upload blobs, and dev.to downloads the cover. Telegraph
articles keep hot-linking the uploaded URL, so an expired or deleted
ImgBB image would leave a broken image on the Telegraph page only.

There is deliberately no personal Telegram session secret in v1.
GitHub API calls inside workflows use the built-in `github.token`,
mapped to `GH_API_TOKEN`.

## Important Variables

| Variable | Test value |
|---|---|
| `APP_ENV` | `test` |
| `PUBLISH_TARGET` | `test` |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` |
| `FEATURE_TELEGRAPH` | `true` |
| `FEATURE_DEVTO` | `false` until article smoke test |
| `FEATURE_BLUESKY` | `false` until social smoke test |
| `FEATURE_MASTODON` | `false` until social smoke test |
| `FEATURE_FACEBOOK` | `false`; no Page token in initial rollout |
| `FEATURE_AI_BRIEF` | `false` until three sample briefs pass review |

`TELEGRAM_SOURCE_CHANNELS` may contain public usernames separated by
commas. Private invite links do not belong in public code or Variables.

## Manual workflow commands

Use **Actions → Publishing pipeline → Run workflow**:

- `collect` — rebuild the gated candidate queue;
- `publish` — publish one project to the resolved target;
- `crossposts` — process due social posts;
- `article` — publish the best project of the day to dev.to;
- `news` — attempt one verified AI Brief (`force_news` only for test
  samples while the feature flag is off);
- `digest` — Top 5 + poll;
- `report` — owner weekly report;
- `moderation` — poll recent discussion updates for obvious spam.

## Schedule (UTC)

| Time (UTC) | Cron | Action |
|---|---|---|
| 04:20 daily | `20 4 * * *` | Collect candidates |
| 07:10 daily | `10 7 * * *` | Project slot 1 |
| 12:40 daily | `40 12 * * *` | Project slot 2 |
| 17:15 daily | `15 17 * * *` | Project slot 3 |
| 13:30 daily | `30 13 * * *` | dev.to article-of-day |
| 19:15 daily | `15 19 * * *` | AI Brief (feature flag) |
| :05 and :35 hourly | `5,35 * * * *` | Due crossposts |
| 18:20 daily | `20 18 * * *` | Facebook handoff (make.com) |
| 20:20 daily | `20 20 * * *` | Views snapshot / metrics |
| every 3 h at :45 | `45 */3 * * *` | Discussion moderation |
| Sun 16:10 | `10 16 * * 0` | Weekly digest + poll |
| Sun 16:40 | `40 16 * * 0` | Owner report |
| Thu 18:50 | `50 18 * * 4` | Close poll **and** `learn` (value model) |
| Mon 06:17 | `17 6 * * 1` | Lifecycle guard (checks only, no publishing) |

Three project posts a day is an owner decision. `MAX_PROJECT_POSTS_PER_DAY = 3`
is enforced in code, so a fourth cron must not be added.

GitHub scheduled workflows can be delayed. A missed or empty slot is
preferred over publishing a candidate that does not pass the gate.

## Long-term operation (5+ years)

- `StateStore` compacts `state.json` on every save: `seen_repos` older than 180
  days are dropped, full `published` records older than 90 days become a light
  index (de-duplication keys are kept), lists are capped at 500 items. Keys in
  `published` are never removed, so `commit-state`'s count guard still holds.
- `CI` fails when `state.json` exceeds 10 MiB. The weekly **Lifecycle guard**
  checks that limit, repository activity (GitHub disables schedules after 60
  quiet days) and whether `GEMINI_MODEL` is still listed by the API; it opens
  an issue instead of failing silently.
- `gemini-3.5-flash-lite` may be retired as early as 2027-07-21. Check the
  model list monthly and update the `GEMINI_MODEL` Variable before switching.
- Python 3.12 reaches EOL in October 2028; CI now runs 3.13. Rebuild the
  hashed lock files when moving to the next interpreter.
- Full analysis and remaining architectural work (state in a separate branch,
  removing `fetch-depth: 0`): [`RELIABILITY_2026-11-03.md`](RELIABILITY_2026-11-03.md).

## Acceptance before main-channel switch

- [ ] Doctor core checks pass, including Telegram, Gemini, GitHub and card render.
- [ ] Doctor confirms the bot is admin of the test channel and sends hello.
- [ ] At least 3 consecutive days of correct autonomous test posts.
- [ ] Every post has a large preview, GitHub button and Telegraph breakdown.
- [ ] At least one Editorial card and one suitable CLI/Neon Terminal card inspected.
- [ ] dev.to smoke article inspected before `FEATURE_DEVTO=true`.
- [ ] One Bluesky and one Mastodon smoke crosspost inspected before enabling flags.
      **This is the only subsystem never exercised live — start here.**
- [x] AI Brief proven able to publish (fixed 2026-11-02): built from the
      x.ai primary source, 1764 characters, `eligible: true`. Two more forced
      samples still worth checking before `FEATURE_AI_BRIEF=true`.
- [ ] Sunday digest and poll render correctly.
- [ ] Weekly owner report arrives in the owner's bot chat.
- [ ] No secret-shaped strings in git history; CI secret scan is green.
- [ ] Temporary setup PAT revoked.
- [ ] Old bot is scheduled to stop on the same day as the switch.

## Facebook status

The legacy path wrote Facebook posts into Google Sheets for an external
consumer. v6 instead contains a direct Meta Pages API adapter, kept
behind `FEATURE_FACEBOOK=false`. It needs a long-lived Page access
token created through the owner's Meta OAuth flow. Do not copy a
personal Facebook password, App Secret or short-lived user token into
this repository.

## Hashnode status

Hashnode is intentionally not part of the initial adapter set. Current
Hashnode API writing requires the target publication to be on Pro,
which conflicts with the project's $0 operating rule. dev.to is the
free article surface unless the existing publication is already Pro or
Hashnode changes the policy.

## Token rotation

- Telegram bot token: BotFather `/token`, then replace `TELEGRAM_BOT_TOKEN`.
- Gemini: create a replacement key in AI Studio, update the secret,
  run Doctor, then delete the old key.
- Bluesky: create a new App Password, update the secret, revoke the old one.
- Mastodon: delete/recreate the application token with the same minimal scopes.
- dev.to: generate a new API key in Settings → Extensions.
- Telegraph: create a new account only if necessary; old pages stay
  attached to the previous account token.
- Setup PAT: never make it long-lived; revoke after bootstrap.

## Incident shortcuts

**Wrong or unsafe post:** delete it in Telegram, set every feature flag
that could amplify it to `false`, inspect the repo/event in
`state/events.jsonl`, then tighten the gate before re-enabling.

**No posts for a day:** run Doctor, then run `collect` manually and read
the rejection counters. Do not lower the star/license floor reflexively.

**Duplicate risk after a failed workflow:** inspect `state/state.json`
and recent commits. If Telegram shows a post that state does not know,
add its repository to `published` manually with the Telegram message ID
before running another publish slot.

**Credential leak:** rotate the affected credential first. Only then
inspect Actions logs and git history. A Telegram bot token is revocable;
never replace a leaked personal session with another shared session.

---

## Security checks (2026-11-02)

Before opening a PR:

```bash
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps -e .
ruff check .
mypy src
pytest
python tools/secret_scan.py
```

`gitleaks` and CodeQL run in CI. Do not disable them. The publishing
workflow is split into a read-only `run` job and a `commit-state` job; keep
the split. `requirements.lock` is mandatory for reproducible installs.

`TELEGRAM_MAIN_CHANNEL_ID` is intentionally unset in the test repository.
Setting it is a production decision: the value must be the main channel
(`@GitHub_Open_Source`), never the test channel id.
