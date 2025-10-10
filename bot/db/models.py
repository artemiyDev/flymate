from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import BigInteger, Text, Date, Boolean, Numeric, DateTime, CHAR, func, CheckConstraint
from datetime import date, datetime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int]       = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_name: Mapped[str | None]  = mapped_column(Text, nullable=True)
    language_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_premium: Mapped[bool]   = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    plan: Mapped[str]          = mapped_column(Text, nullable=False, default="basic", server_default="basic")
    subs_active_cnt: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    updated_at: Mapped["datetime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("plan in ('basic','premium')", name="users_plan_chk"),
    )


class FlightSubscription(Base):
    __tablename__ = "flight_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    origin: Mapped[str | None] = mapped_column(Text)
    destination: Mapped[str | None] = mapped_column(Text)

    range_from: Mapped["date"] = mapped_column(Date, nullable=False)
    range_to:   Mapped["date"] = mapped_column(Date, nullable=False)

    direct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    max_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency:  Mapped[str]   = mapped_column(CHAR(3), nullable=False, default="RUB", server_default="RUB")

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_checked_at: Mapped["datetime | None"] = mapped_column(DateTime(timezone=True))
    next_check_at:   Mapped["datetime | None"] = mapped_column(DateTime(timezone=True))
    check_interval_minutes: Mapped[int] = mapped_column(nullable=False, default=5, server_default="5")

    created_at: Mapped["datetime"] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped["datetime"] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())