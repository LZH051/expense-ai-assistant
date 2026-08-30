from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from web_database import Base


class WebUser(Base):
    __tablename__ = "web_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    expenses: Mapped[list["WebExpense"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    budgets: Mapped[list["WebBudget"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class LoginAttempt(Base):
    """登录失败记录，用于限流。存数据库而不是进程内存：
    serverless 每个实例内存独立，进程内计数挡不住分布式撞库。"""

    __tablename__ = "web_login_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class WebExpense(Base):
    __tablename__ = "web_expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("web_users.id", ondelete="CASCADE"), index=True
    )
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    merchant: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[WebUser] = relationship(back_populates="expenses")


class WebAiAnalysis(Base):
    """AI 消费分析结果，按 用户×月份 缓存：同月重复生成覆盖更新，
    浏览时读库展示，不重复调用付费接口。"""

    __tablename__ = "web_ai_analyses"
    __table_args__ = (
        UniqueConstraint("user_id", "month"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("web_users.id", ondelete="CASCADE"), index=True
    )
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )


class WebBudget(Base):
    __tablename__ = "web_budgets"
    __table_args__ = (
        UniqueConstraint("user_id", "budget_month", "category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("web_users.id", ondelete="CASCADE"), index=True
    )
    budget_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[WebUser] = relationship(back_populates="budgets")
