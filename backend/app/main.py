from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from app.api.routes import router
from app.core.config import get_settings
from app.db.session import Base, engine
import app.models.entities  # noqa: F401

settings = get_settings()
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
                return FileResponse(index_path)
        return response


app = FastAPI(title=settings.app_name, root_path=base_path)
app.add_middleware(PrefixStripMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
static_dir = Path("/app/static")
if static_dir.exists():
    app.mount("/", SpaStaticFiles(directory=str(static_dir), html=True), name="static")
