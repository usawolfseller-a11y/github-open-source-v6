# Roadmap — GitHub Open Source v6

Single source of truth for *what happens next*. Updated whenever a phase
closes. Everything here has an owner action or a measurable "done", because a
roadmap item without both is a wish.

**Last updated:** 2026-11-01 · **Owner:** Apex_Predator_X1 · **Builder:** agent

---

## 0. Decisions locked (owner, 2026-11-01)

| Decision | Choice | Consequence |
|---|---|---|
| Cadence | **3 posts a day** + weekly digest | Cron reduced from 4 slots to 3; collection unchanged |
| Polls | **Project of the Week only** | One poll per week, opened Sunday, closed Thursday (Telegram caps polls at 10 days) |
| Novelty | **Re-visit only on a milestone** | ≥ +50 % stars **or** a major release, and never inside a 90-day cooldown |
| Value signal | Views + reactions + votes. **No click tracking** | Owner rejected a third-party redirect domain: links must stay `github.com` |
| Publishing gate | Unchanged | Nothing goes to the main channel until the owner accepts a full test post |
| Card design | v6 editorial, brand icons, no ring | Frozen; changes only on owner request |

---

## 1. Where we are (verified, not assumed)

| Subsystem | State | Evidence |
|---|---|---|
| Discovery | 453 candidates/run, 7 sources live | `AUDIT_2026-11-02.md`, live run |
| Anti-duplication | Verified | `dedup.py`, tested |
| Views measurement | Verified live | widget returns real view counts |
| Polls | Built | `polls.py`, `stopPoll`, 96-hour cap |
| Value model | Built | `learn` writes clamped multipliers (0.85–1.15) |
| Click tracking | **Rejected by owner** | Links stay `github.com`; views + votes only |
| Facebook hand-off | **Built, off by default** | `sheets.py`, `facebook-handoff`, `docs/FACEBOOK_PIPELINE.md` |
| Cards | Verified on 3 edge cases | 1200×630, `editorial_daily` |
| Visual hosting | **Fixed 2026-11-02** | README image now re-hosted on ImgBB, not passed through |
| Per-surface bodies | **Built 2026-11-02** | 12 fields, Facebook and dev.to write their own |
| AI Brief | **Was dead, fixed 2026-11-02** | rejected 15/15 videos; now builds from a primary source |
| Social | Disabled by flag | **never sent live** — the one untested system |
| Production | **Not live** | test channel only, workflow disabled |

---

## 2. What the data says (facts that shaped the design)

Measured on the live channel, 2026-11-01:

- Median post: **224 views**; reactions exist on only **19 %** of posts; correlation of views ↔ reactions **0.14** → reactions alone cannot rank posts.
- Views accumulate for about a week then flatten. Measured: **12 views/h** at 1 h, **2.2/h** at 40 h, **0.7/h** at 250 h.
- Therefore the value score compares posts **at a 24-hour reference age**, not raw. Raw comparison would call every fresh post a flop and every old post a hit.
- The last 30 days trend **below** the four-month median (190 vs 222). Not enough data to call it a decline, but it is why cadence and selection quality are being tightened rather than increased.

---

## 3. Roadmap

### Phase A — Core correctness `[DONE this session]`
- [x] Anti-duplication: repo key, content fingerprints, similarity 0.55, 90-day cooldown
- [x] Milestone re-visits (stars ≥ +50 %, major release)
- [x] Views measurement from the public widget, verified live
- [x] Age-normalised value score (24 h reference)
- [x] Weekly poll: open Sunday, `stopPoll` Thursday, tally stored
- [x] `learn`: deterministic multipliers, clamped, written to state
- [x] 3-post schedule; two-command cron for close+learn
- [x] 98 tests green

**Exit criteria:** all tests pass, no change to publishing target. ✅

### Phase B — Prove it on the test channel `[NEXT, 5–7 days]`
- [ ] Run 5 consecutive days at 3 posts/day in the test channel
- [ ] Daily `metrics` run; confirm views land and the 24 h normalisation looks sane
- [ ] Sunday: digest + poll opens; Thursday: poll closes, tally stored
- [ ] `learn` produces a model with ≥ 10 samples; review the multipliers by hand
- [ ] Owner reads 3 cards and 3 posts and approves copy

**Exit criteria:** a full weekly loop with no manual intervention, and the owner's sign-off on copy.
**Owner action:** read the test channel once a day; flag any post whose hook lies.

### Phase C — Social crossposts, one at a time `[after B]`
Order is fixed by risk, not preference:

1. **dev.to** — canonical link back to Telegraph, no rate-limit risk.
2. **Bluesky** — 300-char budget; needs the card image as a blob upload.
3. **Mastodon** — 500-char budget, instance-level rate limits.
4. **Facebook** — *blocked*: needs a Page access token the owner does not have. Stays disabled until then; do not fake it with a user token.

- [ ] Smoke each platform with one real post, flags flipped one at a time
- [ ] Record failures as dead letters with the raw error

**Exit criteria:** each platform published at least one post from the queue, unattended.

