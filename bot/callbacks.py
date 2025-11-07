# bot/callbacks.py
from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.filters.callback_data import CallbackData

from bot.db.engine import get_sessionmaker
from bot.db.repo_subscriptions import SubscriptionsRepo


class DisableSubCallback(CallbackData, prefix="disable_sub"):
    """Callback data for disabling subscription."""
    sub_id: int


async def on_disable_subscription(callback: CallbackQuery, callback_data: DisableSubCallback):
    """Handle subscription disable button click."""
    sub_id = callback_data.sub_id
    user_id = callback.from_user.id

    Session = get_sessionmaker()
    async with Session() as session:
        async with session.begin():
            # Try to delete subscription (returns sub_id if deleted, 0 otherwise)
            deleted_id = await SubscriptionsRepo.delete(session, sub_id, user_id)

    if deleted_id:
        await callback.answer("Подписка отключена!", show_alert=True)

        # Edit message to show subscription was disabled
        try:
            await callback.message.edit_text(
                f"{callback.message.text}\n\n"
                f"❌ <b>Подписка отключена</b>",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception:
            pass
    else:
        await callback.answer("Подписка не найдена или уже удалена", show_alert=True)


def build_callbacks_router() -> Router:
    """Build router for callback handlers."""
    router = Router(name="callbacks")

    # Register callback handler
    router.callback_query.register(
        on_disable_subscription,
        DisableSubCallback.filter()
    )

    return router
