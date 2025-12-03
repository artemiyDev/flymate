# Subscriptions translations for Russian

# New subscription dialog
new-sub-text-input =
    ✈️ Опишите ваш запрос в свободной форме

    Примеры:
    • "С 7 октября по 23 октября прямой из Лондона в Анталию"
    • "Москва - Дубай 1-10 января, до 30000 рублей"
    • "Из Стамбула в Париж прямой 15-20 декабря, макс 500 евро"

    Укажите города, диапазон дат вылета и (опционально) бюджет.

    Или нажмите "Заполнить вручную" для пошагового ввода.

new-sub-processing = ⏳ Обрабатываю запрос...

new-sub-parse-error =
    ❌ Не удалось распознать запрос. Возможно, сервис временно недоступен.

    Попробуйте:
    • Переформулировать запрос
    • Нажать "Заполнить вручную" для пошагового ввода

new-sub-origin = ✈️ Укажите IATA-код города вылета (например, IST)
new-sub-destination = 📍 Укажите IATA-код города назначения (например, ALA)

new-sub-depart-date =
    🗓 Выберите НАЧАЛО диапазона дат вылета
    (с какого числа искать билеты)

    Текущий выбор: { $date }

new-sub-return-date =
    🗓 Выберите КОНЕЦ диапазона дат вылета
    (по какое число искать билеты)

    Начало: { $from }
    Конец: { $to }

new-sub-return-before-depart = Дата возврата не может быть раньше даты вылета

new-sub-direct-flights = ✈️ Искать только прямые рейсы?
new-sub-direct-yes = ✅ Да, только прямые
new-sub-direct-no = ❌ Нет, можно с пересадками

new-sub-currency-select = Выберите валюту (или пропусти, будет использован RUB):
new-sub-currency-usd = 💵 USD
new-sub-currency-eur = 💶 EUR
new-sub-currency-rub = ₽ RUB
new-sub-currency-skip = ⏭ Пропустить (RUB)

new-sub-budget-input =
    Введите максимальную цену билета
    (или пропусти, чтобы не ограничивать):
new-sub-budget-skip = ⏭ Пропустить (без ограничения)

new-sub-confirm =
    Проверяем:
    От: { $origin }
    До: { $destination }
    Даты вылета: { $from } → { $to }
    Бюджет: { $price }
    Только прямые рейсы: { $direct }

new-sub-missing-params = Не все параметры заполнены
new-sub-saved = Подписка сохранена!
new-sub-success =
    ✅ Подписка успешно создана!

    Я буду проверять цены каждые 5 минут и пришлю уведомление,
    как только найду подходящий вариант.

# My subscriptions dialog
my-subs-title = 📋 Ваши подписки
my-subs-empty = У вас пока нет активных подписок
my-subs-create-first = Создайте первую подписку через /start

my-subs-item =
    🛫 { $origin } → { $destination }
    📅 { $from } - { $to }
    💰 до { $price } { $currency }
    { $direct ->
        [true] ✈️ Только прямые
       *[false] 🔁 С пересадками
    }

my-subs-edit = ✏️ Изменить бюджет
my-subs-disable = 🔕 Отключить

subscription-disabled = ❌ Подписка отключена
