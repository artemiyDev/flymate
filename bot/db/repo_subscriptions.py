# bot/db/repo_subscriptions.py
from datetime import datetime, timedelta, timezone
from typing import Sequence, Optional

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import FlightSubscription


UTC = timezone.utc  # Use your own TZ if needed


class SubscriptionsRepo:
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        user_id: int,
        origin: str | None,
        destination: str | None,
        range_from,  # date
        range_to,    # date
        direct: bool,
        max_price: float,
        currency: str,
        check_interval_minutes: int = 5,
        active: bool = True,
    ) -> FlightSubscription:
        sub = FlightSubscription(
            user_id=user_id,
            origin=origin,
            destination=destination,
            range_from=range_from,
            range_to=range_to,
            direct=direct,
            max_price=max_price,
            currency=currency,
            check_interval_minutes=check_interval_minutes,
            active=active,
            next_check_at=datetime.now(UTC),  # Let it be due immediately
        )
        session.add(sub)
        await session.flush()  # To get id
        return sub

    @staticmethod
    async def list_by_user(session: AsyncSession, user_id: int) -> Sequence[FlightSubscription]:
        res = await session.execute(
            select(FlightSubscription)
            .where(FlightSubscription.user_id == user_id)
            .order_by(FlightSubscription.created_at.desc())
        )
        return res.scalars().all()

    @staticmethod
    async def set_active(session: AsyncSession, sub_id: int, active: bool) -> None:
        await session.execute(
            update(FlightSubscription)
            .where(FlightSubscription.id == sub_id)
            .values(active=active)
        )

    @staticmethod
    async def bump_next_check(session: AsyncSession, sub_id: int) -> None:
        # next = now + check_interval_minutes
        res = await session.execute(
            select(FlightSubscription.check_interval_minutes)
            .where(FlightSubscription.id == sub_id)
        )
        interval = res.scalar_one()
        await session.execute(
            update(FlightSubscription)
            .where(FlightSubscription.id == sub_id)
            .values(
                last_checked_at=datetime.now(UTC),
                next_check_at=datetime.now(UTC) + timedelta(minutes=interval),
            )
        )

    @staticmethod
    async def fetch_due(session: AsyncSession, limit: int = 200) -> Sequence[FlightSubscription]:
        now = datetime.now(UTC)
        res = await session.execute(
            select(FlightSubscription)
            .where(FlightSubscription.active.is_(True))
            .where(
                (FlightSubscription.next_check_at.is_(None))
                | (FlightSubscription.next_check_at <= now)
            )
            .order_by(FlightSubscription.next_check_at.is_(None).desc(),
                      FlightSubscription.next_check_at.asc())
            .limit(limit)
        )
        return res.scalars().all()

    @staticmethod
    async def update_max_price(session: AsyncSession, sub_id: int, user_id: int, max_price: float) -> bool:
        """Update maximum price for subscription."""
        res = await session.execute(
            update(FlightSubscription)
            .where(FlightSubscription.id == sub_id, FlightSubscription.user_id == user_id)
            .values(max_price=max_price)
            .returning(FlightSubscription.id)
        )
        row = res.first()
        return row is not None

    @staticmethod
    async def delete(session: AsyncSession, sub_id: int, user_id: int) -> int:
        res = await session.execute(
            delete(FlightSubscription)
            .where(FlightSubscription.id == sub_id, FlightSubscription.user_id == user_id)
            .returning(FlightSubscription.id)
        )
        row = res.first()
        return row[0] if row else 0
