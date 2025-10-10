# dialogs/main_menu.py
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.text import Const
from aiogram_dialog.widgets.kbd import Button, Cancel, Row
from aiogram_dialog.api.entities.modes import StartMode

from dialogs.new_sub import NewSubSG
from dialogs.my_subs import MySubsSG


class MainMenuSG(StatesGroup):
    menu = State()


# --- callbacks ---

async def on_new_sub(c: CallbackQuery, b: Button, manager: DialogManager):
    """Navigate to create subscription dialog."""
    await manager.start(NewSubSG.text_input, mode=StartMode.RESET_STACK)


async def on_my_subs(c: CallbackQuery, b: Button, manager: DialogManager):
    """Navigate to my subscriptions dialog."""
    await manager.start(MySubsSG.list, mode=StartMode.RESET_STACK)


async def on_help(c: CallbackQuery, b: Button, manager: DialogManager):
    """Show help message."""
    await c.message.answer(
        "Я помогу оформить подписку на дешёвые авиабилеты.\n"
        "Команды:\n"
        "• /start — создать подписку\n"
        "• /subs — список подписок\n"
    )
    await c.answer()


async def on_close_menu(c: CallbackQuery, b: Button, manager: DialogManager):
    """Close main menu and delete message."""
    try:
        await c.message.delete()
    except Exception:
        pass

    await manager.done()


# --- windows ---

menu_win = Window(
    Const(
        "✈️ Flymate — ваш помощник в поиске дешёвых авиабилетов\n\n"
        "Я помогу вам отслеживать цены на интересующие маршруты и сообщу, "
        "когда появятся выгодные предложения!\n\n"
        "Создайте подписку на нужный маршрут, укажите даты и бюджет — "
        "я буду проверять цены каждые 5 минут и пришлю уведомление, "
        "как только найду подходящий вариант.\n\n"
        "Выберите действие:"
    ),
    Row(
        Button(Const("➕ Создать подписку"), id="new_sub", on_click=on_new_sub),
        Button(Const("📋 Мои подписки"), id="my_subs", on_click=on_my_subs),
    ),
    Row(
        Button(Const("❓ Помощь"), id="help", on_click=on_help),
        Button(Const("❌ Закрыть"), id="close", on_click=on_close_menu),
    ),
    state=MainMenuSG.menu,
)


# --- dialog ---

main_menu_dialog = Dialog(
    menu_win,
)
