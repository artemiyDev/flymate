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
from dateutil import parser as dtparse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.settings import Settings
from bot.db.engine import init_db_engine, get_sessionmaker, close_db_engine
from bot.db.repo_subscriptions import SubscriptionsRepo

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


def build_deeplink(aviasales_path: str | None) -> str | None:
    """Построение прямой ссылки на Aviasales."""
    if not aviasales_path:
        return None
    # чаще всего прилетает относительный путь вида /some/path — префиксуем
    return f"https://aviasales.ru{aviasales_path}"


def build_search_url(origin: str, destination: str, departure_at: str) -> str:
    """
    Быстрый конструктор human-link для поиска на Aviasales.
    """
    dt = dtparse.isoparse(departure_at)
    day = dt.strftime("%d")
    month = dt.strftime("%m")
    # "21" в хвосте = шаблон длительности/возврата (можешь поменять под себя)
    return f"https://www.aviasales.com/search/{origin}{day}{month}{destination}21"


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
    """
    logger.info(f"Обработка подписки #{sub.id}: {sub.origin}→{sub.destination}, "
                f"даты={sub.range_from} - {sub.range_to}, макс.цена={sub.max_price} {sub.currency}")

    months = month_span(sub.range_from, sub.range_to)
    logger.debug(f"Подписка #{sub.id}: будет проверено месяцев: {len(months)} ({', '.join(months)})")

    total_sent = 0  # счётчик отправленных уведомлений

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
                    # Цена снизилась!
                    savings = old_price - new_price
                    logger.info(f"📉 Подписка #{sub.id}: снижение цены для {date_str}: "
                                f"{old_price} → {new_price} {sub.currency} "
                                f"(экономия: {savings:.2f})")
                    should_notify = True
                else:
                    # Цена не изменилась или выросла
                    logger.debug(f"Подписка #{sub.id}: цена для {date_str} не снизилась "
                                 f"({new_price} >= {old_price}), пропускаем")

            if should_notify:
                # Формируем и отправляем уведомление
                airline = min_offer.get("airline")
                transfers = min_offer.get("transfers")
                duration = min_offer.get("duration")
                origin = min_offer.get("origin")
                destination = min_offer.get("destination")
                dep = min_offer.get("departure_at")
                link = build_deeplink(min_offer.get("link"))
                search_link = build_search_url(origin, destination, dep)

                dt = dtparse.isoparse(dep)
                dt_txt = dt.strftime("%d.%m %H:%M")
                transfers_txt = "Прямой" if transfers == 0 else f"{transfers} пересадка" if transfers == 1 else f"{transfers} пересадки"
                dur_txt = human_duration(duration or 0)

                lines = [
                    f"🛫 <b>{origin} → {destination}</b>",
                    f"📅 {dt_txt}",
                    f"💺 {airline or 'Авиакомпания не указана'}",
                    f"💰 <b>{new_price} {sub.currency}</b>",
                ]

                # Добавляем информацию о снижении цены
                if old_price is not None:
                    savings = old_price - new_price
                    savings_percent = (savings / old_price) * 100
                    lines.append(f"📉 <b>-{savings:.2f} {sub.currency} (-{savings_percent:.1f}%)</b>")
                    lines.append(f"   Было: {old_price} {sub.currency}")
                else:
                    lines.append("🆕 <b>Новое направление!</b>")

                lines.extend([
                    f"🔁 {transfers_txt}",
                    f"🕒 {dur_txt}",
                ])

                if link:
                    lines.append(f'<a href="{link}">🔗 Купить билет</a>')
                if search_link:
                    lines.append(f'<a href="{search_link}">🔎 Найти похожие</a>')

                text = "\n".join(lines)

                try:
                    await bot.send_message(
                        chat_id=sub.user_id,
                        text=text,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                    total_sent += 1
                    logger.info(f"✉️ Подписка #{sub.id}: уведомление отправлено пользователю {sub.user_id}")

                    # Обновляем минимальную цену в Redis
                    await rds.set(tracking_key, str(new_price))
                    # TTL 90 дней (с запасом больше возможного диапазона подписки)
                    await rds.expire(tracking_key, 90 * 24 * 60 * 60)

                except Exception as e:
                    logger.error(f"Подписка #{sub.id}: ошибка отправки уведомления: {e}")

                # Ограничение: не более 10 уведомлений за один запуск
                if total_sent >= 10:
                    logger.warning(f"Подписка #{sub.id}: достигнут лимит 10 уведомлений, "
                                   f"остальные направления будут проверены в следующий раз")
                    break

        # Если достигли лимита, выходим из цикла по месяцам
        if total_sent >= 10:
            break

    if total_sent > 0:
        logger.info(f"✅ Подписка #{sub.id}: отправлено уведомлений: {total_sent}")
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

    # init Redis
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