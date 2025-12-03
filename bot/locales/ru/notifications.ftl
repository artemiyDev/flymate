# Notifications translations for Russian

# Flight found notification
flight-found-header = 🛫 { $origin } → { $destination }
flight-found-date = 📅 { $date }
flight-found-airline = 💺 { $airline }
flight-found-price = 💰 { $price } { $currency }

flight-found-price-drop = 📉 -{ $savings } { $currency } (-{ $percent }%)
flight-found-was = Было: { $oldPrice } { $currency }
flight-found-new-route = 🆕 Новое направление!

flight-found-direct = Прямой
flight-found-transfer = { $count ->
    [1] 1 пересадка
    [2] 2 пересадки
    [3] 3 пересадки
    [4] 4 пересадки
   *[other] { $count } пересадок
}

flight-found-duration = 🕒 { $duration }
flight-found-buy = 🔗 Купить билет
flight-found-search = 🔎 Найти похожие

button-disable-subscription = 🔕 Отключить эту подписку

# Subscription expired notification
subscription-expired-title = ⏰ Подписка истекла и была автоматически удалена
subscription-expired-route = 🛫 { $origin } → { $destination }
subscription-expired-dates = 📅 Период поиска: { $from } - { $to }
subscription-expired-price = 💰 Макс. цена: { $price } { $currency }
subscription-expired-footer = Создайте новую подписку через /start, если хотите продолжить мониторинг цен.
