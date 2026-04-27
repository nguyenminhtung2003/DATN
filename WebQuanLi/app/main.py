import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings, setup_cool_logging
from app.database import init_db

setup_cool_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting WebQuanLi — Drowsiness Warning System")
    await init_db()
    logger.info("✅ Database initialized")
    yield
    logger.info("🛑 Shutting down")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

# Static files
settings.STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")

# ── Routers ──
from app.auth.router import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.vehicles import router as vehicles_router
from app.api.alerts import router as alerts_router
from app.api.sessions import router as sessions_router
from app.api.control import router as control_router
from app.api.sse import router as sse_router
from app.api.pages import router as pages_router
from app.ws.jetson_handler import router as ws_router

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(vehicles_router)
app.include_router(alerts_router)
app.include_router(sessions_router)
app.include_router(control_router)
app.include_router(sse_router)
app.include_router(pages_router)
app.include_router(ws_router)
