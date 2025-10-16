# keyboards/reply.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Main persistent keyboard with two buttons
def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Get main persistent ReplyKeyboard with two buttons."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➕ Создать подписку"),
                KeyboardButton(text="📋 Мои подписки"),
            ]
        ],
        resize_keyboard=True,
        persistent=True,
    )
    return keyboard
