from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.downloads import router as downloads_router
from app.api.routes.files import router as files_router
from app.config import settings
from app.database import Base, engine

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(files_router)
app.include_router(downloads_router)
