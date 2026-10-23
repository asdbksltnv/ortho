import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import audit_routes, auth_routes, cases, documents, health, intake, meta, users, wards
from app.api.errors import register_error_handlers
from app.logging_config import configure_logging
from app.security import security_headers
from app.services.config_loader import get_config
from app.settings import get_settings

logger = logging.getLogger("app")


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_for_web()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="OrthoReady",
        version=__version__,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.middleware("http")(security_headers)
    register_error_handlers(app)
    get_config()  # fail fast on invalid clinical configuration

    app.include_router(health.router, prefix="/api")
    for module in (meta, auth_routes, users, wards, cases, intake, documents, audit_routes):
        app.include_router(module.router, prefix="/api/v1")

    _mount_frontend(app, Path(settings.frontend_dist))
    logger.info("startup env=%s demo_mode=%s", settings.env, settings.demo_mode)
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    if not index.is_file():
        logger.warning("frontend build not found at %s; serving API only", dist)
        return

    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist.resolve()):
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
