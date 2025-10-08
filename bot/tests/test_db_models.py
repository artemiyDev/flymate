"""
Тесты для моделей базы данных.
"""
import pytest
from datetime import datetime, timedelta

from bot.db.models import User, FlightSubscription


@pytest.mark.asyncio
async def test_create_user(db_session):
    """Тест создания пользователя."""
    user = User(
        user_id=123456789,
        username="test_user",
        plan="basic",
        subs_active_cnt=0
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.user_id == 123456789
    assert user.username == "test_user"
    assert user.plan == "basic"
    assert user.subs_active_cnt == 0


@pytest.mark.asyncio
async def test_create_subscription(db_session):
    """Тест создания подписки на авиамаршрут."""
    # Сначала создаём пользователя
    user = User(
        user_id=123456789,
        username="test_user",
        plan="basic",
        subs_active_cnt=0
    )
    db_session.add(user)
    await db_session.commit()

    # Создаём подписку
    subscription = FlightSubscription(
        user_id=123456789,
        origin="IST",
        destination="AMS",
        range_from=datetime.now().date(),
        range_to=(datetime.now() + timedelta(days=30)).date(),
        direct=False,
        max_price=200,
        currency="EUR",
        check_interval_minutes=5,
        active=True,
        next_check_at=datetime.now()
    )
    db_session.add(subscription)
    await db_session.commit()
    await db_session.refresh(subscription)

    assert subscription.origin == "IST"
    assert subscription.destination == "AMS"
    assert subscription.max_price == 200
    assert subscription.currency == "EUR"
    assert subscription.active is True


@pytest.mark.asyncio
async def test_user_subscriptions_relationship(db_session):
    """Тест связи между пользователем и подписками."""
    # Создаём пользователя
    user = User(
        user_id=987654321,
        username="test_user2",
        plan="premium",
        subs_active_cnt=0
    )
    db_session.add(user)
    await db_session.commit()

    # Создаём несколько подписок
    sub1 = FlightSubscription(
        user_id=987654321,
        origin="IST",
        destination="LON",
        range_from=datetime.now().date(),
        range_to=(datetime.now() + timedelta(days=15)).date(),
        direct=True,
        max_price=150,
        currency="GBP",
        check_interval_minutes=10,
        active=True,
        next_check_at=datetime.now()
    )

    sub2 = FlightSubscription(
        user_id=987654321,
        origin="IST",
        destination="PAR",
        range_from=datetime.now().date(),
        range_to=(datetime.now() + timedelta(days=20)).date(),
        direct=False,
        max_price=180,
        currency="EUR",
        check_interval_minutes=15,
        active=True,
        next_check_at=datetime.now()
    )

    db_session.add_all([sub1, sub2])
    await db_session.commit()

    # Проверяем связь
    await db_session.refresh(user)
    # Note: Нужно явно загрузить связанные объекты если используем lazy loading
    # или использовать selectinload/joinedload в запросе
