# Redirect layer (optional)

Telegram does not report link clicks to anybody — not to bots, not to
channels. If click-through is a value signal, the link has to be ours.
This Worker does exactly one thing: `/r/<code>` → 302 → the GitHub repo,
plus a KV counter.

## Why it is optional

With `REDIRECT_BASE_URL` unset the pipeline publishes direct GitHub links
and simply does not measure clicks. Views and poll votes keep working.
Nothing fails; the value score just has one signal fewer.

## Deploy (free tier, no card)

```bash
npm i -g wrangler
wrangler kv namespace create REPOS   # paste the id into wrangler.toml
wrangler kv namespace create STATS
wrangler secret put STATS_TOKEN      # any long random string
wrangler deploy
```

Then set the repository variable
`REDIRECT_BASE_URL=https://ghs-links.<you>.workers.dev`.

## Loading the map

`ghos-v6 links-export` prints `{code: "https://github.com/owner/repo"}` for
every published record. Upload it once, and again after publish runs:

```bash
wrangler kv bulk put --binding=REPOS links.json
```

## Cost

Cloudflare free tier: 100 000 requests/day, 1 000 KV writes/day. Three
posts a day with a few hundred clicks each is nowhere near the ceiling.

## Honest limitation

A redirect hides the real URL from the reader and adds ~50 ms. If the
channel ever grows past the free tier, or if the extra hop hurts trust,
delete the variable and the pipeline falls back to direct links the same
minute — no code change.
