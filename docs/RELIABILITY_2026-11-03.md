# Надёжность и готовность к продакшену — аудит 3 ноября 2026

**Коммит-основа:** `cb45ebb` · **Проверено на:** Python 3.12.16 (версия CI) и 3.13.16 · **Итог после правок:** 196 тестов, coverage 66.83 %, ruff / mypy / secret-scan / gitleaks / pip-audit — чисто.

Этот документ объединяет два аудита: готовность к запуску в продакшен и работоспособность на горизонте 5+ лет. Раздел 3 перечисляет, что **исправлено в этом коммите**; раздел 4 — что осталось за рамками кода и требует решения владельца.

---

## 1. Что проверялось

| Проверка | Результат |
|---|---|
| Полный CI на Python 3.12.16 и 3.13.16 | ✅ 196 passed, ruff — чисто, mypy — 29 файлов без замечаний |
| `--require-hashes` для `requirements.lock` и `requirements-dev.lock` на 3.12 | ✅ все колёса найдены, хеши совпали |
| `pip-audit -r requirements.lock` | ✅ уязвимостей нет |
| `gitleaks detect --log-opts "--all"` (65 коммитов) | ✅ утечек нет |
| 13 кронов `pipeline.yml` ↔ маршруты `cli.py` | ✅ все имеют маршрут, мёртвых маршрутов нет |
| Fail-closed `publish` / `doctor` без секретов, `Unknown schedule` | ✅ exit 1, без publikаций, state не тронут |
| `state.json`, `events.jsonl` | ✅ валидны, битых строк нет |
| Сборка wheel и установка в чистое окружение | ✅ 142 PNG-ассета (было 0) |
| GitHub Actions API: workflow states, Variables, Secrets, runs, rulesets | ✅ проверено, значения секретов не читались |

---

## 2. Найденные проблемы

### Блокеры продакшена

1. **Проект сам запрещает публикацию с этого аккаунта.** `Publishing pipeline` и `Doctor` = `disabled_manually`; фазы B/C Roadmap и acceptance checklist не пройдены, кросспосты ни разу не отправлялись вживую. Требуется решение владельца и, по документации, отдельный аккаунт/репозиторий.
2. **Основной канал не резолвился.** В Variables была legacy `MAIN_TELEGRAM_CHANNEL`, а workflow передавал `vars.TELEGRAM_MAIN_CHANNEL_ID` (пустая строка). Воспроизведено: `APP_ENV=production` + `PUBLISH_TARGET=main` → `RuntimeError: TELEGRAM_MAIN_CHANNEL_ID is required`.
3. **Ключи требуют перевыпуска** при переезде в боевой репозиторий; присланный PAT имел права `admin`.

### Дефекты кода и сборки

4. **Wheel терял 142 PNG-иконки** — `pyproject.toml` не объявлял package data. В CI использовался `-e .`, поэтому дефект был невидим; при установке из wheel/Docker карточки тихо рендерились без фирменной графики.
5. **Еженедельный `learn` не запускался.** `pipeline.yml` использует `50 18 * * 4`, а пара `(close_poll, learn)` висела на старом кроне `10 18 * * 4`; по расписанию выполнялось только закрытие опроса.
6. **Покрытие критических модулей низкое:** `doctor.py` 13 %, `pipeline.py` 40 %, `telegram.py` 43 %, `platforms.py` 47 %, `Gemini.py` 52 % при общем 66 %.
7. **`state.json` рос без ограничения.** `published` — 10.5 КБ на запись, `seen_repos` — 227 Б на запись; ротация была только у `events.jsonl` и `views_history`. Оценка: ~20.5 МиБ/год → **~103 МиБ на 5-й год**, что упирается в лимит GitHub 100 МБ на файл. Для сравнения: у v5 есть `Keep Last 10 Published Posts Monthly`, поэтому его state остаётся маленьким.
8. **64.43 запуска в сутки** (`5,35 * * * *` = 48) → ~23 500 коммитов/год, ~117 600 за 5 лет; `commit-state` с `fetch-depth: 0` выполняется для каждого запуска.
9. **Внешние зависимости с коротким lifecycle:** `gemini-3.5-flash-lite` выключается не ранее 2027-07-21, Python 3.12 — EOL 2028-10-01, GitHub отключает schedule после 60 дней неактивности, `GITHUB_TOKEN` — 1000 запросов/час на репозиторий.
10. **Рассинхроны:** документация утверждала, что `TELEGRAM_OWNER_CHAT_ID` не задан (задан), расписание в RUNBOOK не совпадало с кодом, приватный ID тестового канала оставался в `cleanup.yml` и тесте, `license = {text=...}` deprecated, версии Python в pyproject/CI/lock различались, `doctor` показывал `FACEBOOK_PAGE_ACCESS_TOKEN: true` при отсутствующем токене.

