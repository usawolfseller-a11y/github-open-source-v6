# Content formats and tone by platform

Decision: **one canonical fact pack, native adaptation per surface**.
Gemini writes the facts once; deterministic adapters in
`src/ghos_v6/content_adapters.py` reshape them for each platform.
That gives consistent truth, different rhythm, no extra LLM calls.

Shared voice — *curious senior developer-editor*:

- specific and useful, never fake first-person ("I tested it");
- benefit before features, proof points before adjectives;
- no inherited hype: no "INSANE", "revolutionary" or "game-changing"
  unless a primary source quantifies it;
- short paragraphs, concrete nouns/verbs, one discussion prompt;
- visually: answer *what / why / proof* in the first screen, then
  progressively disclose detail.

## Telegram project post — the flagship

- **Budget:** hard Bot API limit 4,096 visible chars; formatter keeps
  a safety budget and trims features before hook/stats/links.
- **Layout:** large preview above text → emoji + name + hook → stats
  line (stars, forks, license, activity, language) → dual-use warning
  if needed → summary → key features → expandable deep dive
  (*Who should try it / Why it matters now / Verdict / Quick start*) →
  discussion question → links → star CTA → max 4 hashtags.
- **Tone:** energetic editorial, scannable, restrained emoji.
- **Links:** buttons carry GitHub / Full breakdown / Homepage, so the
  body does not need raw long URLs.

## Telegraph full breakdown — the deep dive

- **Layout:** standfirst hook → repository snapshot line → H2 article
  (*What it is / Why it matters / Key features / Quick start / Who
  should try it / Verdict*) → links → transparency note.
- **Tone:** calm reference article. It exists for Instant View from
  Telegram, not for search ranking.

## dev.to article of the day — the search surface

- **Title:** `Project: main task/use case`, search phrasing, no
  clickbait, about 125 characters maximum.
- **Layout:** TL;DR + Best for + repository snapshot in the first
  screen → article → Discuss section with the discussion question,
  repo/breakdown/Telegram links and a no-hands-on-test disclosure.
- **Tags:** maximum 4, `opensource` first, then language/category.
- **SEO decision:** no `canonical_url` to Telegraph. The dev.to
  version has its own TL;DR/discussion wrapper and should remain the
  indexable public article; Telegraph serves Telegram readers.
- **Series:** `Open Source Finds`.

## Bluesky — one idea

- **Budget:** 300 characters, enforced in code.
- **Layout:** `Name — concrete benefit` → one supporting detail →
  GitHub URL → max 2 hashtags. No emoji, no feature list.
- **Tone:** native and terse; the image carries the rest.
- **Accessibility:** clickable link *and* hashtag facets with UTF-8
  byte offsets; meaningful image alt text.

## Mastodon — community note

- **Budget:** 500 characters (built conservatively by raw length;
  Mastodon itself counts URLs as 23).
- **Layout:** lead → two feature bullets → `Repo:` and `Breakdown:`
  links → max 4 hashtags on their own line.
- **Tone:** open-source community register, less salesy than X-like
  surfaces.
- **Accessibility:** CamelCase hashtags (`#OpenSource`) for screen
  readers and descriptive media alt text.

## Facebook Page — plain-language story

- **Budget:** editorial target up to about 1,800 characters; the API
  allows far more, but readability wins.
- **Layout:** one-emoji title → proof line → dual-use note if needed
  → summary → *What stands out* bullets → *Why it matters* → *Good
  fit for* → quick start → question → GitHub/breakdown links → max 3
  hashtags.
- **Tone:** explanatory and welcoming for non-specialist followers;
  no Markdown, generous line breaks.

## AI Brief (Telegram) — verified news

- **Budget:** about 1,400–2,200 visible characters.
- **Visual:** Glass Aurora is reserved for this track only; if the
  upload fails, the YouTube preview is the fallback.
- **Layout:** factual headline → *What happened* → *Why developers
  should care* → *Confirmed vs. video-only* → credit line
  ("Spotted via WorldofAI; written from the primary source") →
  question. Buttons: Official source / Watch on WorldofAI.
- **Tone:** wire-service calm. Uncertainty is labelled, never smoothed
  over; rumors and sponsored items do not publish.

## Sunday digest + poll

- **Visual:** Editorial Daily "Sunday Edition" card.
- **Layout:** numbered Top 5, one entry as *name + stars* followed by
  its one-line hook; then a native poll containing **all five**
  projects as options.
- **Tone:** weekly newspaper recap, celebratory but factual.

## Alt text rule

Alt text is generated from facts, never from guessing pixels:
image kind (README demo / branded card / GitHub preview) + repository
+ one-line purpose + language/license/stars when known.

## Private-link rule

Public social copy never includes private test-channel `t.me/c/...`
links. During the test rollout, social adapters link to the GitHub
repo and the Telegraph breakdown instead.
