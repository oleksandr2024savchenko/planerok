# Planer — звіт для наступного агента

Двоосібний планер у Telegram для двох акаунтів. Живий сайт: https://planer.pp.ua. Бот: `@PlanerokUA_Bot`. Код: `/home/ubuntu/planer`. Часовий пояс усього бекенда і Mini App — `Europe/Vienna`. Відповідай користувачу українською. UI-зміни перевіряй у браузері на телефоні (близько 390×844) саме на https://planer.pp.ua. `http://127.0.0.1:3000` з браузера Cursor не відкривається. Поза Telegram заголовок `X-Telegram-Init-Data` порожній, тому API відповідає 401 — це очікувано, не баг продукту.

Не виводь секрети з `planer/.env` (токен бота, ключ Gemini, пароль Postgres) і не коміть `.env` чи `service_account.json`. Коміти й пуш лише коли користувач прямо просить.

## Хто користується

Лише ці два Telegram ID. Усі інші отримують відмову і в боті, і в API.

| Порядок у `ALLOWED_TELEGRAM_IDS` | Telegram ID | Тема | Google Calendar |
| --- | --- | --- | --- |
| перший | 969740172 | violet, `--void` `#12061f` | `savasashok@gmail.com` |
| другий | 729424163 | pink (світла), `--void` `#fff0f7` | `pelmenkotanya@gmail.com` |

Сервісний акаунт Google: `calendar-bot@planerok.iam.gserviceaccount.com`. Файл ключа на хості `planer/service_account.json`, у контейнері змонтований лише він: `/app/service_account.json`. Решта коду бекенда запечена в образ.

`ensure_allowed_users` у `backend/app/services/users.py` створює обох при старті і проставляє партнера навхрест. Календар записується в `users.google_calendar_id`, лише якщо поле ще порожнє. `"primary"` вважається непридатним і ігнорується. Тема другого акаунта примусово стає pink, якщо там досі violet. Першому violet не перезаписують.

## Як це запущено

Docker Compose у `/home/ubuntu/planer`. `env_file: .env` (файл у корені проєкту, не в `backend/`).

| Контейнер | Роль | Порт |
| --- | --- | --- |
| `planer-postgres` | Postgres 16, volume `postgres_data` | лише мережа Compose |
| `planer-redis` | Redis 7, лише FSM бота (aiogram) | лише мережа Compose |
| `planer-backend` | FastAPI + aiogram polling + APScheduler, один процес | `127.0.0.1:8000` |
| `planer-webapp` | статичний експорт Next.js 15 у nginx | `127.0.0.1:3000` |

Caddy (`/etc/caddy/Caddyfile`) віддає `planer.pp.ua`. Шляхи `/tasks`, `/calendar`, `/me`, `/webhooks`, `/health`, `/docs`, `/openapi.json` ідуть на бекенд. Усе інше — на вебзастосунок. Збірка вебзастосунка запікає `NEXT_PUBLIC_API_URL=https://planer.pp.ua` і `NEXT_PUBLIC_USE_MOCKS=false`.

Воркфлоу `.github/workflows/pages.yml` збирає той самий фронт з моками і порожнім API URL для GitHub Pages. Це не продакшен. Живий Mini App — Docker на цьому VPS. `WEBAPP_URL` у прикладі `.env` досі вказує на GitHub Pages; у бойовому `.env` має бути `https://planer.pp.ua`.

Бекенд не монтує вихідний код. Зміна Python або фронта не з’являється, доки образ не перезібрано:

```bash
cd /home/ubuntu/planer
docker compose up -d --build webapp
docker compose up -d --build backend
```

