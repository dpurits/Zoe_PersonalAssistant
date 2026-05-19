from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from zoe_assistant.config import get_settings
from zoe_assistant.db import init_db
from zoe_assistant.routes import assistant, briefings, google, portfolio, twilio
from zoe_assistant.scheduler import build_scheduler


def create_app() -> FastAPI:
    settings = get_settings()
    scheduler = build_scheduler(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.token_store == "database":
            init_db()
        scheduler.start()
        try:
            yield
        finally:
            scheduler.shutdown(wait=False)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.include_router(assistant.router)
    app.include_router(briefings.router)
    app.include_router(google.router)
    app.include_router(portfolio.router)
    app.include_router(twilio.router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name, "environment": settings.app_env}

    return app


app = create_app()
