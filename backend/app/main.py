from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from app.core.config import get_settings
from app.db.session import Base, engine
import app.models.entities  # noqa: F401

settings = get_settings()
Base.metadata.create_all(bind=engine)
app = FastAPI(title=settings.app_name)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
app.mount("/", StaticFiles(directory="/app/static", html=True), name="static")
