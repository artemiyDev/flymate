"""
Тесты для репозитория пользователей.
"""
import pytest
from unittest.mock import MagicMock

from bot.db.repo_users import UsersRepo


@pytest.mark.asyncio
async def test_upsert_user_new(db_session):
    """Тест создания нового пользователя через upsert."""
    # Создаём мок Telegram User
    tg_user = MagicMock()
    tg_user.id = 111222333
    tg_user.username = "new_user"

    repo = UsersRepo(db_session)
    user = await repo.upsert(tg_user)

    assert user.user_id == 111222333
    assert user.username == "new_user"
    assert user.plan == "basic"
    assert user.subs_active_cnt == 0


@pytest.mark.asyncio
async def test_upsert_user_existing(db_session):
    """Тест обновления существующего пользователя через upsert."""
    # Создаём мок Telegram User
    tg_user = MagicMock()
    tg_user.id = 444555666
    tg_user.username = "existing_user"

    repo = UsersRepo(db_session)

    # Первый раз - создание
    user1 = await repo.upsert(tg_user)
    assert user1.username == "existing_user"

    # Меняем username
    tg_user.username = "updated_user"

    # Второй раз - обновление
    user2 = await repo.upsert(tg_user)
    assert user2.user_id == 444555666
    assert user2.username == "updated_user"


@pytest.mark.asyncio
async def test_get_user(db_session):
    """Тест получения пользователя по ID."""
    # Создаём пользователя
    tg_user = MagicMock()
    tg_user.id = 777888999
    tg_user.username = "get_user_test"

    repo = UsersRepo(db_session)
    await repo.upsert(tg_user)

    # Получаем пользователя
    user = await repo.get(777888999)
    assert user is not None
    assert user.user_id == 777888999
    assert user.username == "get_user_test"


@pytest.mark.asyncio
async def test_get_user_not_found(db_session):
    """Тест получения несуществующего пользователя."""
    repo = UsersRepo(db_session)
    user = await repo.get(999999999)
    assert user is None
