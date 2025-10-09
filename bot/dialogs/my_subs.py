# dialogs/my_subs.py
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.text import Const, Format, Multi
from aiogram_dialog.widgets.kbd import Button, ScrollingGroup, Select, Cancel, Back
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.api.entities.modes import ShowMode

from bot.db.engine import get_sessionmaker
from bot.db.repo_subscriptions import SubscriptionsRepo


class MySubsSG(StatesGroup):
    list = State()
    select_action = State()
    edit_price = State()
    confirm_delete = State()


# --- callbacks ---

async def on_sub_select(c: CallbackQuery, widget: Select, manager: DialogManager, item_id: str):
    """When user selects a subscription."""
    manager.dialog_data["selected_sub_id"] = int(item_id)
    await manager.switch_to(MySubsSG.select_action)


async def on_edit_price_action(c: CallbackQuery, b: Button, manager: DialogManager):
    """Navigate to price editing."""
    manager.show_mode = ShowMode.EDIT
    await manager.switch_to(MySubsSG.edit_price)


async def on_delete_action(c: CallbackQuery, b: Button, manager: DialogManager):
    """Navigate to deletion confirmation."""
    manager.show_mode = ShowMode.EDIT
    await manager.switch_to(MySubsSG.confirm_delete)


async def on_price_input(m: Message, widget: TextInput, manager: DialogManager, value: str):
    """Handle new price input."""
    try:
        new_price = float(value.replace(",", "."))
        if new_price <= 0:
            await m.answer("Цена должна быть больше нуля")
            return
    except ValueError:
        await m.answer("Неверный формат цены. Введите число.")
        return

    sub_id = manager.dialog_data.get("selected_sub_id")
    if not sub_id:
        await m.answer("Ошибка: подписка не выбрана")
        return

    Session = get_sessionmaker()
    async with Session() as session:
        async with session.begin():
            success = await SubscriptionsRepo.update_max_price(
                session, sub_id, m.from_user.id, new_price
            )

    if success:
        await m.answer(f"✅ Максимальная цена обновлена: {int(new_price)}")
    else:
        await m.answer("❌ Не удалось обновить цену")

    try:
        await m.delete()
    except Exception:
        pass

    manager.show_mode = ShowMode.EDIT
    await manager.switch_to(MySubsSG.list)


async def skip_price_input(c: CallbackQuery, b: Button, manager: DialogManager):
    """Cancel price editing."""
    manager.show_mode = ShowMode.EDIT
    await manager.switch_to(MySubsSG.select_action)


async def on_delete_confirm(c: CallbackQuery, b: Button, manager: DialogManager):
    """Confirm subscription deletion."""
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
    """Cancel deletion."""
    manager.show_mode = ShowMode.EDIT
    await manager.switch_to(MySubsSG.list)


# --- getters ---

async def subs_list_getter(dialog_manager: DialogManager, **kwargs):
    """Get user's subscription list."""
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
        # Format data for display
        price_text = "без ограничения" if sub.max_price >= 999999999 else f"до {int(sub.max_price)} {sub.currency}"

        subs_data.append({
            "id": str(sub.id),  # Convert to string for item_id_getter
            "text": f"{sub.origin} → {sub.destination} | {sub.range_from.strftime('%d.%m')}—{sub.range_to.strftime('%d.%m')} | {price_text}",
        })

    return {
        "has_subs": True,
        "subs": subs_data,
        "count": len(subs_data),
    }


async def selected_sub_getter(dialog_manager: DialogManager, **kwargs):
    """Get selected subscription data."""
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
            "currency": "RUB",
        }

    price_text = "без ограничения" if selected_sub.max_price >= 999999999 else f"до {int(selected_sub.max_price)} {selected_sub.currency}"

    return {
        "origin": selected_sub.origin,
        "destination": selected_sub.destination,
        "date_range": f"{selected_sub.range_from.strftime('%d.%m.%Y')} — {selected_sub.range_to.strftime('%d.%m.%Y')}",
        "price": price_text,
        "currency": selected_sub.currency,
    }


async def confirm_delete_getter(dialog_manager: DialogManager, **kwargs):
    """Get selected subscription data for deletion confirmation."""
    return await selected_sub_getter(dialog_manager, **kwargs)


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

select_action_win = Window(
    Const("⚙️ Выберите действие:\n"),
    Format("Маршрут: {origin} → {destination}"),
    Format("Даты: {date_range}"),
    Format("Бюджет: {price}\n"),
    Button(Const("✏️ Изменить максимальную цену"), id="edit_price", on_click=on_edit_price_action),
    Button(Const("🗑 Удалить"), id="delete", on_click=on_delete_action),
    Back(Const("◀️ Назад")),
    state=MySubsSG.select_action,
    getter=selected_sub_getter,
)

edit_price_win = Window(
    Const("💰 Введите новую максимальную цену\n"),
    Format("Маршрут: {origin} → {destination}"),
    Format("Текущий бюджет: {price}"),
    Format("Валюта: {currency}\n"),
    Const("Введите число (например: 5000):"),
    TextInput(
        id="price_input",
        on_success=on_price_input,
    ),
    Back(Const("◀️ Назад"), on_click=skip_price_input),
    state=MySubsSG.edit_price,
    getter=selected_sub_getter,
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
    select_action_win,
    edit_price_win,
    confirm_delete_win,
)
