# bot/gpt_parser.py
import json
import asyncio
import aiohttp
from typing import Optional

TEXT_GENERATION_OPENAI_URL = "https://text.pollinations.ai/openai"

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
    prompt = f"""Ты — помощник для приложения по поиску авиабилетов.
Твоя задача — преобразовывать текстовый запрос пользователя в JSON-словарь с IATA-кодами городов, диапазоном дат вылета, валютой, бюджетом и предпочтением по прямым рейсам.

Примеры запросов:
"С 7 октября по 23 октября из Москвы в Анталию"
"Из Лондона в Стамбул с 15 декабря по 20 декабря, до 500 евро"
"Москва - Дубай 1-10 января, максимум 30000 рублей"
"Из Петербурга в Париж 5-12 марта, только прямой рейс"
"Москва - Тбилиси 20-25 апреля, без пересадок"

ВАЖНО:
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
- Если год не указан, используй 2025.
- Отвечай ТОЛЬКО JSON-словарём, без дополнительного текста.

Запрос пользователя:
{user_text}
"""

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