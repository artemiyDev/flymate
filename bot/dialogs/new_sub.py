# dialogs/new_sub.py
from datetime import date
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import (
    Next, Back, Cancel, Button, Calendar,
)
from aiogram_dialog.api.entities.modes import ShowMode, StartMode
from aiogram_dialog.widgets.kbd.calendar_kbd import CalendarScope

from bot.db.engine import get_sessionmaker
from bot.db.repo_subscriptions import SubscriptionsRepo
from bot.gpt_parser import parse_text_request
from bot.keyboards.reply import get_main_keyboard  # Only used in on_save


def _get_calendar(manager: DialogManager, widget_id: str):
    calendar = manager.dialog().find(widget_id)
    if calendar is None:
        return None
    return calendar.managed(manager)


def _sync_calendar(manager: DialogManager, widget_id: str, base_date: date):
    calendar = _get_calendar(manager, widget_id)
    if calendar is None:
        return
    calendar.set_offset(base_date)
    calendar.set_scope(CalendarScope.DAYS)


async def on_new_sub_start(start_data, manager: DialogManager):
    """Reset calendar widgets to current dates when dialog starts."""
    today = date.today()
    _sync_calendar(manager, "cal_depart", today)
    _sync_calendar(manager, "cal_return", today)

class NewSubSG(StatesGroup):
    text_input = State()
    origin = State()
    destination = State()
    depart_cal = State()
    return_cal = State()
    direct_flights = State()  # NEW: ask if user wants direct flights only
    budget = State()
    currency = State()
    confirm = State()


# --- callbacks ---

async def process_text_input(m: Message, w, manager: DialogManager, value: str):
    """Process free-form text input via GPT."""
    # Show user that processing is in progress
    processing_msg = await m.answer("⏳ Обрабатываю запрос...")

    # Parse via GPT
    parsed = await parse_text_request(value)

    # Delete processing and initial dialog messages
    try:
        await processing_msg.delete()
    except Exception:
        pass

    if not parsed:
        await m.answer(
            "❌ Не удалось распознать запрос. Возможно, сервис временно недоступен.\n\n"
            "Попробуйте:\n"
            "• Переформулировать запрос\n"
            "• Нажать \"Заполнить вручную\" для пошагового ввода"
        )
        return

    # Save parsed data to dialog_data
    manager.dialog_data["origin"] = parsed.get("departure", "").upper()
    manager.dialog_data["destination"] = parsed.get("destination", "").upper()
    manager.dialog_data["date_from"] = parsed.get("range_from", "")
    manager.dialog_data["date_to"] = parsed.get("range_to", "")

    # Optional fields
    if "currency" in parsed:
        manager.dialog_data["currency"] = parsed.get("currency", "").upper()
    if "max_price" in parsed:
        manager.dialog_data["max_price"] = parsed.get("max_price")
    if "direct" in parsed:
        manager.dialog_data["direct"] = parsed.get("direct")

    try:
        await m.delete()  # Delete user input
    except Exception:
        pass

    # Delete and send new message instead of editing
    manager.show_mode = ShowMode.EDIT

    # Check what information is missing and navigate accordingly
    has_direct = "direct" in manager.dialog_data
    has_currency = "currency" in manager.dialog_data
    has_max_price = "max_price" in manager.dialog_data

    # If direct flights preference is not specified, ask user
    if not has_direct:
        await manager.switch_to(NewSubSG.direct_flights)
        return

    # If currency is not specified, go to currency selection
    if not has_currency:
        await manager.switch_to(NewSubSG.currency)
        return

    # If max_price is not specified, go to budget input
    if not has_max_price:
        await manager.switch_to(NewSubSG.budget)
        return

    # All data is present, go to confirmation
    await manager.switch_to(NewSubSG.confirm)


async def on_manual_fill(c: CallbackQuery, b: Button, manager: DialogManager):
    """Handle 'Fill manually' button click."""
    today = date.today()
    _sync_calendar(manager, "cal_depart", today)
    _sync_calendar(manager, "cal_return", today)
    # Delete and send new message instead of editing
    manager.show_mode = ShowMode.EDIT
    await manager.next()


async def on_cancel_dialog(c: CallbackQuery, b: Button, manager: DialogManager):
    """Handle cancel button - delete message and close dialog."""
    # Delete dialog message
    try:
        await c.message.delete()
    except Exception:
        pass

    # Close dialog (ReplyKeyboard remains visible)
    await manager.done()


async def set_origin(m, w, manager, value: str):
    manager.dialog_data["origin"] = value.strip().upper()
    try:
        await m.delete()  # Delete user input
    except Exception:
        pass
    manager.show_mode = ShowMode.EDIT  # Next update = edit mode
    await manager.next()  # Move to next window

# destination
async def set_destination(m, w, manager, value: str):
    manager.dialog_data["destination"] = value.strip().upper()
    _sync_calendar(manager, "cal_depart", date.today())
    try:
        await m.delete()
    except Exception:
        pass
    manager.show_mode = ShowMode.EDIT
    await manager.next()


