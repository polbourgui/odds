import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import app_settings, events, meta, paper_bets, stats, value_bets
from app.core.config import get_settings

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(title="Odds", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)

app.include_router(value_bets.router)
app.include_router(meta.router)
app.include_router(events.router)
app.include_router(paper_bets.router)
app.include_router(app_settings.router)
app.include_router(stats.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
