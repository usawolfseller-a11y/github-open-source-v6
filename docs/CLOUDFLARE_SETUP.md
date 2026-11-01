# Cloudflare: получить токен и поднять редирект-слой

Задача: считать переходы по ссылкам из постов. Telegram не отдаёт клики
никому, поэтому ссылка должна быть наша: `https://<домен>/r/<код>` → 302 →
GitHub. Считает клики Cloudflare, бесплатно.

Два пути. Первый — без своего домена (5 минут). Второй — на своём домене,
если он у вас есть в Cloudflare.

---

## Путь А — workers.dev, без домена

### 1. Включить Workers

1. Откройте [dash.cloudflare.com](https://dash.cloudflare.com) → войдите.
2. В левом меню **Workers & Pages**.
3. Если видите кнопку **Create** — Workers уже доступны.
4. Если просят выбрать план: **Workers Free** (100 000 запросов в день,
   карта не нужна).

### 2. Создать KV-хранилища (два штуки)

1. Workers & Pages → **KV** (в меню слева, ниже Workers).
2. **Create a namespace** → имя `ghs-repos` → Create.
3. Ещё раз → имя `ghs-stats` → Create.
4. Скопируйте **Namespace ID** у каждого (кнопка с иконкой копирования).

### 3. Создать Worker

1. Workers & Pages → **Create** → **Start with Hello World!** (или «Create Worker»).
2. Имя: `ghs-links` → Deploy.
3. **Edit code** → удалите шаблон → вставьте содержимое
   `infra/redirect/worker.js` из репозитория → **Deploy**.

### 4. Привязать KV и токен

1. В Worker → **Settings** → **Variables and Secrets**.
2. **Bindings** → **Add** → **KV namespace**:
   - Variable name: `REPOS` → namespace `ghs-repos`
   - Ещё раз: `STATS` → namespace `ghs-stats`
3. **Variables and Secrets** → **Add** → тип **Secret**:
   - Name: `STATS_TOKEN`
   - Value: длинная случайная строка. Сгенерируйте:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

4. **Deploy** заново, чтобы биндинги применились.

### 5. Проверить

Ваш адрес: `https://ghs-links.<ваш-субдомен>.workers.dev`

- Откройте `https://ghs-links.<...>.workers.dev/` — должно быть
  «GitHub Open Source redirect layer».
- Откройте `/stats?token=<ваш токен>` — должен вернуться `{}`.
- Откройте `/stats?token=неверный` — должен быть `403`.

### 6. Залить ссылки

Локально, в репозитории:

```bash
export REDIRECT_BASE_URL=https://ghs-links.<ваш-субдомен>.workers.dev
ghos-v6 links-export > /tmp/links.json
```

Дальше — залить `links.json` в namespace `REPOS`. Через CLI:

```bash
npm i -g wrangler
wrangler login
wrangler kv bulk put --binding=REPOS /tmp/links.json --remote
```

Или руками через дашборд: KV → `ghs-repos` → **Add entry** (по одной
паре `код` → `https://github.com/...`; при 100+ записях лучше через CLI).

### 7. Включить в системе

В GitHub-репозитории → **Settings** → **Secrets and variables** →
**Actions** → **Variables** → **New repository variable**:

| Имя | Значение |
|---|---|
| `REDIRECT_BASE_URL` | `https://ghs-links.<ваш-субдомен>.workers.dev` |

Всё. С этого момента новые посты используют редирект, а `metrics`
читает клики. Если что-то не так — удалите переменную, и всё вернётся к
прямым ссылкам на GitHub.

---

## Путь Б — ваш домен

Если домен уже обслуживается Cloudflare DNS:

1. Workers & Pages → ваш `ghs-links` → **Settings** → **Domains & Routes**.
2. **Add** → **Custom domain** → например `go.вашдомен.ru`.
3. Cloudflare сам создаст DNS-запись и сертификат (1–2 минуты).
4. `REDIRECT_BASE_URL=https://go.вашдомен.ru`.

Плюс домена: ссылка в посте выглядит как ваша, а не как служебный адрес
Cloudflare. Это заметно влияет на доверие к клику.

---

## Что важно знать

**Лимиты бесплатного плана.** 100 000 запросов в день (это не про клики,
а про все обращения) и 1 000 записей в KV в день. Один клик = одна запись.
При трёх постах в день и даже 300 кликах на пост это 900 записей —
впритык, но в пределах. Если упрётесь: либо переносите счётчик в Durable
Objects (платно от $5/мес), либо считайте только первый клик с устройства.

**Почему не считаем «просмотры ссылки» в самом Facebook.** Facebook даёт
Page Insights, но только по своим постам и только в интерфейсе; API
отдаёт ограниченный набор метрик и требует Page-токен, которого у нас нет.

**Честное ограничение редиректа.** Читатель видит не `github.com/...`, а
`go.вашдомен.ru/r/3ec69c85`, и переход становится на ~50 мс дольше. Если
это смущает — слой выключается одной переменной.

**Токен Cloudflare API** (не путать с `STATS_TOKEN` выше) нужен только если
хотите деплоить из CI. Тогда: My Profile → API Tokens → Create Token →
шаблон **Edit Cloudflare Workers** → сохранить как GitHub secret
`CLOUDFLARE_API_TOKEN` плюс `CLOUDFLARE_ACCOUNT_ID`. Для ручного деплоя
через `wrangler login` это не требуется.
