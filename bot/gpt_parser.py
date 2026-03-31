# bot/gpt_parser.py
import asyncio
import json
import re
from datetime import date
from typing import Optional

import aiohttp

TEXT_GENERATION_OPENAI_URL = "https://text.pollinations.ai/openai"


def _extract_explicit_years(user_text: str) -> list[int]:
    """Return explicitly mentioned years like 2026 from user text."""
    years = re.findall(r"\b(20\d{2})\b", user_text)
    return sorted({int(year) for year in years})


def _replace_year(iso_date: str, year: int) -> str:
    parsed_date = date.fromisoformat(iso_date)
    return parsed_date.replace(year=year).isoformat()


def _normalize_parsed_dates(parsed: dict, user_text: str) -> dict:
    """
    Keep explicit user year authoritative.

    This protects against model drift where the prompt bias or examples
    cause the model to return 2025 even when the user explicitly asked for 2026.
    """
    explicit_years = _extract_explicit_years(user_text)
    if len(explicit_years) != 1:
        return parsed

    explicit_year = explicit_years[0]
    for key in ("range_from", "range_to"):
        iso_date = parsed.get(key)
        if not iso_date:
            continue
        try:
            parsed[key] = _replace_year(iso_date, explicit_year)
        except ValueError:
            # Preserve the original value if day/month cannot exist in that year.
            continue
    return parsed


def _build_prompt(user_text: str, today: date | None = None) -> str:
    today = today or date.today()
    current_year = today.year
    today_iso = today.isoformat()

    return f"""Ты — помощник для приложения по поиску авиабилетов.
Твоя задача — преобразовывать текстовый запрос пользователя в JSON-словарь с IATA-кодами городов, диапазоном дат вылета, валютой, бюджетом и предпочтением по прямым рейсам.

Примеры запросов:
"С 7 октября по 23 октября из Москвы в Анталию"
"Из Лондона в Стамбул с 15 декабря по 20 декабря, до 500 евро"
"Москва - Дубай 1-10 января, максимум 30000 рублей"
"Из Петербурга в Париж 5-12 марта, только прямой рейс"
"Москва - Тбилиси 20-25 апреля, без пересадок"

ВАЖНО:
- Сегодня {today_iso}.
- range_from и range_to — это ДИАПАЗОН ДАТ ВЫЛЕТА (начало и конец периода поиска), НЕ даты вылета и возврата!
- Пользователь ищет билеты на вылет в любой день между range_from и range_to.
- Если пользователь указал "прямой рейс", "без пересадок", "direct", "non-stop", "только прямые" и подобные формулировки — добавь поле "direct": true

Ты должен вернуть JSON-словарь такого вида:

{{"departure": "MOW", "destination": "AYT", "range_from": "2024-10-07", "range_to": "2024-10-23", "currency": "RUB", "max_price": 15000, "direct": true}}

Правила:
- departure — IATA-код города/аэропорта вылета (3 буквы в верхнем регистре).
- destination — IATA-код города/аэропорта назначения (3 буквы в верхнем регистре).
- range_from — начало диапазона дат вылета (формат YYYY-MM-DD).
- range_to — конец диапазона дат вылета (формат YYYY-MM-DD).
- currency — валюта (USD, EUR, RUB). ОПЦИОНАЛЬНО — если не указана, не добавляй это поле.
- max_price — максимальная цена (число). ОПЦИОНАЛЬНО — если не указана, не добавляй это поле.
- direct — булево значение (true/false). ОПЦИОНАЛЬНО — добавляй только если пользователь явно указал требование прямого рейса или с пересадками.
- Если пользователь явно указал год, сохрани этот год ТОЧНО как в запросе.
- Если год не указан, используй {current_year}.
- Если год не указан и дата в {current_year} уже прошла относительно {today_iso}, выбери ближайший логичный будущий год.
- Отвечай ТОЛЬКО JSON-словарём, без дополнительного текста.

Запрос пользователя:
{user_text}
"""

async def parse_text_request(user_text: str) -> Optional[dict]:
    """
    Парсит текстовый запрос пользователя через GPT API.

    Возвращает словарь вида:
    {
        "departure": "MOW",
        "destination": "AYT",
        "range_from": "2024-10-07",
        "range_to": "2024-10-23",
        "currency": "RUB",  # опционально
        "max_price": 15000,  # опционально
        "direct": true  # опционально
    }

    Или None в случае ошибки.
    """
    prompt = _build_prompt(user_text)

    messages = [{"role": "user", "content": prompt}]
    payload = {
        "model": "openai",
        "messages": messages
    }

    content = None

    try:
        async with aiohttp.ClientSession() as session:
            # Пробуем несколько раз при ошибках сервера
            for attempt in range(3):
                print(f"Attempt {attempt + 1}/3")
                try:
                    async with session.post(TEXT_GENERATION_OPENAI_URL, json=payload, timeout=30) as response:
                        if response.status == 502 or response.status == 503:
                            print(f"[WARN] GPT API returned status {response.status}, attempt {attempt + 1}/3")
                            if attempt < 2:
                                await asyncio.sleep(2)  # Ждём 2 секунды перед повтором
                                continue
                            return None

                        if response.status != 200:
                            print(f"[ERROR] GPT API returned status {response.status}")
                            text = await response.text()
                            print(f"Response: {text}")
                            return None

                        result = await response.json()
                        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                        print(f"GPT Response: {content}")
                        break  # Успешный ответ, выходим из цикла retry

                except asyncio.TimeoutError:
                    print(f"[WARN] GPT API timeout, attempt {attempt + 1}/3")
                    if attempt < 2:
                        continue
                    return None

        if not content:
            print("[ERROR] Empty response from GPT")
            return None

        # Пытаемся извлечь JSON из ответа
        content = content.strip()

        # Удаляем markdown-обертки если есть
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()
        print(f"Cleaned content: {content}")

        # Парсим JSON
        parsed = json.loads(content)
        parsed = _normalize_parsed_dates(parsed, user_text)
        print(f"Parsed: {parsed}")

        # Валидация обязательных полей
        required_fields = ["departure", "destination", "range_from", "range_to"]
        if not all(field in parsed for field in required_fields):
            print(f"[ERROR] Missing required fields in GPT response: {parsed}")
            return None

        # Опциональные поля: currency, max_price, direct_flight
        # Если их нет — это нормально, они будут запрошены позже

        return parsed

    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse JSON from GPT: {e}")
        print(f"Content: {content}")
        return None
    except Exception as e:
        print(f"[ERROR] GPT parsing failed: {e}")
        import traceback
        traceback.print_exc()
        return None
