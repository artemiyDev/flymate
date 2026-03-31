import json
from datetime import date

import pytest

from bot.gpt_parser import _build_prompt, _normalize_parsed_dates, parse_text_request


class FakeResponse:
    def __init__(self, status: int, payload: dict):
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self._payload

    async def text(self):
        return json.dumps(self._payload)


class FakeSession:
    def __init__(self, payload: dict):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, *args, **kwargs):
        return FakeResponse(200, self.payload)


def test_build_prompt_uses_current_year():
    prompt = _build_prompt("Москва - Дубай 1-10 января", today=date(2026, 3, 20))
    assert "Если год не указан, используй 2026." in prompt
    assert "Сегодня 2026-03-20." in prompt


def test_normalize_parsed_dates_preserves_explicit_year():
    parsed = {
        "departure": "MOW",
        "destination": "DXB",
        "range_from": "2025-06-10",
        "range_to": "2025-06-20",
    }

    normalized = _normalize_parsed_dates(parsed, "Москва - Дубай с 10 по 20 июня 2026")

    assert normalized["range_from"] == "2026-06-10"
    assert normalized["range_to"] == "2026-06-20"


@pytest.mark.asyncio
async def test_parse_text_request_corrects_model_year(monkeypatch):
    payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "departure": "MOW",
                            "destination": "AYT",
                            "range_from": "2025-10-07",
                            "range_to": "2025-10-23",
                        }
                    )
                }
            }
        ]
    }

    monkeypatch.setattr("bot.gpt_parser.aiohttp.ClientSession", lambda: FakeSession(payload))

    parsed = await parse_text_request("С 7 октября 2026 по 23 октября 2026 из Москвы в Анталию")

    assert parsed is not None
    assert parsed["range_from"] == "2026-10-07"
    assert parsed["range_to"] == "2026-10-23"
