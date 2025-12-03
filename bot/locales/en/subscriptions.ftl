# Subscriptions translations for English

# New subscription dialog
new-sub-text-input =
    ✈️ Describe your request in free form

    Examples:
    • "From October 7 to October 23, direct from London to Antalya"
    • "Moscow - Dubai January 1-10, up to 30000 rubles"
    • "From Istanbul to Paris direct December 15-20, max 500 euros"

    Specify cities, departure date range, and (optionally) budget.

    Or click "Fill Manually" for step-by-step input.

new-sub-processing = ⏳ Processing request...

new-sub-parse-error =
    ❌ Failed to recognize the request. The service may be temporarily unavailable.

    Try:
    • Rephrasing your request
    • Click "Fill Manually" for step-by-step input

new-sub-origin = ✈️ Enter departure city IATA code (e.g., IST)
new-sub-destination = 📍 Enter destination city IATA code (e.g., ALA)

new-sub-depart-date =
    🗓 Select START of departure date range
    (from which date to search for tickets)

    Current selection: { $date }

new-sub-return-date =
    🗓 Select END of departure date range
    (until which date to search for tickets)

    Start: { $from }
    End: { $to }

new-sub-return-before-depart = Return date cannot be before departure date

new-sub-direct-flights = ✈️ Search for direct flights only?
new-sub-direct-yes = ✅ Yes, direct only
new-sub-direct-no = ❌ No, transfers are OK

new-sub-currency-select = Choose currency (or skip, RUB will be used):
new-sub-currency-usd = 💵 USD
new-sub-currency-eur = 💶 EUR
new-sub-currency-rub = ₽ RUB
new-sub-currency-skip = ⏭ Skip (RUB)

new-sub-budget-input =
    Enter maximum ticket price
    (or skip to set no limit):
new-sub-budget-skip = ⏭ Skip (no limit)

new-sub-confirm =
    Reviewing:
    From: { $origin }
    To: { $destination }
    Departure dates: { $from } → { $to }
    Budget: { $price }
    Direct flights only: { $direct }

new-sub-missing-params = Not all parameters are filled
new-sub-saved = Subscription saved!
new-sub-success =
    ✅ Subscription successfully created!

    I'll check prices every 5 minutes and send you a notification
    as soon as I find a suitable option.

# My subscriptions dialog
my-subs-title = 📋 Your subscriptions
my-subs-empty = You don't have any active subscriptions yet
my-subs-create-first = Create your first subscription via /start

my-subs-item =
    🛫 { $origin } → { $destination }
    📅 { $from } - { $to }
    💰 up to { $price } { $currency }
    { $direct ->
        [true] ✈️ Direct only
       *[false] 🔁 With transfers
    }

my-subs-edit = ✏️ Change budget
my-subs-disable = 🔕 Disable

subscription-disabled = ❌ Subscription disabled
