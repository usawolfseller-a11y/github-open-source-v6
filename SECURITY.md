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

## Known operational risks

- The repository is a **test** rollout. The owner instructed that publishing
  from this account stop. Do not re-enable `pipeline.yml` or `doctor.yml`
  without a written decision from the owner.
- Keys for the brand accounts currently live in the test account's secrets.
  When moving to a production repository, revoke and re-issue every key.
- `state/state.json` is committed to `main`. It contains no credentials, but
  it is public; keep it that way.

## Disclosure

We will publish a short note in the release notes for any security fix and
credit the reporter unless they prefer to remain anonymous.
