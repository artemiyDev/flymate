# bot/main.py
import asyncio
import logging
import os
import redis

from sqlalchemy import text
from aiogram import Bot, Dispatcher, F
from aiogram.types import BotCommand, Message
from aiogram.fsm.storage.memory import MemoryStorage

from aiogram import Router
from aiogram.filters import Command
from aiogram_dialog import setup_dialogs, StartMode, DialogManager

from bot.db.repo_users import UsersRepo
from bot.middlewares.messages import AutoDeleteMiddleware
from bot.keyboards.reply import get_main_keyboard
from settings import Settings
from dialogs.new_sub import new_sub_dialog, NewSubSG
from dialogs.my_subs import my_subs_dialog, MySubsSG
from db.engine import init_db_engine, get_sessionmaker
from db.redis_client import init_redis_client, get_redis_client, close_redis_client

async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="subs", description="Мои подписки"),
        BotCommand(command="help", description="Помощь"),
    ]
    await bot.set_my_commands(commands)


def build_storage(settings: Settings):
    # Используй Redis в проде, Memory — для локалки
    if settings.REDIS_DSN:
        # r = Redis.from_url(settings.REDIS_DSN, decode_responses=False)
        # return RedisStorage(r)
        # Если хочешь прямо сейчас без Redis — оставим Memory:
        pass
    return MemoryStorage()


def build_common_router() -> Router:
    r = Router()

    @r.message(Command("start"))
    async def cmd_start(message: Message, dialog_manager: DialogManager):
        # upsert user
        Session = get_sessionmaker()
        async with Session() as session:
            async with session.begin():
                await UsersRepo.upsert_from_tg(session, message.from_user)

        # Delete /start command message
        try:
            await message.delete()
        except Exception:
            pass

        # Close all active dialogs
        await dialog_manager.reset_stack()

        # Show welcome message with persistent ReplyKeyboard
        await message.answer(
            "✈️ Flymate — ваш помощник в поиске дешёвых авиабилетов\n\n"
            "Я помогу вам отслеживать цены на интересующие маршруты и сообщу, "
            "когда появятся выгодные предложения!\n\n"
            "Создайте подписку на нужный маршрут, укажите даты и бюджет — "
            "я буду проверять цены каждые 5 минут и пришлю уведомление, "
            "как только найду подходящий вариант.\n\n"
            "Выберите действие:",
            reply_markup=get_main_keyboard(),
        )

    @r.message(Command("help"))
    async def cmd_help(message):
        await message.answer(
            "Я помогу оформить подписку на дешёвые авиабилеты.\n"
            "Команды:\n"
            "• /start — создать подписку\n"
            "• /subs — список подписок\n"
        )

    @r.message(Command("subs"))
    async def cmd_subs(message: Message, dialog_manager: DialogManager):
        # Delete /subs command message
        try:
            await message.delete()
        except Exception:
            pass

        await dialog_manager.start(MySubsSG.list, mode=StartMode.RESET_STACK)

    @r.message(Command("deal"))
    async def cmd_deal(message):
        await message.answer("Лучшие предложения появятся позже 👷")

    # Handlers for ReplyKeyboard buttons
    @r.message(F.text == "➕ Создать подписку")
    async def on_create_subscription_btn(message: Message, dialog_manager: DialogManager):
        # Delete button message
        try:
            await message.delete()
        except Exception:
            pass

        # Close all active dialogs and start new subscription dialog
        await dialog_manager.start(NewSubSG.text_input, mode=StartMode.RESET_STACK)

    @r.message(F.text == "📋 Мои подписки")
    async def on_my_subscriptions_btn(message: Message, dialog_manager: DialogManager):
        # Delete button message
        try:
            await message.delete()
        except Exception:
            pass

        # Close all active dialogs and start my subscriptions dialog
        await dialog_manager.start(MySubsSG.list, mode=StartMode.RESET_STACK)

    return r


async def load_redis_cache():
    """Load data into Redis before bot starts"""

    print("=" * 60)
    print("Loading data into Redis...")
    print("=" * 60)

    # Use global Redis client
    r = get_redis_client()

    try:
        # Test connection
        await r.ping()
        print("✓ Redis connection established")
    except Exception as e:
        print(f"✗ Redis connection error: {e}")
        return False

    try:
        # Clear old data
        print("\nClearing old data...")
        for pattern in ["airline:*", "airport:*", "city:*"]:
            keys = await r.keys(pattern)
            if keys:
                await r.delete(*keys)
        print("✓ Old data cleared")

        # Get sessionmaker
        Session = get_sessionmaker()

        # Load airlines
        print("\nLoading airlines...")
        async with Session() as session:
            result = await session.execute(
                text("SELECT code, name_en FROM airline_codes WHERE name_en IS NOT NULL")
            )
            airlines = result.fetchall()

            # Use pipeline for better performance
            async with r.pipeline() as pipe:
                for code, name_en in airlines:
                    if code and name_en:
                        await pipe.set(f"airline:{code}", name_en)
                await pipe.execute()

        print(f"✓ Loaded {len(airlines)} airlines")

        # Load airports
        print("\nLoading airports...")
        async with Session() as session:
            result = await session.execute(
                text("SELECT code, name_en FROM airport_codes WHERE name_en IS NOT NULL")
            )
            airports = result.fetchall()

            async with r.pipeline() as pipe:
                for code, name_en in airports:
                    if code and name_en:
                        await pipe.set(f"airport:{code}", name_en)
                await pipe.execute()

        print(f"✓ Loaded {len(airports)} airports")

        # Load cities
        print("\nLoading cities...")
        async with Session() as session:
            result = await session.execute(
                text("SELECT code, name_en FROM city_codes WHERE name_en IS NOT NULL")
            )
            cities = result.fetchall()

            async with r.pipeline() as pipe:
                for code, name_en in cities:
                    if code and name_en:
                        await pipe.set(f"city:{code}", name_en)
                await pipe.execute()

        print(f"✓ Loaded {len(cities)} cities")

        print("\n" + "=" * 60)
        print("✓ Redis cache loaded successfully!")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print(f"\n✗ Error loading data: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    logging.basicConfig(level=logging.INFO)

    settings = Settings()
    init_db_engine()
    init_redis_client()

    # Load Redis cache before starting bot
    cache_loaded = await load_redis_cache()
    if not cache_loaded:
        print("Warning: Redis cache failed to load, continuing anyway...")

    bot = Bot(token=settings.TG_TOKEN)
    dp = Dispatcher()

    dp.message.middleware(AutoDeleteMiddleware())

    # Routers: common handlers first, then dialogs
    dp.include_router(build_common_router())
    dp.include_router(new_sub_dialog)
    dp.include_router(my_subs_dialog)

    # Enable aiogram-dialog v2 support
    setup_dialogs(dp)

    await set_bot_commands(bot)

    try:
        # Start polling
        await dp.start_polling(bot)
    finally:
        # Cleanup on shutdown
        await close_redis_client()
        logging.info("Redis client closed")


if __name__ == "__main__":
    asyncio.run(main())