Автодеплой: systemd-таймер `planer-autodeploy.timer` щохвилини запускає `deploy/auto-deploy.sh`. Скрипт робить `git fetch` гілки `DEPLOY_BRANCH` (у юніті `claude/great-gates-uwg8kl`), підтягує її лише fast-forward і перезбирає тільки змінене: `backend/` → backend, `webapp/` → webapp, `docker-compose.yml` → обидва. Останній задеплоєний коміт лежить у `.git/planer-deployed`; якщо збірка впала, наступний тік повторить. Ручні правки в tracked-файлах на сервері блокують деплой (`.env` і ключі не tracked — не заважають). Логи: `journalctl -u planer-autodeploy -n 50`. Логи самого бекенда пишуться в journald хоста (`logging: driver: journald`, тег `planer-backend`), тому переживають перестворення контейнера: `sudo journalctl -t planer-backend --since "2 hours ago"` (`docker logs` бачить лише поточний контейнер). Тобто достатньо запушити в гілку — за хвилину-дві зміни на проді.

`alembic upgrade head` виконує `backend/docker-entrypoint.sh` при кожному старті бекенда. Зміна `.env` потребує `docker compose up -d --force-recreate backend`: звичайний restart змінні не перечитує. Працівник один (`uvicorn` workers=1), бо опитування бота і планувальник живуть у процесі.

## Бекенд

Корінь API без префікса `/api`. Залежності: `SessionDep`, `UserIdDep` у `backend/app/api/deps.py`. Користувач береться з валідного Telegram `initData` (заголовок `X-Telegram-Init-Data`) і має бути в allowlist. `DEV_USER_ID` пускає браузер без initData лише якщо цей id теж у allowlist. У проді його немає.

| Метод | Шлях | Сенс |
| --- | --- | --- |
| GET/POST | `/tasks` | список і створення. Список додає події ICS, якщо немає фільтра `category` |
| PATCH/DELETE | `/tasks/{id}` | свої задачі. Від’ємний id — лише `is_completed` події ICS |
| GET | `/calendar/status` | чи підключений Google і чи живий watch |
| GET/POST/DELETE | `/calendar/feeds` | підписки ICS. У відповіді host, не повний URL |
| GET | `/me` | `telegram_id`, `theme`, `partner_telegram_id` |
| POST | `/webhooks/google-calendar` | push Google |
| GET | `/calendar/oauth/start`, `/calendar/oauth/callback` | запасний OAuth; зараз працює сервісний акаунт |
| GET | `/health` | `{"status":"ok"}` |

Моделі (`backend/app/models.py`):

- `User` — PK `telegram_id`, партнер, календар, три години дайджесту (08:00, 14:00, 20:00), тема.
- `Task` — `user_id` і `owner_id`, `is_shared`, `assigned_to_id`, дедлайн, `remind_at`, `start_time`/`end_time`, `google_event_id`, `partner_google_event_id`, `sync_token`, `is_completed`.
- `ExternalCalendar` / `ExternalEvent` — підписка ICS і розгорнуті входження. У події є локальний `is_completed` (міграція `0005`).
- `GoogleCalendarState` — sync token і канал watch на календар.

Міграції: `0001` задачі, `0002` Google, `0003` користувачі й спільні задачі, `0004` зовнішні календарі, `0005` позначка виконання зовнішньої події, `0006` відносне нагадування `tasks.remind_before_minutes`, `0007` автор задачі `tasks.created_by_id` і `users.first_name`. Голова — `0007`.

Видимість задач (`tasks._visible_to`): свої як owner, user, assigned або **автор** (`created_by_id`), плюс спільні задачі партнера (`is_shared` і `owner_id == partner`). «Хто робить»: `assignee` у `TaskCreate`/`TaskUpdate` — `me` / `partner` / `shared`, відносно того, хто пише (`tasks._apply_assignee`). `partner` робить партнера owner/user/assigned, автор лишається в `created_by_id` і бачить задачу. При зміні власника чи спільності старі події Google видаляються з календарів попереднього власника/партнера, потім дзеркало пише нові. Бот повідомляє партнера (з кнопкою «Відкрити планер»), коли задачу створено спільною або для нього, а також коли наявну задачу зробили спільною чи передали йому: «📌 Задача для тебе від <ім'я>», «⚡️ … додає спільну задачу», а авторові — «✅ <ім'я>: «…» — виконано» (`scheduler.notify_assigned`, `notify_done_for_author`). Ім'я з Telegram зберігається в `users.first_name` (`/me` і middleware бота), `/me` віддає `first_name` і `partner_first_name`. Чужі неспільні задачі не видно. `for_partner` при створенні віддає задачу партнеру як власнику, якщо це не спільна. Спільна при першому закритті шле партнеру повідомлення «Спільну задачу закрито».

