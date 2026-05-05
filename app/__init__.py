from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import PASSWORD, STATIC_DIR
from app.database import init_db
from app.routes.files import router as files_router
from app.routes.tags import router as tags_router
from app.routes.charts import router as charts_router
from app.routes.auth import router as auth_router

AUTH_PATHS = {"/api/login"}


def create_app() -> FastAPI:
    init_db()

    app = FastAPI(title="OTA Data Comparison")

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        if PASSWORD and request.url.path.startswith("/api/") and request.url.path not in AUTH_PATHS:
            token = request.cookies.get("auth_token", "") or request.headers.get("X-Auth-Token", "")
            if token != PASSWORD:
                return JSONResponse(
                    status_code=401,
                    content={"ok": False, "error": "未授权访问，请先登录"},
                )
        return await call_next(request)

    app.include_router(auth_router)
    app.include_router(files_router)
    app.include_router(tags_router)
    app.include_router(charts_router)

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app
