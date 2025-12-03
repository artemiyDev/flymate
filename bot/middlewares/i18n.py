# bot/middlewares/i18n.py
"""Middleware for automatic language detection and setting."""

from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from bot.i18n import set_locale, SUPPORTED_LOCALES, DEFAULT_LOCALE
from bot.db.engine import get_sessionmaker
from bot.db.repo_users import UsersRepo


class I18nMiddleware(BaseMiddleware):
    """Middleware to set user's locale before handling message."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user: User = data.get("event_from_user")

        if user:
            # Try to get user's language from database
            Session = get_sessionmaker()
            async with Session() as session:
                user_language = await UsersRepo.get_language(session, user.id)

            if user_language:
                # User has chosen language in bot
                set_locale(user_language)
            else:
                # Use Telegram's language_code as fallback
                telegram_lang = user.language_code or "en"
                # Extract first 2 letters (e.g., "en-US" -> "en")
                lang_code = telegram_lang[:2]

                # Check if supported
                if lang_code in SUPPORTED_LOCALES:
                    set_locale(lang_code)
                else:
                    set_locale(DEFAULT_LOCALE)

        return await handler(event, data)
