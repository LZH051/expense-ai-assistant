import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def is_production() -> bool:
    """Vercel 或显式 APP_ENV=production/staging 都视为线上环境。"""
    return bool(
        os.getenv("VERCEL")
        or os.getenv("APP_ENV", "").strip().lower()
        in {"production", "prod", "staging"}
    )


def get_database_url() -> str:
    configured = os.getenv("DATABASE_URL", "").strip()
    if configured:
        if configured.startswith("postgres://"):
            return configured.replace("postgres://", "postgresql+psycopg://", 1)
        if configured.startswith("postgresql://"):
            return configured.replace("postgresql://", "postgresql+psycopg://", 1)
        return configured

    if is_production():
        # 不允许静默回落到本地 SQLite：serverless 实例的磁盘是临时的，
        # 各实例各写各的文件，数据会随实例回收永久丢失
        raise RuntimeError("线上部署必须配置 DATABASE_URL 环境变量。")

    database_path = (PROJECT_ROOT / "database" / "web_expense.db").resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{database_path.as_posix()}"


DATABASE_URL = get_database_url()
engine_options: dict = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
