# bot/worker.py
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from typing import Any

import aiohttp
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dateutil import parser as dtparse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.settings import Settings
from bot.db.engine import init_db_engine, get_sessionmaker, close_db_engine
from bot.db.repo_subscriptions import SubscriptionsRepo
from bot.db.repo_users import UsersRepo

UTC = timezone.utc

# Настройка логгера
logger = logging.getLogger("flymate.worker")


def setup_logging(settings: Settings) -> None:
    """Настройка логирования для worker с записью в отдельный файл."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Формат логов
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Хендлер для файла с ротацией (макс 10MB, 5 файлов)
    file_handler = RotatingFileHandler(
        settings.WORKER_LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Хендлер для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Настройка корневого логгера worker
    logger.setLevel(log_level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Отключаем пропагацию, чтобы не дублировать в root logger
    logger.propagate = False

    logger.info(f"Логирование настроено: уровень={settings.LOG_LEVEL}, файл={settings.WORKER_LOG_FILE}")


API_BASE_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


def month_span(d1: date, d2: date) -> list[str]:
    """Разбиваем диапазон на YYYY-MM (API принимает YYYY-MM и YYYY-MM-DD)."""
    cur = date(d1.year, d1.month, 1)
    last = date(d2.year, d2.month, 1)
    out = []
    while cur <= last:
        out.append(cur.strftime("%Y-%m"))
        # следующий месяц
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return out


def price_tracking_key(sub_id: int, origin: str, destination: str,
                       departure_date: str, direct: bool) -> str:
    """
    Ключ для отслеживания минимальной цены по маршруту/дате.
    Формат: subs:{sub_id}:minprice:{origin}_{destination}_{date}_{direct}
    """
    direct_flag = "direct" if direct else "transfer"
    return f"subs:{sub_id}:minprice:{origin}_{destination}_{departure_date}_{direct_flag}"


def human_duration(minutes: int) -> str:
    """Форматирование длительности полёта в человекочитаемый вид."""
    h, m = divmod(int(minutes), 60)
    return f"{h}h {m:02d}m"


def build_deeplink(aviasales_path: str | None, marker: str = "", language: str = "ru") -> str | None:
    """
    Build direct Aviasales link with affiliate marker.
    If marker is provided, it will be added as URL parameter for monetization.
    Language determines domain: ru -> aviasales.ru, en -> aviasales.com
    """
    if not aviasales_path:
        return None

    # Determine domain based on language
    domain = "aviasales.ru" if language == "ru" else "aviasales.com"

    # Usually comes as relative path like /some/path — prefix with domain
    base_url = f"https://{domain}{aviasales_path}"

    # Add affiliate marker if provided
    if marker:
        separator = "&" if "?" in base_url else "?"
        base_url = f"{base_url}{separator}marker={marker}"

    return base_url


def build_search_url(origin: str, destination: str, departure_at: str, marker: str = "", language: str = "ru") -> str:
    """
    Build search link for Aviasales with affiliate marker.
    Format: https://www.aviasales.{ru|com}/search/ORIGINDDDESTINATIONDD?marker=YOUR_MARKER
    Language determines domain: ru -> aviasales.ru, en -> aviasales.com
    """
    dt = dtparse.isoparse(departure_at)
    day = dt.strftime("%d")
    month = dt.strftime("%m")

    # Determine domain based on language
    domain = "aviasales.ru" if language == "ru" else "aviasales.com"

    # Build base search URL
    base_url = f"https://www.{domain}/search/{origin}{day}{month}{destination}21"

    # Add affiliate marker if provided
    if marker:
        base_url = f"{base_url}?marker={marker}"

    return base_url


async def get_airport_name(rds: Redis, iata_code: str) -> str:
    """
    Get airport name from Redis cache by IATA code.
    Falls back to IATA code if not found.
    """
    if not iata_code:
        return "Unknown"

    # Try airport first
    airport_name = await rds.get(f"airport:{iata_code.upper()}")
    if airport_name:
        return airport_name

    # Try city as fallback
    city_name = await rds.get(f"city:{iata_code.upper()}")
    if city_name:
        return city_name

    # Fallback to IATA code
    return iata_code.upper()


async def get_airline_name(rds: Redis, iata_code: str) -> str:
    """
    Get airline name from Redis cache by IATA code.
    Falls back to IATA code if not found.
    """
    if not iata_code:
        return "Unknown airline"

    airline_name = await rds.get(f"airline:{iata_code.upper()}")
    if airline_name:
        return airline_name

    # Fallback to IATA code
    return iata_code.upper()




async def fetch_prices_for_month(session_http: aiohttp.ClientSession,
                                 base_url: str,
                                 token: str,
                                 origin: str,
                                 destination: str,
                                 departure_month: str,
                                 direct: bool,
                                 currency: str) -> list[dict[str, Any]]:
    """
    Обертка над /aviasales/v3/prices_for_dates
    Даты разрешены в YYYY-MM и YYYY-MM-DD (см. оф. доки). Мы даём YYYY-MM.
    """
    params = {
        "origin": origin,
        "destination": destination,
        "departure_at": departure_month,  # YYYY-MM
        "sorting": "price",
        "direct": "true" if direct else "false",
        "limit": 100,
        "page": 1,
        "one_way": "true",
        "token": token,
        "currency": currency,
    }

    logger.debug(f"Запрос к API: {origin}→{destination}, месяц={departure_month}, direct={direct}, currency={currency}")

    async with session_http.get(API_BASE_URL, params=params, timeout=30) as r:
        if r.status != 200:
            text = await r.text()
            logger.error(f"Aviasales API error {r.status}: {text}")
            raise RuntimeError(f"Aviasales {r.status}: {text}")
        data = await r.json()
        offers_count = len(data.get("data", []))
        logger.info(f"Получено {offers_count} предложений для {origin}→{destination} ({departure_month})")
        return data.get("data", [])


async def process_subscription(bot: Bot,
                               rds: Redis,
                               session_db: AsyncSession,
                               http: aiohttp.ClientSession,
                               settings: Settings,
                               sub) -> None:
    """
    Обработать одну подписку: дернуть API по месяцам,
    отправить уведомления только при снижении цены.
    Если диапазон дат подписки уже в прошлом — удалить её с уведомлением.
    """
    logger.info(f"Обработка подписки #{sub.id}: {sub.origin}→{sub.destination}, "
                f"даты={sub.range_from} - {sub.range_to}, макс.цена={sub.max_price} {sub.currency}")

    # Get user language for building correct domain links (ru -> .ru, en -> .com)
    user_language = await UsersRepo.get_language(session_db, sub.user_id) or "ru"
    logger.debug(f"Подписка #{sub.id}: язык пользователя = {user_language}")

    # Check if subscription date range is in the past
    today = date.today()
    if sub.range_to < today:
        logger.info(f"Подписка #{sub.id}: диапазон дат истёк (range_to={sub.range_to} < today={today}), удаляем")

        # Get human-readable names for notification
        origin_name = await get_airport_name(rds, sub.origin)
        destination_name = await get_airport_name(rds, sub.destination)

        # Format route display
        origin_display = f"{origin_name} ({sub.origin})" if origin_name != sub.origin else sub.origin
        destination_display = f"{destination_name} ({sub.destination})" if destination_name != sub.destination else sub.destination

        # Send notification to user
        notification_text = (
            f"⏰ <b>Подписка истекла и была автоматически удалена</b>\n\n"
            f"🛫 {origin_display} → {destination_display}\n"
            f"📅 Период поиска: {sub.range_from.strftime('%d.%m.%Y')} - {sub.range_to.strftime('%d.%m.%Y')}\n"
            f"💰 Макс. цена: {sub.max_price} {sub.currency}\n\n"
            f"Создайте новую подписку через /start, если хотите продолжить мониторинг цен."
        )

        try:
            await bot.send_message(
                chat_id=sub.user_id,
                text=notification_text,
                parse_mode="HTML"
            )
            logger.info(f"✉️ Подписка #{sub.id}: уведомление об истечении отправлено пользователю {sub.user_id}")
        except Exception as e:
            logger.error(f"Подписка #{sub.id}: ошибка отправки уведомления об истечении: {e}")

        # Delete subscription from database
        await SubscriptionsRepo.delete(session_db, sub.id, sub.user_id)
        logger.info(f"🗑️ Подписка #{sub.id}: удалена из БД")
        return

    months = month_span(sub.range_from, sub.range_to)
    logger.debug(f"Подписка #{sub.id}: будет проверено месяцев: {len(months)} ({', '.join(months)})")

    total_sent = 0  # счётчик отправленных сообщений
    notifications_to_send = []  # список уведомлений для отправки

    for mon in months:
        try:
            offers = await fetch_prices_for_month(
                http, API_BASE_URL, settings.AVIASALES_API_TOKEN,
                origin=sub.origin, destination=sub.destination,
                departure_month=mon, direct=sub.direct,
                currency=sub.currency,
            )
        except Exception as e:
            logger.warning(f"Подписка #{sub.id}: ошибка API для месяца {mon}: {e}")
            continue

        # Группируем предложения по дате вылета
        # Структура: {date_str: [offers_list]}
        offers_by_date: dict[str, list[dict[str, Any]]] = {}

        for f in offers:
            price = f.get("price")
            if price is None or float(price) > float(sub.max_price):
                continue

            dep = f.get("departure_at")
            if not dep:
                continue

            dt = dtparse.isoparse(dep)
            departure_date = dt.date()

            # фильтрация по диапазону дат
            if departure_date < sub.range_from or departure_date > sub.range_to:
                continue

            date_str = departure_date.strftime("%Y-%m-%d")

            if date_str not in offers_by_date:
                offers_by_date[date_str] = []

            offers_by_date[date_str].append(f)

        logger.debug(f"Подписка #{sub.id}: найдено уникальных дат вылета: {len(offers_by_date)}")

        # Обрабатываем каждую дату отдельно
        for date_str, date_offers in offers_by_date.items():
            # Находим минимальную цену среди всех предложений на эту дату
            min_offer = min(date_offers, key=lambda x: float(x.get("price", float("inf"))))
            new_price = float(min_offer.get("price"))

            # Получаем ключ для отслеживания цены
            tracking_key = price_tracking_key(
                sub.id, sub.origin, sub.destination, date_str, sub.direct
            )

            # Получаем текущий минимум из Redis
            stored_min = await rds.get(tracking_key)

            should_notify = False
            old_price = None

            if stored_min is None:
                # Первое предложение для этой даты
                logger.info(f"📍 Подписка #{sub.id}: новая дата {date_str}, первая цена {new_price} {sub.currency}")
                should_notify = True
            else:
                old_price = float(stored_min)
                if new_price < old_price:
                    # Цена снизилась! Проверяем значимость изменения
                    savings = old_price - new_price
                    price_change_percent = (savings / old_price) * 100

                    if price_change_percent >= 2.0:
                        # Значимое снижение (>=2%)
                        logger.info(f"📉 Подписка #{sub.id}: значимое снижение цены для {date_str}: "
                                    f"{old_price} → {new_price} {sub.currency} "
                                    f"(экономия: {savings:.2f}, -{price_change_percent:.1f}%)")
                        should_notify = True
                    else:
                        # Незначительное снижение (<2%)
                        logger.debug(f"Подписка #{sub.id}: незначительное снижение цены для {date_str}: "
                                     f"{old_price} → {new_price} {sub.currency} "
                                     f"(-{price_change_percent:.1f}% < 2%), пропускаем")
                else:
                    # Цена не изменилась или выросла
                    logger.debug(f"Подписка #{sub.id}: цена для {date_str} не снизилась "
                                 f"({new_price} >= {old_price}), пропускаем")

            if should_notify:
                # Формируем данные для уведомления
                airline = min_offer.get("airline")
                transfers = min_offer.get("transfers")
                duration = min_offer.get("duration")
                origin = min_offer.get("origin")
                destination = min_offer.get("destination")
                dep = min_offer.get("departure_at")
                # Add affiliate marker to all links for monetization
                # Use user's language to determine domain (ru -> .ru, en -> .com)
                link = build_deeplink(
                    min_offer.get("link"),
                    marker=settings.TRAVELPAYOUTS_MARKER,
                    language=user_language
                )
                search_link = build_search_url(
                    origin, destination, dep,
                    marker=settings.TRAVELPAYOUTS_MARKER,
                    language=user_language
                )

                # Собираем данные уведомления
                notifications_to_send.append({
                    "offer": min_offer,
                    "new_price": new_price,
                    "old_price": old_price,
                    "tracking_key": tracking_key,
                    "airline": airline,
                    "transfers": transfers,
                    "duration": duration,
                    "origin": origin,
                    "destination": destination,
                    "dep": dep,
                    "link": link,
                    "search_link": search_link,
                })

                logger.info(
                    f"📋 Подписка #{sub.id}: добавлено уведомление в очередь (всего: {len(notifications_to_send)})")

                # Ограничение: не более 10 уведомлений за один запуск
                if len(notifications_to_send) >= 10:
                    logger.warning(f"Подписка #{sub.id}: достигнут лимит 10 уведомлений, "
                                   f"остальные направления будут проверены в следующий раз")
                    break

        # Если достигли лимита, выходим из цикла по месяцам
        if len(notifications_to_send) >= 10:
            break

    # Отправляем собранные уведомления группами по 5
    if notifications_to_send:
        logger.info(f"📤 Подписка #{sub.id}: начинаем отправку {len(notifications_to_send)} уведомлений группами по 5")

        # Разбиваем на группы по 5
        batch_size = 5
        for i in range(0, len(notifications_to_send), batch_size):
            batch = notifications_to_send[i:i + batch_size]

            # Формируем объединённое сообщение
            message_parts = []
            for idx, notif in enumerate(batch, 1):
                dt = dtparse.isoparse(notif["dep"])
                dt_txt = dt.strftime("%d.%m %H:%M")
                transfers_txt = "Прямой" if notif["transfers"] == 0 else f"{notif['transfers']} пересадка" if notif[
                                                                                                                  "transfers"] == 1 else f"{notif['transfers']} пересадки"
                dur_txt = human_duration(notif["duration"] or 0)

                # Get human-readable names from Redis
                origin_name = await get_airport_name(rds, notif['origin'])
                destination_name = await get_airport_name(rds, notif['destination'])
                airline_name = await get_airline_name(rds, notif['airline'])

                # Format route display: "City Name (CODE)"
                origin_display = f"{origin_name} ({notif['origin']})" if origin_name != notif['origin'] else notif['origin']
                destination_display = f"{destination_name} ({notif['destination']})" if destination_name != notif['destination'] else notif['destination']

                lines = [
                    f"🛫 <b>{origin_display} → {destination_display}</b>",
                    f"📅 {dt_txt}",
                    f"💺 {airline_name}",
                    f"💰 <b>{notif['new_price']} {sub.currency}</b>",
                ]

                # Добавляем информацию о снижении цены
                if notif["old_price"] is not None:
                    savings = notif["old_price"] - notif["new_price"]
                    savings_percent = (savings / notif["old_price"]) * 100
                    lines.append(f"📉 <b>-{savings:.2f} {sub.currency} (-{savings_percent:.1f}%)</b>")
                    lines.append(f"   Было: {notif['old_price']} {sub.currency}")
                else:
                    lines.append("🆕 <b>Новое направление!</b>")

                lines.extend([
                    f"🔁 {transfers_txt}",
                    f"🕒 {dur_txt}",
                ])

                if notif["link"]:
                    lines.append(f'<a href="{notif["link"]}">🔗 Купить билет</a>')
                if notif["search_link"]:
                    lines.append(f'<a href="{notif["search_link"]}">🔎 Найти похожие</a>')

                message_parts.append("\n".join(lines))

            # Объединяем все части в одно сообщение
            text = "\n".join(message_parts)

            # Create inline keyboard with disable button
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔕 Отключить эту подписку",
                            callback_data=f"disable_sub:{sub.id}"
                        )
                    ]
                ]
            )

            try:
                await bot.send_message(
                    chat_id=sub.user_id,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=keyboard
                )
                total_sent += 1
                logger.info(
                    f"✉️ Подписка #{sub.id}: отправлено сообщение #{total_sent} с {len(batch)} предложениями пользователю {sub.user_id}")

                # Обновляем минимальные цены в Redis для всех предложений в группе
                for notif in batch:
                    await rds.set(notif["tracking_key"], str(notif["new_price"]))
                    # TTL 90 дней (с запасом больше возможного диапазона подписки)
                    await rds.expire(notif["tracking_key"], 90 * 24 * 60 * 60)

            except Exception as e:
                logger.error(f"Подписка #{sub.id}: ошибка отправки сообщения: {e}")

        logger.info(
            f"✅ Подписка #{sub.id}: отправлено сообщений: {total_sent} ({len(notifications_to_send)} предложений)")
    else:
        logger.info(f"ℹ️ Подписка #{sub.id}: новых снижений цен не найдено")

    # Сдвигаем расписание
    await SubscriptionsRepo.bump_next_check(session_db, sub.id)
    logger.info(f"Подписка #{sub.id}: обработка завершена, следующая проверка запланирована")


async def loop_worker():
    settings = Settings()

    # Настраиваем логирование
    setup_logging(settings)

    logger.info("=" * 60)
    logger.info("Запуск worker для проверки подписок на авиабилеты")
    logger.info("=" * 60)

    # init DB
    logger.info("Инициализация подключения к БД...")
    init_db_engine()
    Session = get_sessionmaker()
    logger.info("БД подключена успешно")

    # init Redis (worker has its own connection, separate from bot)
    logger.info(f"Подключение к Redis {settings.REDIS_HOST}:{settings.REDIS_PORT}...")
    rds = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=(settings.REDIS_PASSWORD or None),
        decode_responses=True,
    )
    logger.info("Redis подключен успешно")

    # init TG
    logger.info("Инициализация Telegram бота...")
    bot = Bot(token=settings.TG_TOKEN)
    logger.info("Telegram бот инициализирован")

    async with aiohttp.ClientSession(headers={}) as http:
        try:
            logger.info("Начало основного цикла worker (интервал проверки: 5 минут)")

            while True:
                try:
                    logger.debug("Проверка подписок, требующих обработки...")

                    async with Session() as s:
                        async with s.begin():
                            due = await SubscriptionsRepo.fetch_due(s, limit=200)

                        if not due:
                            logger.debug("Нет подписок для обработки, ожидание 5 минут...")
                            await asyncio.sleep(300)
                            continue

                        logger.info(f"Найдено подписок для обработки: {len(due)}")

                        # обработаем по очереди
                        for idx, sub in enumerate(due, 1):
                            logger.info(f"[{idx}/{len(due)}] Обработка подписки #{sub.id}")
                            async with s.begin():
                                await process_subscription(bot, rds, s, http, settings, sub)

                except Exception as e:
                    logger.exception(f"Ошибка в цикле worker: {e}")

                # ждём 5 минут
                logger.info("Цикл завершён, ожидание 5 минут до следующей проверки...")
                await asyncio.sleep(300)
        finally:
            logger.info("Завершение работы worker...")
            await close_db_engine()
            await rds.close()
            await bot.session.close()
            logger.info("Worker остановлен")


def main():
    asyncio.run(loop_worker())


if __name__ == "__main__":
    main()
