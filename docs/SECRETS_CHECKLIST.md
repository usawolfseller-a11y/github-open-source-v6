# Что ещё нужно дать проекту и где это взять

**Дата:** 2026-11-03 · **Репозиторий:** `usawolfseller-a11y/github-open-source-v6`

Коротко: для полного цикла не хватает **ровно одного секрета** и **двух
переменных** — всё это относится к Facebook, который публикует make.com из
Google-таблицы. Остальные 6 секретов уже настроены и работают (Telegram,
Gemini, ImgBB, Telegraph, dev.to, Bluesky).

> ⚠️ Не присылайте значения секретов в чат и не сохраняйте их в файлах
> проекта. Добавляйте их прямо в GitHub → Settings → Secrets and variables →
> Actions. Мне достаточно написать «добавил» — я включу флаг и проверю
> прохождение строки до таблицы.

---

## 1. `GOOGLE_SERVICE_ACCOUNT_JSON` — **Secret**

Это JSON-ключ сервисного аккаунта, который дописывает строки в таблицу.

**Где взять:**

1. Откройте <https://console.cloud.google.com/> и создайте проект
   (например `ghos-v6-sheets`) или выберите существующий.
2. **«API и службы» → «Включить API и сервисы»** → найдите
   **Google Sheets API** → **Включить**. Без этого будет `403/404` при записи.
3. **«IAM и администрирование» → «Сервисные аккаунты» →
   «Создать сервисный аккаунт»**. Имя, например `ghos-sheets-writer`.
   Роль на уровне проекта давать **не обязательно** — доступ выдаётся
   точечно на саму таблицу на шаге 4. Нажмите «Готово».
4. Откройте созданный аккаунт → вкладка **«Ключи»** →
   **«Добавить ключ» → «Создать новый ключ» → JSON** → скачать.
5. Из файла скопируйте значение `client_email` (вида
   `ghos-sheets-writer@....iam.gserviceaccount.com`) — оно нужно для шага 4.
6. Превратите JSON в **одну строку**:

   ```bash
   python -c "import json;print(json.dumps(json.load(open('key.json'))))"
   # или: jq -c . key.json
   ```

7. GitHub → **Settings → Secrets and variables → Actions → Secrets →
   New repository secret**:
   - **Name:** `GOOGLE_SERVICE_ACCOUNT_JSON`
   - **Secret:** вставьте одну строку из п. 6
   - **Add secret**

8. Удалите скачанный `key.json` с компьютера. Если ключ где-то засветился —
   в «Ключах» удалите его и создайте новый, затем обновите Secret.

**Как проверить:** `ghos-v6 facebook-handoff --limit 1` (или workflow
`Publishing pipeline` → `command=facebook-handoff`). В логах должно быть
`queued: 1`, в state — событие `sheet_row_queued`, а в таблице — новая строка.
Ошибка `sheets_not_configured` = не задан Secret или id таблицы;
`google_libs_missing` = не установились зависимости (в CI они есть в
`requirements.lock`).

---

## 2. `FACEBOOK_SHEETS_ID` — **Variable**

**Где взять:** откройте нужную Google-таблицу и посмотрите на адрес:

```
https://docs.google.com/spreadsheets/d/1AbCdEf...XyZ/edit#gid=0
                                      └────── это ID ──────┘
```

Скопируйте часть между `/d/` и `/edit`. Это не секрет, поэтому идёт в
**Variables** (не в Secrets):

- **Name:** `FACEBOOK_SHEETS_ID` · **Value:** скопированный ID.

---

## 3. `FACEBOOK_SHEETS_RANGE` — **Variable** (необязательно)

Имя вкладки внизу таблицы + `!A1`. Например, если лист называется
`facebook` → `facebook!A1`; если `Posts` → `Posts!A1`.

В коде уже стоит дефолт `facebook!A1` (`sheets.DEFAULT_RANGE`), поэтому если
ваш лист так и называется — переменную можно **не создавать**. Если называется
иначе, создайте Variable `FACEBOOK_SHEETS_RANGE` со своим значением.

