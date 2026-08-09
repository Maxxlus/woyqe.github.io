# Woyqe

Telegram Mini App — единый inbox для личных аккаунтов Instagram, MAX и VK.
Сообщения из мессенджеров попадают в Woyqe; ответы уходят обратно в мессенджер.

**Статус:** Instagram — полный рабочий vertical slice (login → 2FA/challenge →
профиль → диалоги → сообщения → отправка → фоновая синхронизация входящих).
MAX и VK — на очереди (коннекторы возвращают честный статус «недоступно», без заглушек).

- Backend: FastAPI + Supabase (Postgres) + instagrapi + Fernet
- Frontend: React + TypeScript + Vite + Tailwind, Supabase Realtime

См. **[SETUP.md](SETUP.md)** для запуска.

## Структура

```
backend/
  app/
    main.py                     FastAPI app (CORS, роутеры, фоновый поллер)
    config.py                   настройки из .env (+ нормализация Supabase URL)
    dependencies.py             проверка Telegram initData -> user_id
    database.py                 supabase client
    core/security.py            Fernet-шифрование сессий
    connectors/
      base.py                   BaseConnector (безопасные дефолты)
      instagram.py              реальный instagrapi-коннектор
      max.py / vk.py            заготовки (честный статус "недоступно")
    routers/
      accounts.py               подключение/список/удаление аккаунтов
      chats.py                  чаты, сообщения, отправка
    services/
      account_connection.py     оркестрация подключения (+ проверка профиля)
      sync.py                   синхронизация чатов/сообщений + поллер
  schema.sql                    DDL для Supabase (запустить перед стартом)
  tests/selfcheck_instagram.py  офлайн-проверка логики коннектора
frontend/
  src/
    App.tsx
    services/api.ts             axios-клиент к backend
    services/realtime.ts        Supabase Realtime подписка на messages
    components/                 BottomNav, ChatList, ChatView, Settings, AddAccount
```
