# GitHub Open Source v6

Autonomous, zero-cost discovery and publishing system for the
[GitHub Open Source](https://t.me/GitHub_Open_Source) Telegram channel.

> **Unofficial project.** This is an independent project. It is not
> affiliated with, endorsed by, or sponsored by GitHub, Inc. The channel
> name and account handles belong to their owner; no GitHub brand rights
> are claimed. Add the same disclaimer to every public account profile.

> **Rollout state (2026-11-03):** the owner lifted the publishing bans and
> authorised live runs — «публикацию разрешаю и все запреты снимаю».
> `pipeline.yml` and `doctor.yml` may now be enabled. The target lock stays
> in force: `main` requires `APP_ENV=production`, `PUBLISH_TARGET=main` and a
> real `TELEGRAM_MAIN_CHANNEL_ID`; with test variables every post goes to the
> private 1:1 test channel, and an empty test ID fails closed. Live
> acceptance checklist: [`docs/RUNBOOK.md`](docs/RUNBOOK.md).
>
> **Security posture:** project code runs in a read-only job with no
> persisted checkout credentials; a separate job with no publishing
> secrets validates and commits the state. See [`SECURITY.md`](SECURITY.md).
>
> **Reliability + intent tests (2026-11-03):** CI is green on Python 3.13 —
> **304 tests**, **65.9 % branch-inclusive coverage** (69 % lines,
> 55 % branches) and **30/30 intentional mutations killed** by
> `tools/mutation_check.py`. The wheel ships all 142 card icons; state
> compaction, a weekly lifecycle guard and executable owner-rule invariants
> are in place. Every outbound CTA points at the real production channel;
> Facebook is published only through make.com + a Google Sheet row (no Page
> token, no `FEATURE_FACEBOOK`). See
> [`docs/RELIABILITY_2026-11-03.md`](docs/RELIABILITY_2026-11-03.md).

## New here? Read these in order

| # | Document | Why |
|---|---|---|
| 1 | [`docs/HANDOFF.md`](docs/HANDOFF.md) | **Start here.** State of the project, what is done, what is not, first steps |
| 2 | [`docs/OWNER_RULES.md`](docs/OWNER_RULES.md) | Decisions the owner made that are not up for redesign |
| 3 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | How the modules fit together and why |
| 4 | [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Daily running, incidents, rollback |
| 5 | [`docs/ROADMAP.md`](docs/ROADMAP.md) | Phases from here to production |
| 6 | [`docs/AUDIT_2026-11-02.md`](docs/AUDIT_2026-11-02.md) | What was verified by running it, and the four defects found |
| 7 | [`SECURITY.md`](SECURITY.md) | How to report a vulnerability, security properties, known operational risks |
| 8 | [`docs/RELIABILITY_2026-11-03.md`](docs/RELIABILITY_2026-11-03.md) | Production-readiness and 5-year reliability audit, and the fixes applied |
| 9 | [`docs/SECRETS_CHECKLIST.md`](docs/SECRETS_CHECKLIST.md) | Exactly which secrets/variables are still missing and where to get them |

Live crossposts and dev.to articles are already proven (2026-11-03), with
all outbound CTAs pointing at the real production channel. Mastodon was
removed after the account was banned for spam. The remaining blocker is the
make.com sheet hand-off: see `docs/SECRETS_CHECKLIST.md`.

## What it does

- Collects a daily pool of repositories from GitHub Search, Hacker News
  and optional public Telegram source channels.
- Enriches candidates with GitHub metadata, contributors and README.
- Applies a conservative autonomous quality/safety gate: license,
  activity, community signal, README, permanent dedup and a malicious-
  topic blocklist. Legitimate dual-use security tools are labelled.
- Uses two structured Gemini calls per project: an editorial pass and a
  per-surface copy pass. A deterministic fallback is used for surface copy
  when Gemini is unavailable; publishing a project requires a model verdict,
  so the slot is skipped (fail-closed) without Gemini.
- Publishes long Telegram text posts (up to the 4,096-character Bot API
  budget) with a large preview above the text and inline buttons.
- Creates a Telegraph full breakdown for every published project.
- Uses the adopted card system: Editorial Daily by default, Neon
  Terminal for CLI/TUI projects, Glass Aurora only for AI Brief assets,
  and Editorial Sunday Edition for the digest.
- Queues Bluesky/Facebook crossposts behind feature flags with
  retries and dead-letter records.
- Can publish the best project of the day to dev.to.
- Includes a verified WorldofAI AI Brief track: the YouTube channel is a
  discovery radar only; a primary source is preferred but not required
  (owner decision), and the brief never carries a "no confirmation" label.
- Publishes a Sunday Top 5 digest + poll and a weekly owner report.

## Architecture

```text
GitHub Search ─┐
Hacker News ───┼─> enrich -> gate -> rank -> queue
Telegram web ──┘                              |
                                              v
                           Gemini / deterministic fallback
                                              |
                         visual cascade -> Telegraph first
                                              |
                                      Telegram test/main
                                              |
                    dev.to article + delayed social crossposts

WorldofAI RSS -> strict filters -> primary source -> Gemini verify
              -> AI Brief (separate feature flag)
```

State is deliberately boring: an append-only `state/events.jsonl`
audit log plus a deterministic `state/state.json` projection committed
by GitHub Actions. All scheduled state writers share one concurrency
group.

## Repository layout

```text
src/ghos_v6/
  config.py      environment + target safety lock
  sources.py     GitHub/HN/Telegram-web collection and enrichment
  gate.py        autonomous quality/safety gate
  rank.py        deterministic ranking and diversity selection
  Gemini.py      structured generation + fallback
  formatter.py   long Telegram project posts
  cards.py       Editorial/Terminal/Aurora/Sunday renderers
  media.py       README -> card -> OpenGraph visual cascade
  telegraph.py   Telegraph pages and image upload
  telegram.py    Bot API client and ID discovery
  platforms.py   dev.to, Bluesky, Facebook adapters
  content_adapters.py  platform-native copy, limits, tags and alt text
  news.py        WorldofAI RSS and verified AI Brief synthesis
  pipeline.py    collect/publish/crosspost/article/news/digest/report
  doctor.py      non-destructive integration checks
  cli.py         GitHub Actions entry point
state/
  state.json
  events.jsonl
```

## Local development

```bash
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps -e .
ruff check .
mypy src
pytest
python tools/secret_scan.py
ghos-v6 doctor
```

Dependencies are locked with hashes: `requirements.lock` is runtime-only
(installed by the publishing job), `requirements-dev.lock` adds the linters and
tests. Regenerate with `pip-compile --generate-hashes requirements.in` and
`pip-compile --generate-hashes requirements-dev.in`. CI runs the same install,
plus gitleaks and CodeQL.

Real credentials belong only in GitHub Secrets/Variables. See
`.env.example` for names, `docs/RUNBOOK.md` for rollout operations
and `docs/CONTENT_FORMATS.md` for per-platform structure, size and tone
(`docs/FORMAT_AUDIT_V2.md` records the audit findings behind format v2).

## Safety principles

- No personal Telegram user session is used for publishing.
- The publication target cannot fall back from test to main.
- README and video text are untrusted LLM input, never instructions.
- A failed crosspost cannot roll back the Telegram post.
- Sponsored and rumor-only news is rejected.
- Secrets are redacted from errors and are never committed.

## Security

The 2026-11-02 external audit found three high-severity issues. All are fixed
in this branch:

- **Pillow** is pinned to `>=13,<14`, and every `Image.open` of untrusted data
  passes an explicit `formats=` allowlist (PNG/JPEG/GIF/WEBP) with a 40 MP cap.
- **CI/CD** is split into a read-only `run` job and a `commit-state` job that
  receives no publishing secrets. Checkout credentials are not persisted,
  actions are pinned to SHAs, and the state commit is validated against the
  published count.
- **Untrusted content** cannot close the model's data block, links in
  generated articles are allowlisted, `curl … | sh` never reaches a post, and
  `safety` is fail-closed (`reject` when missing or invalid).

`state.json` corruption now raises `StateCorruptError` instead of silently
resetting, and the queue keeps only a 1,200-character README excerpt. See
[`SECURITY.md`](SECURITY.md) for the full policy and known operational risks.

A second audit (logic and operations) is also addressed:

- A queued run syncs `origin/main` before it starts, so it cannot republish a
  post that the previous run already committed.
- Cross-posts are crowned from **all** of today's posts, not only from the
  ones that still have a pending cross-post; the losers stay `held`.
- The deterministic fallback (no Gemini) is `safety="reject"` — fail-closed.
- A failed Telegram publish removes the candidate and records a dead-letter,
  so one bad project cannot block the queue.
- The README fingerprint uses the same stored 1200-char prefix at save and
  check time.
- `news.fetch_primary_text` is SSRF-checked and bounded; cross-post image
  downloads happen only for the day's winner.
- Facebook handoff runs daily at 18:20 and selects the best post of the day.

A third audit (regressions) is fixed too: redirects are followed instead of
aborting the download, `commit-state` syncs `main` before committing, the
day's social winner is fixed once a post goes out, the deterministic fallback
rejects dual-use projects as well, a Gemini outage keeps the candidate in the
queue, ranking uses the full README length, crons are staggered, moderation
ignores service senders, and the legacy `MAIN_TELEGRAM_CHANNEL` name is
accepted.

## License

MIT. The channel name/branding remains the property of its owner.
