import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings, setup_cool_logging
from app.database import async_session_factory, init_db
from app.services.hardware_incident_service import process_vehicle_heartbeat_timeouts
from app.services.history_service import purge_old_alerts

setup_cool_logging()
logger = logging.getLogger(__name__)


async def _hardware_heartbeat_watchdog(stop_event: asyncio.Event):
    from app.ws.jetson_handler import manager

    while not stop_event.is_set():
        try:
            async with async_session_factory() as db:
                await process_vehicle_heartbeat_timeouts(
                    db,
                    active_devices=set(manager.active),
                    last_seen_by_device=dict(manager.last_seen),
                    threshold_seconds=settings.HARDWARE_HEARTBEAT_TIMEOUT_SECONDS,
                )
        except Exception as exc:
            logger.warning("Hardware heartbeat watchdog skipped a cycle: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting WebQuanLi — Drowsiness Warning System")
    await init_db()
    logger.info("✅ Database initialized")
    async with async_session_factory() as db:
        deleted_alerts = await purge_old_alerts(db)
    if deleted_alerts:
        logger.info("Purged %s old alert history rows", deleted_alerts)
    stop_watchdog = asyncio.Event()
    watchdog_task = asyncio.create_task(_hardware_heartbeat_watchdog(stop_watchdog))
    try:
        yield
    finally:
        stop_watchdog.set()
        await watchdog_task
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
from app.api.penalties import router as penalties_router
from app.ws.jetson_handler import router as ws_router

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(vehicles_router)
app.include_router(alerts_router)
app.include_router(sessions_router)
app.include_router(control_router)
app.include_router(sse_router)
app.include_router(pages_router)
app.include_router(penalties_router)
app.include_router(ws_router)
