from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR
from app.database import init_db
from app.routes.files import router as files_router
from app.routes.tags import router as tags_router
from app.routes.charts import router as charts_router


def create_app() -> FastAPI:
    init_db()

    app = FastAPI(title="OTA Data Comparison")
    app.include_router(files_router)
    app.include_router(tags_router)
    app.include_router(charts_router)

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app