### Долгосрочные изменения в оценке

По размеру `.git` репозиторий **не** переполнится: симуляция 2000 коммитов дала ~0.97 КБ на коммит в упакованном виде → ~0.11 GiB за 5 лет. Проблема не в объёме истории, а в одном файле `state.json` и во внешних сервисах.

Эмпирика действующего v5 (`donjon1212322/github-projects-bot`, 2802 runs, GitHub Free): `Billed amount $0` за 1–3 ноября при gross $0.04 / $0.03 / <$0.01. Год работы не исчерпал включённую квоту, поэтому первоначальная оценка «квота артефактов за 0.5–1 год» была **слишком пессимистичной**: триггер — не число запусков, а размер артефакта. `Publish to Platforms` у v5 работает (16 успешных из 18), но регулярно падает — это готовый эталон для непроверенных кросспостов v6.

---

## 3. Что исправлено в этом коммите

| # | Исправление | Где |
|---|---|---|
| 1 | Создана Actions Variable `TELEGRAM_MAIN_CHANNEL_ID` (значение скопировано из legacy без вывода); оба workflow дополнительно пробрасывают `MAIN_TELEGRAM_CHANNEL`; `config.py` читает оба имени | Actions Variables, `pipeline.yml`, `doctor.yml`, `.env.example` |
| 2 | `[tool.setuptools.package-data]` — wheel содержит 142 PNG; добавлен CI-шаг, проверяющий наличие ассетов | `pyproject.toml`, `ci.yml` |
| 3 | Четверговый крон `50 18 * * 4` выполняет `close_poll` **и** `learn`; мёртвый маршрут удалён; добавлены тесты на все 13 кронов и на пару | `cli.py`, `tests/test_scheduled_routes.py`, `test_value_system.py` |
| 4 | Компактирование состояния: `seen_repos` TTL 180 дней, полные записи `published` старше 90 дней заменяются лёгким индексом, `history` ≤ 5, списки `dead_letters` / `news_topics` / `poll_history` ≤ 500. **Ключи `published` не удаляются**, поэтому guard `commit-state` не срабатывает; дедуп сохраняет `repo_id`, `description_fp`, `readme_fp`. Идемпотентно | `state.py`, `tests/test_state_compaction.py` |
| 5 | Новый `Lifecycle guard` (еженедельно, без публикаций): размер `state.json` > 10 МиБ, отсутствие активности > 45 дней, исчезновение `GEMINI_MODEL` из списка моделей → автоматический issue. Issue создаёт активность и нейтрализует правило 60 дней | `.github/workflows/lifecycle.yml` |
| 6 | `doctor` честно сообщает об отсутствии `FACEBOOK_PAGE_ACCESS_TOKEN` и проверяет, что настроенная модель Gemini ещё доступна (иначе `ok: false`, а не тихий `gemini_unavailable`) | `doctor.py` |
| 7 | CI-шаг «State size guard» (10 МиБ); порог покрытия поднят 60 → 65 | `ci.yml`, `pyproject.toml` |
| 8 | CI и все workflow переведены на Python 3.13 (-lock скомпилирован на 3.13); `ruff`/`mypy` target `py313`; `license = "MIT"` + `license-files` вместо deprecated table | `*.yml`, `pyproject.toml` |
| 9 | Приватный ID тестового канала удалён из `cleanup.yml` и теста; хардкод заменён на Variable и синтетическое значение | `cleanup.yml`, `test_audit_round5.py` |
| 10 | Документация синхронизирована: расписание, число тестов, статус Variables, долгосрочная эксплуатация, план миграции Python и модели | `README.md`, `HANDOFF.md`, `RUNBOOK.md`, `SECURITY.md`, `ROADMAP.md`, `OPERATIONS.md`, этот файл |

**Эффект компактирования:** вместо ~103 МиБ на 5-й год state оценивается в **~12 МиБ** (≈6 МиБ `published` + ≈5 МиБ `seen_repos` + queue/списки). Оценка верхняя: предполагает 120 уникальных репозиториев в день.

---

## 4. Что НЕ исправлено и требует владельца

