# Notifications translations for English

# Flight found notification
flight-found-header = 🛫 { $origin } → { $destination }
flight-found-date = 📅 { $date }
flight-found-airline = 💺 { $airline }
flight-found-price = 💰 { $price } { $currency }

flight-found-price-drop = 📉 -{ $savings } { $currency } (-{ $percent }%)
flight-found-was = Was: { $oldPrice } { $currency }
flight-found-new-route = 🆕 New route!

flight-found-direct = Direct
flight-found-transfer = { $count ->
    [1] 1 transfer
   *[other] { $count } transfers
}

flight-found-duration = 🕒 { $duration }
flight-found-buy = 🔗 Buy ticket
flight-found-search = 🔎 Find similar

button-disable-subscription = 🔕 Disable this subscription

# Subscription expired notification
subscription-expired-title = ⏰ Subscription expired and was automatically deleted
subscription-expired-route = 🛫 { $origin } → { $destination }
subscription-expired-dates = 📅 Search period: { $from } - { $to }
subscription-expired-price = 💰 Max price: { $price } { $currency }
subscription-expired-footer = Create a new subscription via /start if you want to continue price monitoring.
