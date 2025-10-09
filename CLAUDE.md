# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Обзор проекта

Flymate — Telegram-бот для мониторинга цен на авиабилеты через Aviasales API. Пользователи создают подписки на авиамаршруты с указанием дат, бюджета и валюты, после чего фоновый worker (bot/worker.py) периодически проверяет наличие дешёвых билетов и отправляет уведомления в Telegram.

## Архитектура

### Основные компоненты

1. **bot/main.py** — точка входа Telegram-бота (aiogram v3)
   - Обрабатывает команды `/start`, `/help`, `/subs`, `/deal`
   - Использует aiogram-dialog v2 для построения многошаговых диалогов
   - При `/start` запускает диалог создания подписки (NewSubSG)

2. **bot/worker.py** — фоновый процесс для проверки цен
   - Запускается отдельно от основного бота (независимый процесс)
   - Каждые 5 минут проверяет подписки через `SubscriptionsRepo.fetch_due()`
   - Использует Aviasales API (`/aviasales/v3/prices_for_dates`)
   - Реализует антидубликаты через Redis SET (ключи = SHA1-хеш оффера)
   - Отправляет уведомления через Bot API

3. **bot/settings.py** — Pydantic Settings для конфигурации
   - Загружает переменные окружения из `bot/.env`
   - Поддерживает PostgreSQL, Redis, Aviasales API token
   - ВАЖНО: `.env` содержит чувствительные данные (не коммитить в git)

4. **bot/db/** — слой работы с PostgreSQL (SQLAlchemy 2.0 + asyncpg)
   - `engine.py` — глобальный async engine и sessionmaker
   - `models.py` — две модели: `User` и `FlightSubscription`
   - `repo_users.py` — UPSERT пользователей из Telegram User
   - `repo_subscriptions.py` — создание/получение/обновление подписок

5. **bot/dialogs/new_sub.py** — aiogram-dialog для создания подписки
   - 7 шагов: origin → destination → depart_cal → return_cal → currency → budget → confirm
   - Использует TextInput для IATA-кодов, Calendar для дат, Button для валют
   - При сохранении вызывает `SubscriptionsRepo.create()`

### База данных

- **PostgreSQL** (asyncpg)
- Таблицы:
  - `users`: user_id (PK), username, plan ('basic'/'premium'), subs_active_cnt
  - `flight_subscriptions`: id (PK), user_id, origin, destination, range_from, range_to, direct, max_price, currency, check_interval_minutes, active, next_check_at

### Внешние зависимости

- **Aviasales API** (Travelpayouts): `/aviasales/v3/prices_for_dates` — возвращает список предложений для origin→destination в заданном месяце
- **Redis**: хранение списков отправленных офферов (`subs:{sub_id}:sent`), TTL=60 дней
- **Telegram Bot API**: aiogram v3 (polling mode)

## Команды разработки

### Запуск бота
```bash
cd bot
python main.py
```
Запускает Telegram-бот в режиме long polling.

### Запуск фонового worker
```bash
cd bot
python worker.py
```
Запускает фоновый процесс проверки цен (каждые 5 минут).

### Установка зависимостей
```bash
# Активировать виртуальное окружение
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# Установить пакеты
pip install aiogram==3.22.0 aiogram-dialog==2.4.0 sqlalchemy asyncpg pydantic-settings redis aiohttp python-dateutil
```

### Тестирование
- `bot/test_gpt.py` — ручной тест GPT-интеграции (на данный момент не используется в основном коде)

## Важные особенности

1. **Антидубликаты**: worker использует Redis SET для хранения хешей отправленных офферов. Хеш = SHA1(origin|destination|departure_at|airline|transfers|price).

2. **Расчёт следующей проверки**: после каждой проверки `bump_next_check()` сдвигает `next_check_at` на `check_interval_minutes` вперёд.

3. **Разбиение по месяцам**: API принимает `departure_at` в формате YYYY-MM или YYYY-MM-DD. Функция `month_span()` разбивает диапазон дат на список месяцев.

4. **Диалоги aiogram-dialog v2**: используй `DialogManager.start()` для запуска, `manager.next()` для перехода между окнами, `manager.dialog_data` для хранения state.

5. **Timezone**: по умолчанию используется `Europe/Istanbul` (см. settings.TIMEZONE).

6. **Планы пользователей**: модель User содержит поле `plan` ('basic'/'premium'), но функционал лимитов ещё не реализован (заглушка).

## Структура директорий

```
flymate/
├── bot/
│   ├── .env               # Секретные переменные окружения (НЕ коммитить)
│   ├── main.py            # Точка входа Telegram-бота
│   ├── worker.py          # Фоновый процесс проверки цен
│   ├── settings.py        # Pydantic Settings
│   ├── test_gpt.py        # Ручной тест GPT
│   ├── db/
│   │   ├── engine.py      # SQLAlchemy async engine
│   │   ├── models.py      # User, FlightSubscription
│   │   ├── repo_users.py
│   │   └── repo_subscriptions.py
│   └── dialogs/
│       └── new_sub.py     # Диалог создания подписки
└── .venv/                 # Python виртуальное окружение
```

## Типичные задачи

### Добавить новую команду
1. Добавь `BotCommand` в `set_bot_commands()` (main.py:18)
2. Зарегистрируй обработчик в `build_common_router()` (main.py:38)

### Изменить схему БД
1. Обнови модели в `bot/db/models.py`
2. Создай миграцию Alembic (на данный момент Alembic не настроен — миграции выполняются вручную)
3. Примени миграцию к базе

### Добавить новый шаг в диалог подписки
1. Добавь новый `State` в `NewSubSG` (dialogs/new_sub.py:17)
2. Создай новое `Window` с нужными виджетами (TextInput/Button/Calendar)
3. Добавь callback для обработки ввода
4. Вставь Window в нужное место в `Dialog()` (dialogs/new_sub.py:210)

### Отладка worker
- Добавь `print()` в `process_subscription()` для логирования запросов к API
- Проверь Redis через `redis-cli` (ключи вида `subs:{id}:sent`)
- Уменьши `check_interval_minutes` в БД для тестирования


Все комментарии пиши на английском языке