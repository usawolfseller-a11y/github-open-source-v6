# Security policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately.

- **GitHub private vulnerability reporting:** Settings → Security → Private
  vulnerability reporting (enabled for this repository). Use the
  "Report a vulnerability" button in the Security tab.
- **Fallback:** open a private security advisory or contact the maintainer
  through the repository owner. Do not open a public issue for an
  unpatched vulnerability.

Please include:

- affected version or commit,
- reproduction steps or a proof of concept,
- impact you believe it has,
- any logs or screenshots (redact credentials).

We aim to acknowledge a report within 72 hours and to ship a fix or a
mitigation within 14 days for high-severity issues.

## Scope

This repository is an **unofficial** open-source discovery and publishing
system for the Telegram channel `@GitHub_Open_Source`. It is not affiliated
with GitHub, Inc.

In scope:

- the Python package under `src/ghos_v6`,
- the GitHub Actions workflows under `.github/workflows`,
- the state handling and the publishing pipeline.

Out of scope:

- the Telegram channel, its moderation, or accounts operated by third
  parties,
- the content of third-party repositories that the bot reads,
- social accounts (Bluesky, Mastodon, Facebook, dev.to) — report account
  compromise to the respective platform.

## Security properties

- The bot never executes code from a repository it reads. README content is
  treated as untrusted data, is wrapped in a data block for the model, and
  is stripped of wrapper tags before the prompt is built.
- Only PNG, JPEG, GIF and WEBP images are decoded, with a 40 MP pixel cap.
  Pillow is pinned to a supported major version.
- Outbound HTTP is HTTPS-only, redirects are followed manually, and every
  hop is checked against private IP ranges (SSRF protection).
- Secrets are redacted from logs and from the committed event log.
- The publishing workflow runs project code with a read-only token and no
  persisted checkout credentials. A separate job commits the state, has no
  access to publishing secrets, and refuses to commit a state that lost
  published records.
- A queued run syncs `origin/main` before it starts, and the `commit-state`
  job syncs `main` again before comparing/committing, so a stale queued run
  cannot lose the state or republish a post.
- `download_bytes` follows redirects manually and validates every hop, so a
  public URL cannot bounce the bot to a private address.
- Cross-posts are crowned from all of today's posts, not only from pending
  ones; the losers stay `held`. A failed Telegram publish removes the
  candidate and records a dead-letter instead of blocking the queue.
- The deterministic fallback (no Gemini) is `safety="reject"` for every
  project, including dual-use: the bot fails closed rather than publishing
  without a safety verdict. A Gemini outage keeps the candidate in the queue.
- Moderation ignores Telegram service senders (`is_automatic_forward`, user
  777000), so the channel's own forwarded posts are not deleted.

## Known operational risks

- The repository is a **test** rollout. The owner instructed that publishing
  from this account stop. Do not re-enable `pipeline.yml` or `doctor.yml`
  without a written decision from the owner.
- Keys for the brand accounts currently live in the test account's secrets.
  When moving to a production repository, revoke and re-issue every key.
- `state/state.json` is committed to `main`. It contains no credentials and
  no private test-channel id, but it is public; keep it that way.
- `TELEGRAM_OWNER_CHAT_ID` is not set in the test repository, so owner alerts
  and reports will not be delivered. Set it before production.
- `GOOGLE_SERVICE_ACCOUNT_JSON` is not set, so the Facebook Sheets handoff
  cannot write rows. Set it before enabling `FEATURE_SHEETS_HANDOFF`.

## Disclosure

We will publish a short note in the release notes for any security fix and
credit the reporter unless they prefer to remain anonymous.

## Manual repository settings (not applied by the token)

The fine-grained token used for this remediation could read Actions variables
but not write them (`PUT /actions/variables/...` returned 404). Set these in
**Settings → Secrets and variables → Actions**:

- Variable `TELEGRAM_TEST_CHANNEL_ID` = `-1003909350927` (the test channel).
- Variable `TELEGRAM_OWNER_CHAT_ID` = the owner's private chat id. Without it
  owner reports and alerts are silently not delivered.
- Secret `GOOGLE_SERVICE_ACCOUNT_JSON` = the service-account JSON. Without it
  the Facebook Sheets handoff cannot write rows.

`main` is protected by the ruleset `main-protection`, which blocks force-push
and branch deletion. Required status checks were **not** added: the state bot
commits directly to `main` with `[skip ci]`, so a required `CI` check would
block every state commit. To require checks, move the state to a separate
branch or add a bypass actor for `github-actions[bot]` in the ruleset.
