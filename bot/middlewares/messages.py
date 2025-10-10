from aiogram import BaseMiddleware
from aiogram.types import Message

class AutoDeleteMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data):
        result = await handler(event, data)
        try:
            await event.delete()
        except Exception:
            pass
        return result