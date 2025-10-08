# dialogs/my_subs.py
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.text import Const, Format, Multi
from aiogram_dialog.widgets.kbd import Button, ScrollingGroup, Select, Cancel, Back
from aiogram_dialog.api.entities.modes import ShowMode

from bot.db.engine import get_sessionmaker
from bot.db.repo_subscriptions import SubscriptionsRepo


class MySubsSG(StatesGroup):
    list = State()
    confirm_delete = State()


# --- callbacks ---

async def on_sub_select(c: CallbackQuery, widget: Select, manager: DialogManager, item_id: str):
    """Когда пользователь выбирает подписку для удаления."""
    manager.dialog_data["selected_sub_id"] = int(item_id)
    await manager.switch_to(MySubsSG.confirm_delete)


async def on_delete_confirm(c: CallbackQuery, b: Button, manager: DialogManager):
    """Подтверждение удаления подписки."""
    sub_id = manager.dialog_data.get("selected_sub_id")
    if not sub_id:
        await c.answer("Ошибка: подписка не выбрана", show_alert=True)
        return

    Session = get_sessionmaker()
    async with Session() as session:
        async with session.begin():
            deleted_id = await SubscriptionsRepo.delete(session, sub_id, c.from_user.id)

    if deleted_id:
        await c.answer("Подписка удалена", show_alert=True)
    else:
        await c.answer("Не удалось удалить подписку", show_alert=True)

    manager.show_mode = ShowMode.EDIT
    await manager.switch_to(MySubsSG.list)


async def on_cancel_delete(c: CallbackQuery, b: Button, manager: DialogManager):
    """Отмена удаления."""
    manager.show_mode = ShowMode.EDIT
    await manager.switch_to(MySubsSG.list)


# --- getters ---

async def subs_list_getter(dialog_manager: DialogManager, **kwargs):
    """Получает список подписок пользователя."""
    user_id = dialog_manager.event.from_user.id

    Session = get_sessionmaker()
    async with Session() as session:
        subs = await SubscriptionsRepo.list_by_user(session, user_id)

    if not subs or len(subs) == 0:
        return {
            "has_subs": False,
            "subs": [],
            "count": 0,
        }

    subs_data = []
    for sub in subs:
        # Форматируем данные для отображения
        price_text = "без ограничения" if sub.max_price >= 999999999 else f"до {int(sub.max_price)} {sub.currency}"

        subs_data.append({
            "id": str(sub.id),  # Преобразуем в строку для item_id_getter
            "text": f"{sub.origin} → {sub.destination} | {sub.range_from.strftime('%d.%m')}—{sub.range_to.strftime('%d.%m')} | {price_text}",
        })

    return {
        "has_subs": True,
        "subs": subs_data,
        "count": len(subs_data),
    }


async def confirm_delete_getter(dialog_manager: DialogManager, **kwargs):
    """Получает данные выбранной подписки для подтверждения удаления."""
    sub_id = dialog_manager.dialog_data.get("selected_sub_id")
    user_id = dialog_manager.event.from_user.id

    Session = get_sessionmaker()
    async with Session() as session:
        subs = await SubscriptionsRepo.list_by_user(session, user_id)
        selected_sub = next((s for s in subs if s.id == sub_id), None)

    if not selected_sub:
        return {
            "origin": "—",
            "destination": "—",
            "date_range": "—",
            "price": "—",
        }

    price_text = "без ограничения" if selected_sub.max_price >= 999999999 else f"до {int(selected_sub.max_price)} {selected_sub.currency}"

    return {
        "origin": selected_sub.origin,
        "destination": selected_sub.destination,
        "date_range": f"{selected_sub.range_from.strftime('%d.%m.%Y')} — {selected_sub.range_to.strftime('%d.%m.%Y')}",
        "price": price_text,
    }


# --- windows ---

list_win = Window(
    Format("📋 Мои подписки ({count}):", when="has_subs"),
    Const("📋 Мои подписки", when=lambda data, w, m: not data.get("has_subs")),
    ScrollingGroup(
        Select(
            Format("{item[text]}"),
            id="sub_select",
            item_id_getter=lambda x: x["id"],
            items="subs",
            on_click=on_sub_select,
        ),
        id="subs_scroll",
        width=1,
        height=8,
        when="has_subs",
    ),
    Const("\nУ вас пока нет подписок.\nИспользуйте /start чтобы создать подписку.", when=lambda data, w, m: not data.get("has_subs")),
    Cancel(Const("Закрыть")),
    state=MySubsSG.list,
    getter=subs_list_getter,
)

confirm_delete_win = Window(
    Const("❌ Удалить подписку?\n"),
    Format("Маршрут: {origin} → {destination}"),
    Format("Даты: {date_range}"),
    Format("Бюджет: {price}"),
    Button(Const("🗑 Да, удалить"), id="confirm_delete", on_click=on_delete_confirm),
    Button(Const("Отмена"), id="cancel_delete", on_click=on_cancel_delete),
    state=MySubsSG.confirm_delete,
    getter=confirm_delete_getter,
)


# --- dialog ---

my_subs_dialog = Dialog(
    list_win,
    confirm_delete_win,
)