Нагадування: APScheduler у Postgres (`apscheduler_jobs`), job id `task-reminder:{id}`. «За N до події» — `remind_before_minutes` (0…40320); `remind_at` з нього рахує сервер (`services/reminders.py`, `tasks.apply_relative_reminder`) і переносить разом із подією. Відлік від `start_time`, далі від дедлайну з часом, а для дедлайну без часу (23:59) — від 07:00 того дня (та сама година, що й імпорт all-day з Google). Явний `remind_at` у PATCH (відкласти, «нагадай о 10:00») перемагає лише для цього запису. Тому Mini App при збереженні з інтервалом **не шле** `remind_at`. У Google інтервал іде як popup override і читається назад. «Додовбувач»: задача з `priority=high`, яка не виконана, після першого нагадування (або, якщо його нема, від часу події) отримує повтор кожні `NAG_INTERVAL_MINUTES` (5). `send_reminder` сам ставить наступний job з тим самим id, передаючи `previous` (chat→message, попереднє повідомлення видаляється) і `nag_count`. Тиша `NAG_QUIET_START_HOUR`–`NAG_QUIET_END_HOUR` (23–08), здається через `NAG_GIVE_UP_DAYS` (3) після події. Зупиняють: «Виконано», зниження пріоритету; «+15 хв/+1 год/На завтра» ставлять паузу до нового `remind_at`. Логіка — `services/reminders.py` (`next_fire_at`, `next_nag_at`), а `tasks.sync_reminder` бере час звідти. Gemini ставить high лише за явних слів («терміново», «додовбуй»…), бо high тепер означає спам кожні 5 хв. Дайджести `digest:{telegram_id}:{morning|afternoon|evening}` — cron за годинами користувача, лише якщо на сьогодні є незакриті задачі (зовнішні події в дайджест не входять: `list_tasks` їх не додає). Google watch оновлюється кожні 6 годин. ICS — кожні 30 хвилин і ще раз на старті.

