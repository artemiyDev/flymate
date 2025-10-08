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
from aiogram_dialog.api.entities.modes import ShowMode

from bot.db.engine import get_sessionmaker
from bot.db.repo_subscriptions import SubscriptionsRepo
from bot.gpt_parser import parse_text_request

class NewSubSG(StatesGroup):
    text_input = State()
    origin = State()
    destination = State()
    depart_cal = State()
    return_cal = State()
    budget = State()
    currency = State()
    confirm = State()


# --- callbacks ---

async def process_text_input(m: Message, w, manager: DialogManager, value: str):
    """Обрабатывает свободный текстовый ввод через GPT."""
    # Показываем пользователю, что идёт обработка
    await m.answer("⏳ Обрабатываю запрос...")

    # Парсим через GPT
    parsed = await parse_text_request(value)

    if not parsed:
        await m.answer(
            "❌ Не удалось распознать запрос. Возможно, сервис временно недоступен.\n\n"
            "Попробуйте:\n"
            "• Переформулировать запрос\n"
            "• Нажать \"Заполнить вручную\" для пошагового ввода"
        )
        return

    # Сохраняем распарсенные данные в dialog_data
    manager.dialog_data["origin"] = parsed.get("departure", "").upper()
    manager.dialog_data["destination"] = parsed.get("destination", "").upper()
    manager.dialog_data["date_from"] = parsed.get("range_from", "")
    manager.dialog_data["date_to"] = parsed.get("range_to", "")

    # Опциональные поля
    if "currency" in parsed:
        manager.dialog_data["currency"] = parsed.get("currency", "").upper()
    if "max_price" in parsed:
        manager.dialog_data["max_price"] = parsed.get("max_price")

    try:
        await m.delete()  # удалить ввод пользователя
    except Exception:
        pass

    manager.show_mode = ShowMode.EDIT

    # Устанавливаем значения по умолчанию, если они не указаны
    if "currency" not in manager.dialog_data:
        manager.dialog_data["currency"] = "RUB"
    if "max_price" not in manager.dialog_data:
        manager.dialog_data["max_price"] = None

    # Переходим к подтверждению (все данные уже есть или установлены по умолчанию)
    await manager.switch_to(NewSubSG.confirm)


async def set_origin(m, w, manager, value: str):
    manager.dialog_data["origin"] = value.strip().upper()
    try:
        await m.delete()                    # удалить ввод пользователя
    except Exception:
        pass
    manager.show_mode = ShowMode.EDIT       # следующий апдейт = редактирование
    await manager.next()                    # перейти к следующему окну

# destination
async def set_destination(m, w, manager, value: str):
    manager.dialog_data["destination"] = value.strip().upper()
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
    await manager.next()


async def on_return_selected(
    c: CallbackQuery, widget: Calendar, manager: DialogManager, selected_date: date
):
    manager.dialog_data["date_to"] = selected_date.isoformat()
    # проверим, что возврат не раньше вылета
    if manager.dialog_data["date_to"] < manager.dialog_data["date_from"]:
        await c.answer("Дата возврата не может быть раньше даты вылета", show_alert=True)
        return
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
    """Пропустить выбор валюты (использовать RUB по умолчанию)."""
    manager.dialog_data["currency"] = "RUB"
    manager.show_mode = ShowMode.EDIT
    await manager.next()

async def skip_budget(c: CallbackQuery, b: Button, manager: DialogManager):
    """Пропустить ввод бюджета (использовать None)."""
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
    await manager.next()  # к confirm



async def on_save(c: CallbackQuery, b: Button, manager: DialogManager):
    data = manager.dialog_data
    # минимальная валидация обязательных полей
    if not all(k in data for k in ("origin", "destination", "date_from", "date_to", "currency")):
        await c.answer("Не все параметры заполнены", show_alert=True)
        return

    # max_price может быть None (без ограничения)
    max_price_value = data.get("max_price")
    if max_price_value is not None:
        max_price_value = float(max_price_value)
    else:
        # Если None, установим очень большое значение для БД (например, 999999999)
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
    await c.answer("Подписка сохранена!", show_alert=True)
    await manager.done()


