from pathlib import Path
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from app.api.routes import router
from app.api.client_directory import router as client_directory_router
from app.core.config import get_settings
from app.db.session import Base, engine
import app.models.entities  # noqa: F401
from app.services.ftp_scheduler import start_ftp_scheduler, stop_ftp_scheduler

settings = get_settings()
logger = logging.getLogger(__name__)
base_path = settings.normalized_base_path
if settings.auto_create_tables:
    Base.metadata.create_all(bind=engine)


class PrefixStripMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if base_path and request.scope["path"].startswith(base_path):
            request.scope["root_path"] = base_path
            request.scope["path"] = request.scope["path"][len(base_path):] or "/"
        return await call_next(request)


class SpaStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 404 and not scope["path"].startswith("/api"):
            index_path = Path(self.directory) / "index.html"
            if index_path.exists():
                response = FileResponse(index_path)
        # index.html ссылается на хешированные Vite-ресурсы. Запрещаем хранить
        # сам HTML в кеше, чтобы после выкладки браузер сразу увидел новый bundle.
        if path in {"", ".", "index.html"} or response.media_type == "text/html":
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler_started = False
    try:
        start_ftp_scheduler()
        scheduler_started = True
    except Exception:
        # Ошибка необязательной FTP-автозагрузки не должна выключать реестр,
        # API и статический frontend целиком (nginx в таком случае отдаёт 502).
        logger.exception("Не удалось запустить планировщик FTP; приложение продолжит работу")
    try:
        yield
    finally:
        if scheduler_started:
            stop_ftp_scheduler()


app = FastAPI(title=settings.app_name, root_path=base_path, lifespan=lifespan)
app.add_middleware(PrefixStripMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
# Специализированные /api/clients/changes должны регистрироваться раньше
# динамического маршрута /api/clients/{client_id} основного router.
app.include_router(client_directory_router)
app.include_router(router)
app.include_router(client_directory_router)
static_dir = Path("/app/static")
if static_dir.exists():
    app.mount("/", SpaStaticFiles(directory=str(static_dir), html=True), name="static")
