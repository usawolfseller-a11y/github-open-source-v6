# Эксплуатация

Что делать каждый день, что делать, когда сломалось, и как откатить.

---

## Ежедневно (2 минуты)

1. Открыть канал, посмотреть три поста.
2. Проверить, что превью отображается (значит ImgBB жив).
3. Если пост выглядит не так — `state/events.jsonl`, последние строки.

Ничего запускать руками не нужно: 12 кронов делают всё сами.

---

## Еженедельно

| Когда | Что смотреть |
|---|---|
| Вс 16:10 | дайджест топ-5 и опрос — открылись? |
| Чт 18:10 | опрос закрылся, `learn` пересчитал модель |
| Вс 16:40 | отчёт владельцу пришёл в личку |
| Любой день | `value_model` в `state.json` — не выродился ли |

---

## Диагностика

### Первым делом

```bash
set -a; . .env.local; set +a
PYTHONPATH=src python3 -m ghos_v6.cli doctor
```

13 проверок, ничего не меняют. Если что-то отвалилось — видно сразу.

| Проверка | Что ловит |
|---|---|
| `env_presence` | не хватает переменной |
| `telegram_get_me` | токен бота мёртв |
| `telegram_discovery` | бот не админ канала |
| `Gemini_models` / `Gemini_generate` | квота или ключ |
| `GitHub_search` | токен GitHub |
| `worldofai_rss` | канал сменил RSS |
| `telegraph`, `devto`, `bluesky`, `mastodon`, `Facebook` | токены площадок |
| `card_render` | Pillow или шрифты |

### Частые поломки

**Пост не вышел.**
```bash
tail -20 state/events.jsonl | grep publish
```
`no_candidate` → очередь пуста, `collect` не отработал.
`daily_limit_reached` → норма, лимит 3.
`all_candidates_rejected` → гоут отсёк всех, смотреть `rejections`.

**Превью не отображается.**
Проверить `IMGBB_API_KEY`. Если пуст — карточка не загрузится, пост уйдёт
без превью с записью в лог. Telegraph — резерв, но он хуже.

**AI Brief молчит.**
```bash
PYTHONPATH=src python3 -m ghos_v6.cli news --force
```
В ответе `rejections` — по каждой причине. Если `sponsored` — проверить,
не изменился ли формат спонсорской строки у канала.

**Кросс-посты не уходят.**
Проверить `FEATURE_BLUESKY` / `FEATURE_MASTODON` / `FEATURE_Facebook`.
Потом `crossposts.*.status` в записи поста: `pending` → `sent` или
`dead_letter`.

**Дубликат в канале.**
`dedup.check` пропустил. Смотреть `seen_repos` по этому проекту.
Причина обычно — изменился README и отпечаток не совпал.

---

## Инциденты

### Опубликован плохой пост

Telegram-канал: удалить сообщение руками. Бот не умеет отзывать.
Затем пометить в состоянии:
```bash
PYTHONPATH=src python3 -c "
import json,pathlib
p=pathlib.Path('state/state.json'); d=json.loads(p.read_text())
d['published']['owner/repo']['removed_by_owner']=True
p.write_text(json.dumps(d,ensure_ascii=False,indent=1))
"
```

### Утёк секрет

1. Отозвать токен у провайдера **сразу**.
2. Заменить в Settings → Secrets.
3. `python3 tools/secret_scan.py` — проверить репозиторий.
4. Секреты никогда не печатать в чат.

### Публикация ушла не в тот канал

`Config.telegram_chat_id` не откатывается молча на основной. Если это
случилось — значит `TELEGRAM_TEST_CHANNEL_ID` был пуст, и код должен был
упасть, но не упал. Проверить `config.py`.

### GitHub Actions не запускаются

Проверить, не `disabled_manually`:
```bash
gh api repos/{owner}/{repo}/actions/workflows
```
**На тестовом аккаунте они должны оставаться выключенными.**

---

## Откат

### Откатить пост-формат

Форматтер — `formatter.py::format_project_post`. Вернуть прошлую версию:
```bash
git log --oneline -- src/ghos_v6/formatter.py
git revert <commit>
```

### Откатить всю публикацию

```bash
APP_ENV=test
PUBLISH_TARGET=test
```
Публикация в основной канал прекратится немедленно, тестовый продолжит
работать. Это штатный способ.

### Откатить состояние

`state/state.json` в гите, история коммитов `chore(state):`.
```bash
git log --oneline -- state/state.json | head
git checkout <commit> -- state/state.json
```
Осторожно: откат вернёт проекты в очередь, и они могут выйти повторно.

---

## Продление и лимиты

| Ресурс | Лимит | Расход | Запас |
|---|---|---|---|
| Gemini | 1000 запросов/день | 27 | 37× |
| GitHub API | 5000/час | ~100 на сбор | большой |
| ImgBB | без жёсткого лимита | 3–4 загрузки/день | — |
| Telegram | 30 сообщений/сек | 3/день | — |

Если Gemini начнёт упираться — первым делом сокращать не посты, а вызов
поверхностей (сделать его раз в день на лучший пост).

---

## Что делать НЕЛЬЗЯ

- Включать `pipeline.yml` / `doctor.yml` на тестовом аккаунте.
- Печатать значения секретов в логи или чат.
- Менять `APP_ENV`/`PUBLISH_TARGET` без прохождения приёмки из `RUNBOOK.md`.
- Править `state/state.json` руками при работающих кронах — перезапишут.
- Отключать `concurrency` в workflow — кроны начнут перезаписывать состояние.
