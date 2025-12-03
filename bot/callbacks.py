# bot/callbacks.py
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.filters.callback_data import CallbackData

from bot.db.engine import get_sessionmaker
from bot.db.repo_subscriptions import SubscriptionsRepo
from bot.db.repo_users import UsersRepo
from bot.i18n import _, set_locale


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


async def on_language_change(callback: CallbackQuery):
    """Handle language change button click."""
    # Extract language from callback data (lang:ru or lang:en)
    lang = callback.data.split(":")[1]

    # Save to database
    Session = get_sessionmaker()
    async with Session() as session:
        async with session.begin():
            await UsersRepo.set_language(session, callback.from_user.id, lang)

    # Update current context locale
    set_locale(lang)

    # Send confirmation
    await callback.answer(_("language-changed"), show_alert=True)

    # Edit message to show confirmation
    try:
        lang_name = "Русский" if lang == "ru" else "English"
        await callback.message.edit_text(
            _("language-set", lang=lang_name)
        )
    except Exception:
        pass


def build_callbacks_router() -> Router:
    """Build router for callback handlers."""
    router = Router(name="callbacks")

    # Register callback handlers
    router.callback_query.register(
        on_disable_subscription,
        DisableSubCallback.filter()
    )

    router.callback_query.register(
        on_language_change,
        F.data.startswith("lang:")
    )

    return router
