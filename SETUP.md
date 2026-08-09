# Woyqe — запуск

## Что уже проверено в коде

- Backend поднимается, все роуты подключены, `/health` отвечает.
- Проверка Telegram `initData` считает подпись правильно (валидный payload
  проходит, подделанный отклоняется).
- Логика Instagram-коннектора проверена офлайн 26 ассертами:
  `backend/.venv/Scripts/python -m tests.selfcheck_instagram`
- Frontend собирается: `cd frontend && npm run build`.

## Что нужно сделать вам, чтобы включить «вживую»

Эти два значения — реальные секреты/ресурсы, их нельзя сгенерировать за вас.

### 1. Supabase service_role ключ

В `backend/.env` поле `SUPABASE_SERVICE_ROLE_KEY` сейчас — заглушка
`PASTE_YOUR_SUPABASE_SERVICE_ROLE_JWT_HERE`.

Supabase Dashboard → Project Settings → API → **service_role** (secret) →
скопировать JWT (начинается с `eyJ...`) и вставить в `.env`.
`SUPABASE_URL` уже приведён к нужному виду (без `/rest/v1`).

> ⚠️ Старые ключи и `TELEGRAM_BOT_TOKEN` попадали в git-историю. Их стоит
> перевыпустить (Supabase → API → Reset, BotFather → `/revoke`).

### 2. Создать таблицы в Supabase

Supabase Dashboard → SQL Editor → вставить содержимое `backend/schema.sql` →
Run. Создаст `users`, `accounts`, `account_connections`, `chats`, `messages`
и включит Realtime на `messages`/`chats`.

## Запуск

Backend:
```bash
cd backend
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

`frontend/.env` уже указывает на Supabase (anon key). Для локальной отладки вне
Telegram backend принимает dev-логин: он включён флагом `ALLOW_DEV_LOGIN=true` в
`backend/.env` и работает вместе с dev-`initData` из `frontend/src/services/api.ts`.
**В проде поставьте `ALLOW_DEV_LOGIN=false`.**

## Как проверить Instagram end-to-end

1. Открыть приложение → шестерёнка (Настройки) → **+ Добавить аккаунт** → вкладка **Inst**.
2. Ввести логин/пароль реального Instagram-аккаунта.
3. Если аккаунт требует — появится экран **2FA** или **challenge** (реальные состояния, не таймер).
4. После успеха аккаунт сохраняется, только если backend реально получил профиль.
5. Вкладка **Inst** покажет реальные диалоги; открытие диалога тянет историю.
6. Отправка из Woyqe уходит в Instagram; входящие подтягивает поллер (интервал
   `POLL_INTERVAL_SECONDS`, по умолчанию 45с) и Realtime показывает их без перезагрузки.

## Флаги в backend/.env

| Флаг | Назначение |
|------|-----------|
| `ALLOW_DEV_LOGIN` | dev-логин вне Telegram (в проде `false`) |
| `ENABLE_POLLER` | фоновая синхронизация входящих |
| `POLL_INTERVAL_SECONDS` | интервал поллера (мин. 15с) |
| `CORS_ORIGINS` | разрешённые origin фронтенда (через запятую) |
