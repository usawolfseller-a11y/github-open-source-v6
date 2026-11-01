# Format audit v2 — findings and fixes

This audit was run before enabling public crossposts. The review
panel covered UI design, UX architecture, brand consistency, growth,
persona walkthrough/scanning behaviour and community engagement.
The owner found three visible problems; the panel found several
more. All format changes below are deterministic: no second LLM call
and no new facts are invented.

## P0 — growth loop

| Finding | Fix |
|---|---|
| Bluesky/Mastodon/Facebook copy sent readers to GitHub/Telegraph but did not reliably bring them back to Telegram. | Every external adapter now has a Telegram return CTA. A public post link is labelled **Discuss**; during private-channel testing it falls back to the public channel as **Daily picks**. Private `t.me/c/...` links are still filtered out. |
| The Telegram post asked readers to star somebody else's repository, exporting the value of our audience; even the GitHub button used a ⭐ icon. | Removed. The flagship rotates **React**, **Forward** and **Save + comment** asks on our own post, and the button is now a neutral 🔗 GitHub link. |
| dev.to put Telegram last in the footer, after the reader had already left. | dev.to has a daily-picks line in the first-screen wrapper and puts the Telegram discussion/follow link first under **Discuss**. |
| Telegraph ended in a generic “Links” list. | It now has a follow line near the top, a **Continue exploring** section, Telegram first, and a “Get the next pick” CTA at the end. |

## P1 — scanning and visual hierarchy

| Finding | Fix |
|---|---|
| Name, hook, stats and links were compressed into dense single lines; the five-second *what/why/proof* test was weak. | Telegram v2 separates header, bold hook, divider, star/fork proof line, stack/activity line and contributors line. |
| The `owner/repo` path was hidden behind links/buttons, so forwards lost the exact project identity. | The header shows `owner/repo` in code style beside the project name. |
| One generic 💻 icon represented every stack. | A shared language/stack icon map is used by Telegram, Bluesky, Mastodon and Facebook; the written language name remains present for accessibility. |
| Summary, hook and the first feature often repeated one another. | The Gemini prompt now forbids restating the hook in the summary and requires each feature to add a distinct capability or evidence point. |
| A useful one-line quick start was hidden inside the expandable deep dive. | Short commands are visible before the deep dive; longer/multi-line commands stay expandable. |
| Hashtags favoured niche repository topics and produced awkward tags such as `#SecurityAndAnalysis` and `#Typescript`. | Broad topics are prioritized; special casing and aliases produce `#TypeScript`, `#Security`, `#AI`, `#CLI`, and clean dev.to tags. The prompt also requires one short broad category. |
| dev.to could lose acronyms (for example `REA`) by deriving the title from the hook first. | A good generated article title is now preferred when it fits. |
| Facebook had no real section hierarchy and its fallback could clip the ending. | Facebook uses dividers and labelled sections; the final question/CTA/link block is protected during fitting. |
| AI Brief trust depended on buttons, which disappear when a post is forwarded as text/screenshots. | The primary source is now linked in the body, with a divider, icon-led sections and a reaction CTA. |
| Sunday digest entries ran together and had no share loop. | Entries are separated, title/detail lines are split, and the post ends with a forward CTA before the poll prompt. |

## P1 — trust and discussion quality

| Finding | Fix |
|---|---|
| Dual-use warnings said “research/education” but did not state the authorization boundary plainly. | Telegram now adds: “Use only on software you own or are authorized to analyze.” |
| Discussion questions could require an expert mini-essay, suppressing comments. | The prompt asks for a specific one-line answer: a concrete use case or an either/or choice. |
| Sentence clipping in the Telegram and AI Brief formatters could cut a word and append misleading punctuation. | Both clippers now prefer a complete sentence, otherwise backtrack to a word boundary and use an ellipsis. |

## Found by the first private v2 test

The first actual v2 test post exposed one more tag-quality flaw:
repository order surfaced `#antidetect #antidetect_browser` for a
browser-engine project. That private post was left as evidence, but
the code was fixed before any public use: the generated broad
category now feeds Telegram hashtags, browser/automation topics are
prioritized, the same evasion terms are blocked in social/dev.to
tags, and browser projects use the 🌐 category icon instead of the
generic 🚀 fallback.

## Deliberately deferred

- **README screenshot vs branded card:** the media cascade remains
  README demo → branded card → Open Graph. Dense screenshots can be
  less legible than cards, but authentic demos are valuable evidence;
  changing the cascade needs owner-approved examples, not a silent
  formatting patch.
- **Native reaction/view metrics:** the Bot API pipeline does not yet
  ingest per-post views/reactions. CTA variants are deterministic so
  they can be compared once metrics collection is added.
- **Public smoke order:** format v2 still publishes to the private
  test channel first. dev.to, Bluesky and Mastodon are smoke-tested
  one by one only after the owner accepts the new samples; Facebook
  remains blocked until a real Page token exists.