async def on_depart_selected(
    c: CallbackQuery, widget: Calendar, manager: DialogManager, selected_date: date
):
    manager.dialog_data["date_from"] = selected_date.isoformat()
    _sync_calendar(manager, "cal_return", selected_date)
    await manager.next()


async def on_return_selected(
    c: CallbackQuery, widget: Calendar, manager: DialogManager, selected_date: date
):
    manager.dialog_data["date_to"] = selected_date.isoformat()
    # Check that return is not before departure
    if manager.dialog_data["date_to"] < manager.dialog_data["date_from"]:
        await c.answer("Дата возврата не может быть раньше даты вылета", show_alert=True)
        return
    await manager.next()

async def choose_direct_yes(c: CallbackQuery, b: Button, manager: DialogManager):
    """User wants direct flights only."""
    manager.dialog_data["direct"] = True
    manager.show_mode = ShowMode.EDIT
    await manager.next()

async def choose_direct_no(c: CallbackQuery, b: Button, manager: DialogManager):
    """User accepts flights with transfers."""
    manager.dialog_data["direct"] = False
    manager.show_mode = ShowMode.EDIT
    await manager.next()

async def choose_usd(c: CallbackQuery, b: Button, manager: DialogManager):
    manager.dialog_data["currency"] = "USD"
    manager.show_mode = ShowMode.EDIT
    await manager.next()

async def choose_rub(c: CallbackQuery, b: Button, manager: DialogManager):
    manager.dialog_data["currency"] = "RUB"
    manager.show_mode = ShowMode.EDIT
    await manager.next()

async def choose_eur(c: CallbackQuery, b: Button, manager: DialogManager):
    manager.dialog_data["currency"] = "EUR"
    manager.show_mode = ShowMode.EDIT
    await manager.next()

async def skip_currency(c: CallbackQuery, b: Button, manager: DialogManager):
    """Skip currency selection (use RUB by default)."""
    manager.dialog_data["currency"] = "RUB"
    manager.show_mode = ShowMode.EDIT
    await manager.next()

async def skip_budget(c: CallbackQuery, b: Button, manager: DialogManager):
    """Skip budget input (use None)."""
    manager.dialog_data["max_price"] = None
    manager.show_mode = ShowMode.EDIT
    await manager.next()

async def set_budget(m, w, manager, value: str):
    manager.dialog_data["max_price"] = float(value.replace(",", "."))
    try:
        await m.delete()
    except Exception:
        pass
    manager.show_mode = ShowMode.EDIT
    await manager.next()  # To confirm



async def on_save(c: CallbackQuery, b: Button, manager: DialogManager):
    data = manager.dialog_data
    # Minimal validation of required fields
    if not all(k in data for k in ("origin", "destination", "date_from", "date_to", "currency")):
        await c.answer("Не все параметры заполнены", show_alert=True)
        return

    # max_price can be None (no limit)
    max_price_value = data.get("max_price")
    if max_price_value is not None:
        max_price_value = float(max_price_value)
    else:
        # If None, set very large value for DB (e.g. 999999999)
        max_price_value = 999999999.0

    Session = get_sessionmaker()
    async with Session() as session:
        async with session.begin():
            await SubscriptionsRepo.create(
                session,
                user_id=c.from_user.id,
                origin=str(data["origin"]).upper(),
                destination=str(data["destination"]).upper(),
                range_from=date.fromisoformat(data["date_from"]),
                range_to=date.fromisoformat(data["date_to"]),
                direct=bool(data.get("direct", False)),
                max_price=max_price_value,
                currency=str(data["currency"]).upper(),
                check_interval_minutes=5,
                active=True,
            )

    # Show success notification first
    await c.answer("Подписка сохранена!", show_alert=True)

    # Delete dialog messages
    try:
        await c.message.delete()
    except Exception:
        pass

    # Close dialog
    await manager.done()

    # Show success message with ReplyKeyboard
    await c.message.answer(
        "✅ Подписка успешно создана!\n\n"
        "Я буду проверять цены каждые 5 минут и пришлю уведомление, "
        "как только найду подходящий вариант.",
        reply_markup=get_main_keyboard(),
    )


# --- getters for Format ---

async def depart_getter(dialog_manager: DialogManager, **kwargs):
    return {
        "date_from": dialog_manager.dialog_data.get("date_from", "не выбрана"),
    }


async def return_getter(dialog_manager: DialogManager, **kwargs):
    return {
        "date_from": dialog_manager.dialog_data.get("date_from", "—"),
        "date_to": dialog_manager.dialog_data.get("date_to", "не выбрана"),
    }


async def confirm_getter(dialog_manager: DialogManager, **kwargs):
    max_price = dialog_manager.dialog_data.get("max_price")
    if max_price is None:
        price_text = "без ограничения"
    else:
        currency = dialog_manager.dialog_data.get("currency", "RUB")
        price_text = f"≤ {max_price} {currency}"

    direct = dialog_manager.dialog_data.get("direct", False)
    direct_text = "Да" if direct else "Нет"

    return {
        "origin": dialog_manager.dialog_data.get("origin", "—"),
        "destination": dialog_manager.dialog_data.get("destination", "—"),
        "date_from": dialog_manager.dialog_data.get("date_from", "—"),
        "date_to": dialog_manager.dialog_data.get("date_to", "—"),
        "price_display": price_text,
        "direct_display": direct_text,
    }