- ~~`pipeline.yml` и `doctor.yml` по-прежнему `disabled_manually`, включать нельзя без письменного решения.~~ **Снято владельцем 2026-11-03:** «публикацию разрешаю и все запреты снимаю». Workflow теперь разрешено включать; документация обновлена. Target lock и fail-closed при пустом тестовом ID сохраняются.
- Не пройдены acceptance-пункты: 3–5 дней автономных тестовых постов, живой кросспост Bluesky и Mastodon, dev.to smoke article, еженедельный отчёт владельцу, остановка старого бота v5 в день переключения.
- ~~Не заданы `FACEBOOK_PAGE_ACCESS_TOKEN` / `FACEBOOK_PAGE_ID`.~~ **Снято
  2026-11-03:** прямой Facebook Graph API удалён из рабочего контура, эти
  переменные и `FEATURE_FACEBOOK` больше не нужны и не читаются. Для Facebook
  остаётся только make.com-hand-off: не хватает Secret
  `GOOGLE_SERVICE_ACCOUNT_JSON` и Variables `FACEBOOK_SHEETS_ID`,
  `FACEBOOK_SHEETS_RANGE`, `FEATURE_SHEETS_HANDOFF`; таблицу надо расшарить
  на e-mail сервисного аккаунта, а сценарий make.com включить.
- Значения секретов не читались; живые вызовы Telegram / Gemini / ImgBB / Telegraph / соцсетей не выполнялись. YouTube RSS даёт 404 из сэндбокса, но контрольный чужой канал тоже 404 — это ограничение сети, не доказанный дефект.
- PAT, использованный для аудита, должен быть отозван сразу после завершения работ.
- Архитектурный пункт из `ROADMAP.md` — вынести state в отдельную ветку/хранилище и убрать `fetch-depth: 0` из `commit-state` — **не реализован**: он меняет механизм записи состояния и требует отдельного прогона в Actions. Компактирование снимает остроту, но не заменяет этот шаг.

---

## 5. Эксплуатационный чек-лист (раз в месяц)

