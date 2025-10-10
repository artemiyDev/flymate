from typing import Optional
from aiogram.types import User as TgUser
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from bot.db.models import User

class UsersRepo:
    @staticmethod
    async def upsert_from_tg(session: AsyncSession, tg: TgUser, plan: str | None = None) -> User:
        values = {
            "user_id": tg.id,
            "username": tg.username,
            "first_name": tg.first_name,
            "last_name": tg.last_name,
            "language_code": getattr(tg, "language_code", None),
            "is_premium": bool(getattr(tg, "is_premium", False)),
        }
        if plan:
            values["plan"] = plan

        stmt = insert(User).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[User.user_id],
            set_={
                "username": stmt.excluded.username,
                "first_name": stmt.excluded.first_name,
                "last_name": stmt.excluded.last_name,
                "language_code": stmt.excluded.language_code,
                "is_premium": stmt.excluded.is_premium,
                **({"plan": stmt.excluded.plan} if plan else {}),
            },
        ).returning(User)

        res = await session.execute(stmt)
        row = res.scalar_one()
        return row

    @staticmethod
    async def set_plan(session: AsyncSession, user_id: int, plan: str) -> None:
        await session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(plan=plan)
        )

    @staticmethod
    async def get(session: AsyncSession, user_id: int) -> Optional[User]:
        res = await session.execute(select(User).where(User.user_id == user_id))
        return res.scalar_one_or_none()