# --- windows ---

text_input_win = Window(
    Const("✈️ Опишите ваш запрос в свободной форме\n\n"
          "Примеры:\n"
          "• \"С 7 октября по 23 октября прямой из Лондона в Анталию\"\n"
          "• \"Москва - Дубай 1-10 января, до 30000 рублей\"\n"
          "• \"Из Стамбула в Париж прямой 15-20 декабря, макс 500 евро\"\n\n"
          "Укажите города, диапазон дат вылета и (опционально) бюджет.\n\n"
          "Или нажмите \"Заполнить вручную\" для пошагового ввода."),
    TextInput(id="text_in", on_success=process_text_input),
    Button(Const("📝 Заполнить вручную"), id="manual_btn", on_click=on_manual_fill),
    Button(Const("Отмена"), id="cancel_start", on_click=on_cancel_dialog),
    state=NewSubSG.text_input,
)

origin_win = Window(
    Const("✈️ Укажи IATA города вылета (например, IST)"),
    TextInput(id="origin_in", on_success=set_origin),
    Button(Const("Отмена"), id="cancel", on_click=on_cancel_dialog),
    state=NewSubSG.origin,
)

dest_win = Window(
    Const("📍 Укажи IATA города назначения (например, ALA)"),
    TextInput(id="dest_in", on_success=set_destination),
    Back(Const("Назад")),
    Button(Const("Отмена"), id="cancel", on_click=on_cancel_dialog),
    state=NewSubSG.destination,
)

depart_cal_win = Window(
    Format("🗓 Выбери НАЧАЛО диапазона дат вылета\n(с какого числа искать билеты)\n\nТекущий выбор: {date_from}"),
    Calendar(id="cal_depart", on_click=on_depart_selected),
    Back(Const("Назад")),
    Button(Const("Отмена"), id="cancel", on_click=on_cancel_dialog),
    state=NewSubSG.depart_cal,
    getter=depart_getter,
)

return_cal_win = Window(
    Format("🗓 Выбери КОНЕЦ диапазона дат вылета\n(по какое число искать билеты)\n\nНачало: {date_from}\nКонец: {date_to}"),
    Calendar(id="cal_return", on_click=on_return_selected),
    Back(Const("Назад")),
    Button(Const("Отмена"), id="cancel", on_click=on_cancel_dialog),
    state=NewSubSG.return_cal,
    getter=return_getter,
)

direct_flights_win = Window(
    Const("✈️ Искать только прямые рейсы?"),
    Button(Const("✅ Да, только прямые"), id="direct_yes", on_click=choose_direct_yes),
    Button(Const("❌ Нет, можно с пересадками"), id="direct_no", on_click=choose_direct_no),
    Back(Const("Назад")),
    Button(Const("Отмена"), id="cancel", on_click=on_cancel_dialog),
    state=NewSubSG.direct_flights,
)

currency_win = Window(
    Const("Выбери валюту (или пропусти, будет использован RUB):"),
    Button(Const("💵 USD"), id="cur_usd", on_click=choose_usd),
    Button(Const("💶 EUR"), id="cur_eur", on_click=choose_eur),
    Button(Const("₽ RUB"), id="cur_rub", on_click=choose_rub),
    Button(Const("⏭ Пропустить (RUB)"), id="skip_cur", on_click=skip_currency),
    Back(Const("Назад")),
    Button(Const("Отмена"), id="cancel", on_click=on_cancel_dialog),
    state=NewSubSG.currency,
)

budget_win = Window(
    Const("Введи максимальную цену билета\n(или пропусти, чтобы не ограничивать):"),
    TextInput(id="budget_in", on_success=set_budget),
    Button(Const("⏭ Пропустить (без ограничения)"), id="skip_budget", on_click=skip_budget),
    Back(Const("Назад")),
    Button(Const("Отмена"), id="cancel", on_click=on_cancel_dialog),
    state=NewSubSG.budget,
)

confirm_win = Window(
    Format(
        "Проверяем:\n"
        "От: {origin}\n"
        "До: {destination}\n"
        "Даты вылета: {date_from} → {date_to}\n"
        "Бюджет: {price_display}\n"
        "Только прямые рейсы: {direct_display}"
    ),
    Button(Const("✅ Сохранить"), id="save", on_click=on_save),
    Back(Const("Назад")),
    Button(Const("Отмена"), id="cancel", on_click=on_cancel_dialog),
    state=NewSubSG.confirm,
    getter=confirm_getter,
)

# --- dialog ---

new_sub_dialog = Dialog(
    text_input_win,
    origin_win,
    dest_win,
    depart_cal_win,
    return_cal_win,
    direct_flights_win,
    currency_win,
    budget_win,
    confirm_win,
    on_start=on_new_sub_start,
)
