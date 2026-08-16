import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    BOT_TOKEN: str = os.environ["BOT_TOKEN"]
    DATABASE_URL: str = os.environ["DATABASE_URL"]
    ADMIN_IDS: tuple[int,...] = tuple(int(x.strip()) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip())
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL","").rstrip("/")
    PAYMENT_CHANNEL_ID: int|None = int(os.environ["PAYMENT_CHANNEL_ID"]) if os.getenv("PAYMENT_CHANNEL_ID") else None
    WEBAPP_SECRET: str = os.getenv("WEBAPP_SECRET","change-me")
settings=Settings()
