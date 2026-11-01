# Facebook: как это устроено и что мы меняем

## Что есть сейчас (ваша рабочая схема, не трогаем)

```
github-projects-bot
   └─ formated_facebook.py  →  data/facebook_posts.json
        └─ google_sheets.py (сервисный аккаунт Google)
             └─ Google Sheet: project_id | content | platform | media_urls
                  └─ make.com → Facebook Page
```

Схема рабочая и бесплатная. Единственное, что в ней плохо — **текст**
(см. `docs/agents/FACEBOOK_REVIEW.md`: faux-bold, дубли, 6 разделителей,
7 фич, «0 open issues», картинка — авто-карточка GitHub).

## Что делает v6

v6 не заменяет make.com. Он становится **поставщиком строк** в ту же
таблицу — тем же сервисным аккаунтом, в те же колонки:

```
ghos-v6 publish        → пост в Telegram + карточка 1200×630
ghos-v6 facebook-handoff → строка в Sheet  → make.com → Facebook Page
```

Почему так, а не напрямую через Graph API:

| | Hand-off в Sheet + make.com | Прямой Graph API из v6 |
|---|---|---|
| Токен | не нужен (сервисный аккаунт уже есть) | нужен Page-токен, которого нет |
| Ретраи | делает make.com | писать самим |
| Вы уже умеете | да | нет |
| Картинка | URL из колонки `media_urls` | нужен публичный хост |

Поэтому основной путь — hand-off. Прямой `FacebookClient` в v6 остаётся
на случай, если Page-токен когда-нибудь появится.

## Колонки

| Колонка | Что | Откуда |
|---|---|---|
| `project_id` | `repo_id`, иначе `full_name` | запись публикации |
| `content` | готовый текст поста | `content_adapters.build_Facebook_text` |
| `platform` | `facebook` | константа |
| `media_urls` | URL карточки 1200×630 | `image_url` записи |
| `title` | короткое имя проекта (новая, для сценариев, которым нужен заголовок) | `name` |

Первые четыре колонки **совпадают** с тем, что писала старая схема, —
существующий сценарий make.com продолжит работать без правок.

## Включение

1. Убедитесь, что сервисный аккаунт имеет доступ на редактирование к
   таблице (тот же, что сейчас пишет из `google_sheets.py`).
2. GitHub → Settings → Secrets and variables → Actions:
   - **Secret** `GOOGLE_SERVICE_ACCOUNT_JSON` — JSON сервисного аккаунта целиком.
   - **Variable** `FACEBOOK_SHEETS_ID` — id таблицы.
   - **Variable** `FACEBOOK_SHEETS_RANGE` — лист и ячейка, по умолчанию `facebook!A1`.
   - **Variable** `FEATURE_SHEETS_HANDOFF=true` (по умолчанию выключено).

`FACEBOOK_PAGE_ACCESS_TOKEN` для этой схемы **не нужен**: в Facebook
публикует make.com, а v6 только пишет строку в таблицу. Токен остаётся
необязательным для прямого `FacebookClient` и по умолчанию выключен
(`FEATURE_Facebook=false`) — если когда-нибудь захочется публиковать мимо
make. Пока переменная пустая, ничего не ломается и в логах тишина.
3. Проверка без публикации:

```bash
ghos-v6 facebook-handoff --limit 1
```

Команда вернёт `{"queued": 1, "range": "facebook!A5:F5", ...}` и запишет
строку. make.com подхватит её как обычно.

## Гарантии

- **Падение Sheets не ломает Telegram.** Ошибка логируется в
  `events.jsonl` как `facebook_handoff_failed`, публикация в канал
  продолжается.
- **Никаких двойных публикаций.** Запись получает
  `crossposts.facebook_sheet.status = "queued"`, повторный запуск её не
  выберет.
- **Выключено по умолчанию.** Без `FEATURE_SHEETS_HANDOFF=true` команда
  отвечает `feature_disabled` и ничего не пишет.

## Что нужно решить вам

Сейчас `media_urls` берётся из `image_url` записи. Для постов, где картинка
хостилась локально (ImgBB), это публичный URL — годится. Но у самых первых
записей там `opengraph.githubassets.com`, то есть та самая авто-карточка
GitHub, которую мы хотим заменить. После включения ImgBB-хостинга в
пайплайне (он уже есть, `media_host.py`) в таблицу пойдёт наша карточка.
