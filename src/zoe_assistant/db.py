from sqlalchemy import LargeBinary, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from zoe_assistant.config import get_settings


class Base(DeclarativeBase):
    pass


class AppSecret(Base):
    __tablename__ = "app_secrets"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


def _database_url() -> str:
    url = get_settings().database_url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def save_secret(key: str, value: bytes) -> None:
    with SessionLocal() as session:
        secret = session.get(AppSecret, key)
        if secret is None:
            secret = AppSecret(key=key, value=value)
            session.add(secret)
        else:
            secret.value = value
        session.commit()


def load_secret(key: str) -> bytes | None:
    with SessionLocal() as session:
        secret = session.get(AppSecret, key)
        return secret.value if secret else None
