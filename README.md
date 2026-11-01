# GitHub Open Source v6

Autonomous, zero-cost discovery and publishing system for the
[GitHub Open Source](https://t.me/GitHub_Open_Source) Telegram channel.

> **Rollout state:** the code is production-shaped, but the repository
> Variables lock it to a private test channel (`APP_ENV=test`,
> `PUBLISH_TARGET=test`). It must not be pointed at the main channel until
> the test acceptance checklist in [`docs/RUNBOOK.md`](docs/RUNBOOK.md) passes.

## What it does

- Collects a daily pool of repositories from GitHub Search, Hacker News
  and optional public Telegram source channels.
- Enriches candidates with GitHub metadata, contributors and README.
- Applies a conservative autonomous quality/safety gate: license,
  activity, community signal, README, permanent dedup and a malicious-
  topic blocklist. Legitimate dual-use security tools are labelled.
- Uses one structured Gemini call per project for the Telegram post,
  Telegraph/article text and social copy. A deterministic fallback keeps
  a slot alive when Gemini is unavailable.
- Publishes long Telegram text posts (up to the 4,096-character Bot API
  budget) with a large preview above the text and inline buttons.
- Creates a Telegraph full breakdown for every published project.
- Uses the adopted card system: Editorial Daily by default, Neon
  Terminal for CLI/TUI projects, Glass Aurora only for AI Brief assets,
  and Editorial Sunday Edition for the digest.
- Queues Bluesky/Mastodon/Facebook crossposts behind feature flags with
  retries and dead-letter records.
- Can publish the best project of the day to dev.to.
- Includes a verified WorldofAI AI Brief track: the YouTube channel is a
  discovery radar only; a fetchable primary source is mandatory.
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
  platforms.py   dev.to, Bluesky, Mastodon, Facebook adapters
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
python -m pip install -e '.[test]'
pytest -q
python tools/secret_scan.py
ghos-v6 doctor
```

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

## License

MIT. The channel name/branding remains the property of its owner.
