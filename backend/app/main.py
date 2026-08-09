import asyncio
import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import accounts, chats
from .services.sync import poll_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("woyqe")


@asynccontextmanager
async def lifespan(app: FastAPI):
    poller_task = None
    if settings.ENABLE_POLLER:
        logger.info("Starting background message poller (interval=%ss)", settings.POLL_INTERVAL_SECONDS)
        poller_task = asyncio.create_task(poll_loop())
    try:
        yield
    finally:
        if poller_task:
            poller_task.cancel()
            try:
                await poller_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="Woyqe API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts.router)
app.include_router(chats.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "woyqe"}
