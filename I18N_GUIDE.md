# Руководство по мультиязычности (i18n)

## Обзор

Flymate поддерживает мультиязычность с использованием Fluent (Mozilla). Реализованы языки: русский (по умолчанию) и английский.

## Структура файлов

```
bot/
├── locales/
│   ├── ru/                    # Русские переводы
│   │   ├── common.ftl
│   │   ├── subscriptions.ftl
│   │   └── notifications.ftl
│   ├── en/                    # Английские переводы
│   │   ├── common.ftl
│   │   ├── subscriptions.ftl
│   │   └── notifications.ftl
├── i18n.py                    # Инициализация i18n
└── middlewares/
    └── i18n.py                # Middleware для определения языка
```

## Применение миграции БД

Перед запуском бота нужно применить SQL миграцию:

```bash
# Подключитесь к вашей PostgreSQL базе и выполните:
psql -U your_user -d your_database -f migrations/add_language_column.sql
```

## Использование в коде

### Импорт функции перевода

```python
from bot.i18n import _
```

### Простые переводы

```python
# Было:
await message.answer("Выберите язык:")

# Стало:
await message.answer(_("choose-language"))
```

### Переводы с параметрами

```python
# С одним параметром
await message.answer(_("language-set", lang="Русский"))

# С несколькими параметрами
await message.answer(_(
    "flight-found-price",
    price=500,
    currency="USD"
))
```

### Установка/получение текущего языка

```python
from bot.i18n import set_locale, get_locale

# Установить язык для текущего контекста
set_locale("en")

# Получить текущий язык
current_lang = get_locale()  # -> "ru" или "en"
```

## Добавление новых переводов

### 1. Добавить ключ в .ftl файлы

**bot/locales/ru/common.ftl**:
```ftl
new-feature-text = Это новая функция!
new-feature-with-param = Привет, { $name }!
```

**bot/locales/en/common.ftl**:
```ftl
new-feature-text = This is a new feature!
new-feature-with-param = Hello, { $name }!
```

### 2. Использовать в коде

```python
# Простой текст
await message.answer(_("new-feature-text"))

# С параметром
await message.answer(_("new-feature-with-param", name="Иван"))
```

## Плюрализация (для будущего)

Fluent поддерживает плюрализацию:

```ftl
# Русский
days-count = { $count ->
    [one] { $count } день
    [few] { $count } дня
   *[other] { $count } дней
}

# Английский
days-count = { $count ->
    [one] { $count } day
   *[other] { $count } days
}
```

Использование:
```python
_("days-count", count=5)  # RU: "5 дней", EN: "5 days"
```

## Команды бота

- `/language` — сменить язык интерфейса
- При выборе языка он сохраняется в БД и применяется автоматически

## Автоматическое определение языка

1. **При первом запуске**: используется `language_code` из Telegram
2. **После выбора языка**: используется сохранённый в БД язык
3. **Fallback**: если язык не поддерживается → русский

## Текущий статус реализации

✅ **Готово:**
- Инфраструктура i18n (Fluent)
- Middleware для автоматического определения языка
- Команда `/language` для смены языка
- Файлы переводов для ru/en
- Поддержка БД (поле `language` в таблице `users`)
- Методы в `UsersRepo` для работы с языком

⏳ **TODO (для полной реализации):**
- Заменить все хардкод-тексты в `main.py` на `_()`
- Заменить все тексты в диалогах (`bot/dialogs/`) на `_()`
- Добавить мультиязычность в `worker.py` для уведомлений
- Обновить клавиатуры (`bot/keyboards/`) с переводами

## Пример замены хардкод-текстов

### До:
```python
await message.answer(
    "✈️ Flymate — ваш помощник в поиске дешёвых авиабилетов"
)
```

### После:
```python
await message.answer(_("start-welcome"))
```

### В worker.py:
```python
# Получить язык пользователя из БД
user_lang = await UsersRepo.get_language(session, user_id)
set_locale(user_lang or "ru")

# Теперь все _() будут на нужном языке
notification = _(
    "flight-found-price",
    price=new_price,
    currency=sub.currency
)
```

## Добавление нового языка (в будущем)

1. Создать папку `bot/locales/{lang_code}/`
2. Скопировать `.ftl` файлы из `ru/` или `en/`
3. Перевести содержимое
4. Добавить язык в `bot/i18n.py`:
   ```python
   SUPPORTED_LOCALES = ["ru", "en", "de"]  # Добавили немецкий
   ```
5. Обновить команду `/language` в `main.py`
6. Обновить команды бота в `set_bot_commands()`

## Отладка

### Проверить загрузку переводов
```python
from bot.i18n import i18n

# Проверить все локали
for locale in i18n.supported_locales:
    print(f"{locale}: {i18n.format('start-welcome', locale=locale)}")
```

### Проверить текущую локаль
```python
from bot.i18n import get_locale

current = get_locale()
print(f"Current locale: {current}")
```

## Поддержка

Если при использовании `_()` выводится сам ключ вместо текста:
1. Проверьте, что ключ существует в `.ftl` файлах
2. Убедитесь, что файлы сохранены в UTF-8
3. Проверьте синтаксис Fluent (особенно фигурные скобки)
4. Перезапустите бота для перезагрузки переводов