Колонки, которые читает make.com (порядок сохранён от старой схемы):

| A | B | C | D | E |
|---|---|---|---|---|
| `project_id` | `content` | `platform` | `media_urls` | `title` |

---

## 4. Доступ сервисного аккаунта к таблице

Обязательный шаг, без него запись упадёт с `403 Permission denied`:

1. В таблице **«Настройки доступа» / Share**.
2. Вставьте `client_email` из п. 1.5.
3. Роль **«Редактор»** (Editor) → **Отправить**. Галочку «уведомить» можно
   снять — сервисному аккаунту письмо не нужно.

---

## 5. Сценарий make.com

Находится вне этого репозитория и настраивается владельцем:

1. Модуль **Google Sheets → Watch New Rows** (или Search Rows) на таблицу и
   диапазон из п. 2–3.
2. Модуль **Facebook Pages → Create a Post**: `message` ← колонка B
   (`content`), картинка ← D (`media_urls`), при необходимости заголовок ← E.
3. Сопоставьте колонки A–E по таблице выше.
4. Включите сценарий (**ON**) и проверьте, что подключение Facebook в make.com
   авторизовано на нужную Page.

> **Важный нюанс:** токен Facebook Page нужен **внутри make.com** (там он
> живёт в авторизованном соединении). В нашем репозитории он **не нужен**:
> `FACEBOOK_PAGE_ACCESS_TOKEN`, `FACEBOOK_PAGE_ID` и `FEATURE_FACEBOOK`
> удалены 2026-11-03, прямой Graph API из v6 убран.

---

## 6. `FEATURE_SHEETS_HANDOFF` — **Variable**, включает сам агент

После того как секрет, id и доступ есть: создайте/измените Variable
`FEATURE_SHEETS_HANDOFF=true`. До этого команда `facebook-handoff` — безопасный
no-op (`queued: 0`), ничего не ломает.

Скажите мне «включено» — я поставлю флаг, прогоню `facebook-handoff`
последовательно (не в одном батче: у `concurrency: state-writer` максимум
один выполняющийся и один ожидающий запуск) и проверю, что строка дошла до
таблицы и её подобрал make.com.

---

## Чего давать **НЕ** нужно

| Имя | Почему |
|---|---|
| `FACEBOOK_PAGE_ACCESS_TOKEN`, `FACEBOOK_PAGE_ID`, `FEATURE_FACEBOOK` | удалены: Facebook публикует make.com |
| `MASTODON_ACCESS_TOKEN`, `MASTODON_INSTANCE_URL`, `FEATURE_MASTODON` | удалены: аккаунт заблокирован за спам 2026-11-03 |
| `TELEGRAM_MAIN_CHANNEL_ID` | уже `@GitHub_Open_Source` |
| `BLUESKY_APP_PASSWORD`, `DEV_API_KEY`, `TELEGRAPH_ACCESS_TOKEN`, `IMGBB_API_KEY`, `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN` | уже заданы, живые прогоны прошли |
| Любые значения Secrets в чат | добавляйте только через UI GitHub |

---

## После переключения в прод

1. Отзовите временный PAT: github.com → **Settings → Developer settings →
   Personal access tokens → Fine-grained tokens** → Revoke.
2. В день переключения остановите v5, чтобы два бота не писали в один канал.
3. Переключите три Variables одновременно: `APP_ENV=production`,
   `PUBLISH_TARGET=main`, `TELEGRAM_MAIN_CHANNEL_ID=@GitHub_Open_Source`.

Связанные документы: [`FACEBOOK_PIPELINE.md`](FACEBOOK_PIPELINE.md),
[`RUNBOOK.md`](RUNBOOK.md), [`SECURITY.md`](../SECURITY.md),
[`RELIABILITY_2026-11-03.md`](RELIABILITY_2026-11-03.md) §10.
