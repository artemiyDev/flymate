# bot/main.py
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import BotCommand, Message
from aiogram.fsm.storage.memory import MemoryStorage

from aiogram import Router
from aiogram.filters import Command
from aiogram_dialog import setup_dialogs, StartMode, DialogManager

from bot.db.repo_users import UsersRepo
from settings import Settings
from dialogs.new_sub import new_sub_dialog, NewSubSG
from dialogs.my_subs import my_subs_dialog, MySubsSG
from db.engine import init_db_engine, get_sessionmaker

async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Онбординг / создать подписку"),
        BotCommand(command="subs", description="Мои подписки"),
        BotCommand(command="deal", description="Лучшие предложения сейчас"),
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

        # запустить диалог
        await dialog_manager.start(NewSubSG.text_input, mode=StartMode.RESET_STACK)

    @r.message(Command("help"))
    async def cmd_help(message):
        await message.answer(
            "Я помогу оформить подписку на дешёвые авиабилеты.\n"
            "Команды:\n"
            "• /start — создать подписку\n"
            "• /subs — список подписок\n"
            "• /deal — лучшие предложения"
        )

    @r.message(Command("subs"))
    async def cmd_subs(message: Message, dialog_manager: DialogManager):
        await dialog_manager.start(MySubsSG.list, mode=StartMode.RESET_STACK)

    @r.message(Command("deal"))
    async def cmd_deal(message):
        await message.answer("Лучшие предложения появятся позже 👷")

    return r


async def main():
    logging.basicConfig(level=logging.INFO)

    settings = Settings()
    init_db_engine()

    bot = Bot(token=settings.TG_TOKEN)
    dp = Dispatcher()


    # Роутеры: сначала обычные, потом диалоги
    dp.include_router(build_common_router())
    dp.include_router(new_sub_dialog)
    dp.include_router(my_subs_dialog)

    # Включаем поддержку aiogram-dialog v2
    setup_dialogs(dp)

    await set_bot_commands(bot)

    # Если у тебя есть APScheduler — поднимай его тут (асинхронно) до старта polling

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