1. `Lifecycle guard` не открыл новый issue; `state/state.json` < 10 МиБ.
2. `GEMINI_MODEL` всё ещё доступен; до июля 2027 запланировать миграцию (Firebase AI Logic: <https://firebase.google.com/docs/ai-logic/models>).
3. До октября 2028 перевести CI на поддерживаемую версию Python и пересобрать lock (<https://www.python.org/downloads/>).
4. Dependabot PR слиты; `pip-audit` чист; зафиксированные SHA Actions актуальны.
5. Резервный хостинг изображений и источник AI Brief на случай изменения бесплатных тарифов.

---

## 6. Источники лимитов

- GitHub: рекомендуемо < 1 ГБ, настоятельно < 5 ГБ, жёстко 100 МБ на файл — <https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github>
- `GITHUB_TOKEN`: 1000 запросов/час на репозиторий — <https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api>
- Отключение scheduled workflows после 60 дней неактивности — <https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule>
- Lifecycle `gemini-3.5-flash-lite` — <https://firebase.google.com/docs/ai-logic/models>, <https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions>
- Python 3.12 EOL — <https://peps.python.org/pep-0693/>

---

## 7. Второй проход 2026-11-03: тесты «как задумано»

Владелец разрешил публикацию и снял все запреты, поставив задачу «чтобы всё
работало как задумано и мы смогли запустить в продакшен». Ключевой вывод
предыдущего разговора: **100 % покрытия строк не является гарантией**. Замер
показал 66.83 % строк и лишь 63.01 % с учётом ветвей; мини-мутационный тест
выявил 7 выживших из 13 поломок при зелёном CI. Поэтому добавлен не «ещё
процент покрытия», а слой, который кодирует намерение.

### Что добавлено

| Файл | Что проверяет |
|---|---|
| `tests/test_owner_rules.py` | Решения владельца как инварианты: 3 поста в день (в коде, доках, cron и поведении), 90 дней кулдауна, 2000 строк events, TTL 180/90, caps 5/500, Telegraph по умолчанию включён, модель Gemini, карточки 1200×630, текстовый пост с большим превью, прямые ссылки, один лучший кросспост в сутки, Facebook только через make.com, разные SEO-углы |
| `tests/test_state_properties.py` | 40 сгенерированных состояний: ни один ключ `published` не теряется, индекс сохраняет поля, списки и `history` ограничены, компактирование идемпотентно; 200 случайных пар текстов для симметрии `similarity`; 50 сгенерированных постов в лимите 4000 UTF-16 |
| `tests/test_contract_artifacts.py` | Имена `os.getenv` из `config.py` ⊆ `.env.example` ⊆ workflow; Python 3.13 везде; 142 PNG в package-data; 13 cron ↔ 13 маршрутов; guards `commit-state`; docs не противоречат решению владельца |
| `tests/test_client_failures.py` | Фейковые клиенты: Telegram `ok:false` и пустой токен, ретраи 429/503, редактирование секретов, список моделей Gemini, зелёный и красный `Doctor` (модель выведена из эксплуатации → `ok:false`) |
| `tests/test_config_edges.py`, `tests/test_http_edges.py` | Граничные ветви `_bool`/`_int_or_none`/`_csv`, target lock, ссылки, SSRF-проверки URL, ретраи и пустые ответы |
| `tools/mutation_check.py` | 18 намеренных дефектов по одному; каждый должен «убить» набор тестов. Без новых зависимостей, поэтому хешированные lock-файлы не менялись |

### Найденный и исправленный дефект

Property-тест обнаружил, что `StateStore._compact_state()` ограничивал
`history` до 5 элементов **только у старых** записей `published`: у свежего
проекта с несколькими revisit список рос неограниченно. Теперь ограничение
применяется ко всем записям, а изменение учитывается в `changed` и пишет
`state_compacted` в `events.jsonl`.

### Метрики после второго прохода

- **284 теста**, все зелёные; `ruff`, `mypy`, `secret-scan` чисты.
- **65.53 % branch-inclusive** (69 % строк, 55 % ветвей) при пороге
  `--cov-fail-under=65` с включённым `--cov-branch`. Порог не понижался.
- **18/18 мутаций убито** (было 7 выживших из 13). Mutation gate добавлен
  в `ci.yml` и в локальный чек-лист `RUNBOOK.md`.
- Wheel по-прежнему содержит 142 PNG; `state.json` 153465 B не менялся.

### Что это не доказывает

Тесты доказывают согласие кода, конфигурации и документации с зафиксированными
решениями владельца. Они **не** заменяют живые интеграции, 3–5 дней
автономных постов, визуальную приёмку карточек и кросс-постов, одобрение копи
владельцем и мониторинг в проде. Чек-лист в `RUNBOOK.md` остаётся открытым.
Список оставшихся решений владельца — в разделах 4–5 выше.

---

## 8. Живой прогон 2026-11-03 после снятия запретов

Владелец разрешил публикацию и выбрал режим «тестовый канал → затем прод».
На момент запуска: `APP_ENV=test`, `PUBLISH_TARGET=test`,
`GEMINI_MODEL=gemini-3.5-flash-lite`, `FEATURE_TELEGRAPH=true`, остальные
опциональные флаги выключены. Присутствуют 7 Secrets;
`FACEBOOK_PAGE_ACCESS_TOKEN` и `GOOGLE_SERVICE_ACCOUNT_JSON` не заданы
(эти подсистемы выключены). `TELEGRAM_MAIN_CHANNEL_ID` — публичный username и
не совпадает с ID тестового канала.

| Проверка | Результат |
|---|---|
| CI на `7e7f26e`: ruff, mypy, 284 теста, branch coverage, mutation gate, secret scan, wheel (142 PNG), state guard | **success** |
| CodeQL, gitleaks | success |
| `Doctor` с `--hello` | **success**: бот — админ тестового канала, приветствие отправлено, Gemini-модель доступна (46 моделей), GitHub search, карточка `neon_terminal`; единственный `ok:false` — ожидаемый пропуск Facebook без Page-токена |
| `publish` (`slot=smoke_e2e`) | **success**: `"published": true`, Telegraph-страница создана, `published` 4 → 5, `commit-state` закоммитил state |
| `collect`, `crossposts`, `article`, `news`, `metrics`, `learn`, `moderation`, `facebook-handoff`, `poll-close`, `report` | **10/10 success** |
| Состояние workflow | `Doctor`, `Publishing pipeline`, `CI`, `CodeQL`, `Lifecycle guard`, `Cleanup test posts` — `active` |
| `state.json` на `main` | `published=5`, `queue=28`, `seen_repos=209`, `dead_letters=0` |

**Операционная находка.** `concurrency: group: state-writer,
cancel-in-progress: false` в GitHub Actions допускает только один
выполняющийся и один ожидающий запуск. Пакет из 10 одновременных
`workflow_dispatch` дал 8 `cancelled` (не отказ кода); при последовательном
повторе все команды завершились success. Правило: ручные dispatch отправлять
по одному и дожидаться завершения.

**Что остаётся за владельцем (живая приёмка, а не автотесты):** визуальная
проверка поста и карточки в тестовом канале, 3 дня автономных постов по 3
в день, воскресный дайджест и опрос (`learn` уже прошёл, но `value_model`
появится только после данных опроса), живой кросспост Bluesky/Mastodon,
dev.to smoke article, Facebook-handoff после добавления Secrets/Variables,
переключение трёх Variables на `production`/`main`, остановка v5 в день
переключения и отзыв временного PAT.