# --- getters для Format ---

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

    return {
        "origin": dialog_manager.dialog_data.get("origin", "—"),
        "destination": dialog_manager.dialog_data.get("destination", "—"),
        "date_from": dialog_manager.dialog_data.get("date_from", "—"),
        "date_to": dialog_manager.dialog_data.get("date_to", "—"),
        "price_display": price_text,
    }


# --- windows ---

text_input_win = Window(
    Const("✈️ Опишите ваш запрос в свободной форме\n\n"
          "Примеры:\n"
          "• \"С 7 октября по 23 октября из Лондона в Анталию\"\n"
          "• \"Москва - Дубай 1-10 января, до 30000 рублей\"\n"
          "• \"Из Стамбула в Париж 15-20 декабря, макс 500 евро\"\n\n"
          "Укажите города, диапазон дат вылета и (опционально) бюджет.\n\n"
          "Или нажмите \"Заполнить вручную\" для пошагового ввода."),
    TextInput(id="text_in", on_success=process_text_input),
    Button(Const("📝 Заполнить вручную"), id="manual_btn", on_click=lambda c, b, m: m.next()),
    Cancel(Const("Отмена")),
    state=NewSubSG.text_input,
)

origin_win = Window(
    Const("✈️ Укажи IATA города вылета (например, IST)"),
    TextInput(id="origin_in", on_success=set_origin),
    Cancel(Const("Отмена")),
    state=NewSubSG.origin,
)

dest_win = Window(
    Const("📍 Укажи IATA города назначения (например, ALA)"),
    TextInput(id="dest_in", on_success=set_destination),
    Back(Const("Назад")),
    Cancel(Const("Отмена")),
    state=NewSubSG.destination,
)

depart_cal_win = Window(
    Format("🗓 Выбери НАЧАЛО диапазона дат вылета\n(с какого числа искать билеты)\n\nТекущий выбор: {date_from}"),
    Calendar(id="cal_depart", on_click=on_depart_selected),
    Back(Const("Назад")),
    Cancel(Const("Отмена")),
    state=NewSubSG.depart_cal,
    getter=depart_getter,
)

return_cal_win = Window(
    Format("🗓 Выбери КОНЕЦ диапазона дат вылета\n(по какое число искать билеты)\n\nНачало: {date_from}\nКонец: {date_to}"),
    Calendar(id="cal_return", on_click=on_return_selected),
    Back(Const("Назад")),
    Cancel(Const("Отмена")),
    state=NewSubSG.return_cal,
    getter=return_getter,
)

currency_win = Window(
    Const("Выбери валюту (или пропусти, будет использован RUB):"),
    Button(Const("💵 USD"), id="cur_usd", on_click=choose_usd),
    Button(Const("💶 EUR"), id="cur_eur", on_click=choose_eur),
    Button(Const("₽ RUB"), id="cur_rub", on_click=choose_rub),
    Button(Const("⏭ Пропустить (RUB)"), id="skip_cur", on_click=skip_currency),
    Back(Const("Назад")),
    Cancel(Const("Отмена")),
    state=NewSubSG.currency,
)

budget_win = Window(
    Const("Введи максимальную цену билета\n(или пропусти, чтобы не ограничивать):"),
    TextInput(id="budget_in", on_success=set_budget),
    Button(Const("⏭ Пропустить (без ограничения)"), id="skip_budget", on_click=skip_budget),
    Back(Const("Назад")),
    Cancel(Const("Отмена")),
    state=NewSubSG.budget,
)

confirm_win = Window(
    Format(
        "Проверяем:\n"
        "От: {origin}\n"
        "До: {destination}\n"
        "Даты вылета: {date_from} → {date_to}\n"
        "Бюджет: {price_display}"
    ),
    Button(Const("✅ Сохранить"), id="save", on_click=on_save),
    Back(Const("Назад")),
    Cancel(Const("Отмена")),
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
    currency_win,
    budget_win,
    confirm_win,
)