### Phase D — Facebook via make.com `[ready, needs owner secrets]`
The Page is published today by make.com reading a Google Sheet. That chain
stays; v6 becomes its row producer (`ghos-v6 facebook-handoff`).

- [x] `sheets.py` row writer (same four columns the old script used) + `title`
- [x] `facebook_handoff_command` with idempotent `queued` marking
- [x] Post format audited; rewrite rules agreed in `docs/agents/FACEBOOK_REVIEW.md`
- [ ] Owner sets `GOOGLE_SERVICE_ACCOUNT_JSON`, `FACEBOOK_SHEETS_ID`,
      `FEATURE_SHEETS_HANDOFF=true`
- [ ] First real row → make.com picks it up → Page post appears
- [ ] Rewrite the text per the audit (faux-bold, duplicate opener, 7 features → 4)

**Exit criteria:** one post on the Page produced end-to-end without touching
the spreadsheet by hand.

### Phase E — Go live `[owner gate]`
- [ ] Private test channel approved post fixes a real defect
- [ ] Set `APP_ENV=production`, `PUBLISH_TARGET=main`, `TELEGRAM_MAIN_CHANNEL_ID`
- [ ] Re-enable the pipeline; watch the first three slots by hand
- [ ] Keep the rollback: flip `PUBLISH_TARGET=test` and the bot posts nowhere public

**Exit criteria:** three consecutive days in the main channel with zero duplicate posts and zero broken cards.

### Phase F — Growth experiments `[only after E]`
Ranked by expected value per hour of work:

1. **Post timing sweep** — the three slots are guesses; test one slot ±2 h for two weeks against the normalised view score.
2. **Hook A/B** — the same project, two hooks, split by time of day; the winner goes into the Gemini prompt as an example.
3. **Weekly digest depth** — Top 5 now; test Top 10 with one-line verdicts if engagement justifies it.
4. **"Tried it" poll** — a second weekly poll asking what readers actually ran. Adds a real usage signal, costs one poll per week.
5. **Language/category report** — publish what the channel covers, as a Telegraph page. Cheap credibility, also a discovery surface.

---

## 3.5. Next session, in order

1. **Prove one live crosspost.** This is the only subsystem never exercised
   against a real API. Post one existing record to Bluesky and to Mastodon,
   confirm the text and the image, then delete it if the account is public.
   Facebook cannot be proven this way: it goes through make.com.
2. **Run `doctor`** and confirm 13/13.
3. **Five days at three posts a day** in the test channel (Phase B), reading
   every post for a lying hook.
4. Only then Phase C (social, one platform at a time) and Phase E (go live).

Do not start with refactoring. `publish_slot` is 221 lines and should be
split, but not while the publishing path is unproven.

---

## 4. Explicitly rejected / not doing

- **Redirect domain for click tracking** (Cloudflare or any shortener): it would replace `github.com/...` with `go.example.dev/r/xxxx` in every post. Owner decision: not worth the loss of transparency.
- **MTProto user session** for `views`/`forwards` in real time: needs a phone number held by a bot, and risks the account. The public widget gives the same number 24 h later.
- **Retroactive polls**: the Bot API cannot create them; only a live poll produces a tally.
- **LLM-driven ranking weights**: the model stays deterministic and reviewable; a model that silently drifts is worse than no model.
- **Facebook without a Page token**: no workaround is honest here.
- **More than 3 posts a day** until the value curve shows the audience wants volume.

---

## 5. Risks and their honest mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Views wall for private channel | Cannot measure until the main channel is public | Test channel metrics stay unmeasured by design; use poll votes there |
| Cloudflare/KV not configured | No click data | Score falls back to views + votes; nothing breaks |
| `poll` edited by the owner mid-week | `stopPoll` may fail | Error is logged, active poll cleared, no partial data written |
| Value model overfits 10 samples | Wrong projects get boosted | Clamp 0.85–1.15, needs ≥ 5 samples, multipliers reviewed by hand |
| GitHub rate limits at 3 posts/day | Queue starves | Collection unchanged at 4 pages; runway 5 415 days |
| Duplicate slipping through via a fork | Embarrassing repost | Fork flag in the gate + description similarity + repo id |

---

## 6. Definition of done for the whole project

1. Three posts a day in the main channel for 30 days, unattended.
2. Zero duplicate repositories (audited from `state/events.jsonl`).
3. Weekly poll closed every week with a stored tally.
4. Value model refreshed weekly and reviewed at least twice.
5. Owner can answer "why was this project posted?" from `state.json` alone.

---

## 7. После аудита 2026-11-02

- **Ручное одобрение постов в Telegram на старте** (рекомендация H3). Кнопка
  «Одобрить» владельцу, публикация только после неё. Требует нового состояния
  и UI, поэтому вынесено отдельной задачей.
- **Изоляция декодирования картинок** (H1): отдельный процесс с таймаутом и
  лимитом памяти. Allowlist форматов и pixel cap уже закрывают основной риск.
- **State в отдельной ветке** или внешнем хранилище (M7/H2): сейчас state
  коммитится в `main` и проверяется перед коммитом. Отдельная ветка уберёт
  write-доступ к `main` из CI полностью.
- **Перевыпуск ключей** (M5) при переезде в боевой репозиторий.