Бот (aiogram 3): allowlist, потім сесія БД. `/start` і `/help` дають кнопку Mini App. Вільний текст і голосові йдуть у Gemini (`backend/app/services/ai_agent.py`, модель за замовчуванням `gemini-3.6-flash`); якщо Gemini недоступний, текст розбирає regex у `backend/app/bot/parser.py`. Тимчасові збої Gemini (429/5xx, таймаут `GEMINI_TIMEOUT_SECONDS`=60, обрив з'єднання) повторюються ще двічі з паузою (`ai_agent._generate`), потім один раз на `GEMINI_FALLBACK_MODEL`, якщо задана. Голосове пише користувачу, на якому кроці збій: Gemini не відповідає / розпізнав, але не зберіг / інше. Голос перекодовується з ogg у wav через ffmpeg. Після створення є кнопки змінити час, «🔔 Нагадати за…» (пресети, свій інтервал, вимкнути) і видалити. Фрази «нагадай за день / за 2 години» розуміють і Gemini, і regex. Нагадування: виконано, +15 хв, +1 год, на завтра, «❌ Скасувати» (з підтвердженням «Так, скасувати / Ні»).

## Google Calendar

Двосторонній синк через сервісний акаунт. Вихід: `tasks._mirror_google` пише подію в календар власника і, якщо `is_shared`, копію в календар партнера (`partner_google_event_id`). Вхід: `sync_from_google` тягне обидва календарі. Копії спільних подій не імпортуються вдруге (звірка `partner_google_event_id` / `planerTaskId`). Подія Google на весь день під час імпорту стає годинним блоком о 07:00. Скасовані події Google видаляють локальну задачу.

`GOOGLE_WEBHOOK_URL` може бути порожнім: тоді push вимкнений, лишається періодичний sync. Не ковтай помилки синку мовчки — раніше пропущений імпорт `_spec_from_body` у `_sync_event` давав NameError, події в Google не створювались, а виняток губився.

## Календарі за посиланням

`backend/app/services/external_calendars.py`. Користувач вставляє `https://` або `webcal://`. Google-посилання з `cid=` перетворюється на публічний `basic.ics`. Секретне iCal-посилання зберігається в БД і клієнту не повертається.

Обмеження: 8 стрічок на користувача, тіло до 2 МБ, до 400 подій, вікно від учора до +120 днів, all-day серія не довша за 14 днів. SSRF: лише порти 80/443, заборонені localhost, приватні й link-local адреси, `.local`, `.internal`. Редіректи ручні, не більше 5, кожен URL перевіряється знову.

Події віддаються як `TaskRead` з від’ємним `id` (`-external_events.id`), `read_only=true`, `source_name` = назва стрічки. Вони особисті, не спільні. Назва й час не редагуються: наступний sync перезаписує рядки. Виконання локальне. Перед видаленням рядків `_replace_events` копіює `is_completed` за стабільним ключем `stored_event_uids`: `uid#start.isoformat()`. PATCH на від’ємний id приймає лише `{"is_completed": bool}`. Інші поля — 400. Фільтр категорії на `GET /tasks` зовнішні події ховає.

## Mini App

`webapp/`, Next.js 15 `output: "export"`, React 19, Tailwind 4, framer-motion. Точка входу `src/app/page.tsx` → `HomePage`.

`USE_MOCKS` істинний, якщо `NEXT_PUBLIC_USE_MOCKS` не дорівнює рядку `"false"` або API URL порожній. У бойовій збірці моки вимкнені. У моках є демо-подія `id: -1` «Лекція з календаря».

Поведінка, яку легко зламати:

- Список опитує `GET /tasks` кожні 8 с і ще на `visibilitychange` / `focus`. Тихий режим не показує спінер і не затирає помилку. `busy` і `generation` у `useTasks` відкидають застарілу відповідь під час редагування.
- Клік по картці в списку відкриває шит. Свої задачі редагуються (назва, опис, тег, пріоритет, дата, початок, кінець, «спільне»). Галочка лише перемикає `is_completed` і не відкриває шит (`stopPropagation`).
- Своя задача в шиті має внизу «Скасувати подію» з підтвердженням: `DELETE /tasks/{id}` прибирає її з планера й Google, вимикає нагадування. `tasks.delete_task(actor_id=…)` повідомляє всіх причетних, крім того, хто скасував (спільна, віддана, написана ним): «❌ <ім'я> скасовує «…»» (`scheduler.notify_cancelled`).
- Подія ICS у шиті лише для перегляду плюс кнопки «Позначити виконаною» / «Позначити як невиконану».
- Календар (день/тиждень) кліком по сітці створює слот, кліком по блоку відкриває ту саму картку. All-day ICS — чіпси «Весь день», не блоки часу. Чужі події з пунктирною рамкою. Виконані закреслені.
- Прогрес «Виконано N з M» рахує всі задачі на сьогодні, включно з ICS. Простроченими ICS не стають (`isOverdue` для `read_only` завжди false).
- Аудиторії: «Мої» — те, що роблю я (без спільних і без відданих партнеру), «Спільні» — лише спільні, «Усі» — усе. Типово «Усі». Прогрес дня не рахує задачі, віддані партнеру. У шиті «Хто робить: Я / <ім'я партнера> / Разом»; на картці «Робить: …» або «Від: …». Контекст пари — `lib/couple.ts` (`CoupleContext`, `assigneeOf`).
- Теги: робота, навчання, тренування, особисте.
- Рух (`lib/motion.ts`): `GLIDE` — пружина без відскоку для пілюль вибору й зсуву карток, `SHEET` — для шитів, `SOFT_MOVE`/`FADE` — для появи. У шитах `anchored` не «їздить», а плавно проявляє заливку на місці (`InPlaceFill`), бо пілюля, що їде, дрейфувала б разом із шитом. Блоки, що з'являються у формі, загортай у `Reveal` (анімація висоти), а не в `{cond && …}`. Зміна вигляду/фільтра/аудиторії — `AnimatePresence mode="wait"` у `HomePage`. Кнопки злегка стискаються під пальцем (`button:active { scale: .97 }` у `globals.css`). Тема кешується в `localStorage['planer:theme']` і ставиться скриптом у `<head>` до першого кадру, тож рожева не блимає фіолетовою. `prefers-reduced-motion` вимикає анімації.
- Тема з `GET /me` ставить `document.documentElement.dataset.theme` у `violet` або `pink`. Pink — **світла**: блок `html[data-theme="pink"]` у `globals.css` перемаплює `--color-zinc-*` у ягідні відтінки тексту, поверхні робить білим склом, акценти — неоново-рожевими (`#ff2e97`). Квіточки — SVG (`Flower.tsx`, `FlowerDecor.tsx`); елементи лише для pink мають клас `pink-only`, а приховані в pink — `not-pink`. Для pink шапка Telegram стає `#FFF0F7` (`setSurfaceColor`). Класи на кшталт `bg-zinc-950` у темі перемальовуються на `--panel`, тому меню зливається з карткою. Випадаюче меню налаштувань має фон `bg-[var(--void)]` і `z-40`.
- Налаштування — кнопка-гамбургер у шапці (`SettingsBlock`): статус Google («Наживо» / «Підключено» / «Немає зв’язку») і пункт «Календар за посиланням» (`ExternalCalendarSheet`).
- `nginx.conf` без своїх cache-заголовків. Чанки Next з хешем, тож повторне відкриття Mini App підхоплює нову збірку. Якщо Telegram тримає старий HTML, додай на час перевірки query на кшталт `?v=…`.

## Перевірка

Pytest у бойовому образі не встановлений (`uv sync --no-dev`). Робочий спосіб:

```bash
docker run --rm -e BOT_TOKEN=test \
  -v /home/ubuntu/planer/backend/app:/app/app:ro \
  -v /home/ubuntu/planer/backend/tests:/app/tests:ro \
  --entrypoint bash planer-backend \
  -c 'uv pip install -q pytest && pytest tests -q'
```

Тести: парсер, Telegram auth, Gemini-розбір, Google, ICS (нормалізація webcal/cid, SSRF, розбір, стабільні ключі повторень). Окремого HTTP-тесту на PATCH від’ємного id немає.

Фронт: `npm run typecheck` у `webapp` (залежності в образі збірки; на хості `node_modules` зазвичай немає, і `.dockerignore` його виключає).

## Куди лізти

| Задача | Файл |
| --- | --- |
| Список, створення, видимість, дзеркало в Google | `backend/app/services/tasks.py` |
| Імпорт і watch Google | `backend/app/services/google_calendar.py` |
| ICS | `backend/app/services/external_calendars.py`, `api/routes/feeds.py`, `api/routes/tasks.py` |
| Схема відповіді задачі | `backend/app/schemas.py` |
| Розклад | `backend/app/scheduler.py` |
| Бот | `backend/app/bot/` |
| Картка, клік, галочка | `webapp/src/components/TaskCard.tsx` |
| Шит створення й редагування | `webapp/src/components/AddTaskSheet.tsx` (вибір нагадування — `ReminderPicker.tsx`, `lib/reminders.ts`) |
| Сітка календаря | `webapp/src/components/CalendarBoard.tsx` |
| Стан списку й опитування | `webapp/src/hooks/useTasks.ts` |
| Фільтри й лічильник дня | `webapp/src/lib/filters.ts` |
| Клієнт API | `webapp/src/lib/api.ts` |

## Не робити

- Не редагувати поля події ICS через звичайний `TaskUpdate`: синк їх зітре. Виконання живе лише в `external_events.is_completed` і переноситься за ключем входження.
- Не вважати GitHub Pages продакшеном і не вмикати там моки на бойовому домені.
- Не піднімати кількість workers бекенда.
- Не віддавати клієнту URL стрічки ICS.
- Не слабшати перевірку публічної адреси в `assert_public_url`.
- Не ставити випадаючі панелі на `bg-zinc-950`: у темі це `--panel`.
- Не скидати `google_calendar_id` наявного користувача «для надійності»: сид цього не робить і не повинен.
