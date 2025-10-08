"""
Тесты для репозитория подписок.
"""
import pytest
from datetime import datetime, timedelta

from bot.db.models import User
from bot.db.repo_subscriptions import SubscriptionsRepo


@pytest.mark.asyncio
async def test_create_subscription(db_session):
    """Тест создания подписки."""
    # Создаём пользователя
    user = User(
        user_id=111111111,
        username="sub_test_user",
        plan="basic",
        subs_active_cnt=0
    )
    db_session.add(user)
    await db_session.commit()

    # Создаём подписку
    repo = SubscriptionsRepo(db_session)
    subscription = await repo.create(
        user_id=111111111,
        origin="IST",
        destination="BCN",
        range_from=datetime.now().date(),
        range_to=(datetime.now() + timedelta(days=30)).date(),
        direct=False,
        max_price=250,
        currency="EUR",
        check_interval_minutes=5
    )

    assert subscription.id is not None
    assert subscription.user_id == 111111111
    assert subscription.origin == "IST"
    assert subscription.destination == "BCN"
    assert subscription.max_price == 250
    assert subscription.active is True


@pytest.mark.asyncio
async def test_get_active_by_user(db_session):
    """Тест получения активных подписок пользователя."""
    # Создаём пользователя
    user = User(
        user_id=222222222,
        username="multi_sub_user",
        plan="basic",
        subs_active_cnt=0
    )
    db_session.add(user)
    await db_session.commit()

    # Создаём несколько подписок
    repo = SubscriptionsRepo(db_session)

    sub1 = await repo.create(
        user_id=222222222,
        origin="IST",
        destination="ROM",
        range_from=datetime.now().date(),
        range_to=(datetime.now() + timedelta(days=20)).date(),
        direct=True,
        max_price=200,
        currency="EUR",
        check_interval_minutes=10
    )

    sub2 = await repo.create(
        user_id=222222222,
        origin="IST",
        destination="BER",
        range_from=datetime.now().date(),
        range_to=(datetime.now() + timedelta(days=25)).date(),
        direct=False,
        max_price=180,
        currency="EUR",
        check_interval_minutes=15
    )

    # Получаем активные подписки
    subscriptions = await repo.get_active_by_user(222222222)
    assert len(subscriptions) == 2
    assert {sub.destination for sub in subscriptions} == {"ROM", "BER"}


@pytest.mark.asyncio
async def test_fetch_due(db_session):
    """Тест получения подписок, готовых к проверке."""
    # Создаём пользователя
    user = User(
        user_id=333333333,
        username="due_test_user",
        plan="basic",
        subs_active_cnt=0
    )
    db_session.add(user)
    await db_session.commit()

    # Создаём подписку с прошедшим временем проверки
    repo = SubscriptionsRepo(db_session)
    subscription = await repo.create(
        user_id=333333333,
        origin="IST",
        destination="MAD",
        range_from=datetime.now().date(),
        range_to=(datetime.now() + timedelta(days=30)).date(),
        direct=False,
        max_price=220,
        currency="EUR",
        check_interval_minutes=5
    )

    # Устанавливаем next_check_at в прошлое
    subscription.next_check_at = datetime.now() - timedelta(minutes=10)
    await db_session.commit()

    # Получаем подписки, готовые к проверке
    due_subscriptions = await repo.fetch_due()
    assert len(due_subscriptions) >= 1
    assert any(sub.id == subscription.id for sub in due_subscriptions)


@pytest.mark.asyncio
async def test_bump_next_check(db_session):
    """Тест обновления времени следующей проверки."""
    # Создаём пользователя
    user = User(
        user_id=444444444,
        username="bump_test_user",
        plan="basic",
        subs_active_cnt=0
    )
    db_session.add(user)
    await db_session.commit()

    # Создаём подписку
    repo = SubscriptionsRepo(db_session)
    subscription = await repo.create(
        user_id=444444444,
        origin="IST",
        destination="VIE",
        range_from=datetime.now().date(),
        range_to=(datetime.now() + timedelta(days=30)).date(),
        direct=False,
        max_price=190,
        currency="EUR",
        check_interval_minutes=5
    )

    old_next_check = subscription.next_check_at

    # Обновляем время следующей проверки
    await repo.bump_next_check(subscription.id)
    await db_session.refresh(subscription)

    # Проверяем, что время увеличилось примерно на 5 минут
    time_diff = (subscription.next_check_at - old_next_check).total_seconds()
    assert 4 * 60 <= time_diff <= 6 * 60  # от 4 до 6 минут (с погрешностью)
