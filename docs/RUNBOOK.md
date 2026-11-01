# Runbook — GitHub Open Source v6

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

## Required Secrets

| Secret | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot API publishing and owner reports |
| `GEMINI_API_KEY` | Structured generation and news verification |
| `TELEGRAPH_ACCESS_TOKEN` | Full-breakdown pages and card hosting |
| `DEV_API_KEY` | Optional article-of-day |
| `BLUESKY_APP_PASSWORD` | Optional Bluesky crossposts |
| `MASTODON_ACCESS_TOKEN` | Optional Mastodon crossposts |
| `FACEBOOK_PAGE_ACCESS_TOKEN` | Optional direct Facebook Page posts |

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
| `FEATURE_Facebook` | `false`; no Page token in initial rollout |
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

| Time | Action |
|---|---|
| 04:20 daily | Collect candidates |
| 07:10 daily | Project slot 1 |
| 12:40 daily | Project slot 2 |
| 13:30 daily | dev.to article-of-day |
| 15:40 Mon/Wed/Fri | AI Brief, if feature enabled and eligible |
| 17:15 daily | Project slot 3 |
| 22:35 daily | Project slot 4 |
| every 30 min | Due crossposts |
| Sun 16:10 | Weekly digest + poll |
| Sun 16:40 | Owner report |
| every 6 h at :15 | Discussion moderation poll |

GitHub scheduled workflows can be delayed. A missed or empty slot is
preferred over publishing a candidate that does not pass the gate.

## Acceptance before main-channel switch

- [ ] Doctor core checks pass, including Telegram, Gemini, GitHub and card render.
- [ ] Doctor confirms the bot is admin of the test channel and sends hello.
- [ ] At least 3 consecutive days of correct autonomous test posts.
- [ ] Every post has a large preview, GitHub button and Telegraph breakdown.
- [ ] At least one Editorial card and one suitable CLI/Neon Terminal card inspected.
- [ ] dev.to smoke article inspected before `FEATURE_DEVTO=true`.
- [ ] One Bluesky and one Mastodon smoke crosspost inspected before enabling flags.
- [ ] Three forced AI Brief samples checked against primary sources before `FEATURE_AI_BRIEF=true`.
- [ ] Sunday digest and poll render correctly.
- [ ] Weekly owner report arrives in the owner's bot chat.
- [ ] No secret-shaped strings in git history; CI secret scan is green.
- [ ] Temporary setup PAT revoked.
- [ ] Old bot is scheduled to stop on the same day as the switch.

## Facebook status

The legacy path wrote Facebook posts into Google Sheets for an external
consumer. v6 instead contains a direct Meta Pages API adapter, kept
behind `FEATURE_Facebook=false`. It needs a long-lived Page access
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
