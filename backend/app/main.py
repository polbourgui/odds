import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.routes import app_settings, events, meta, paper_bets, stats, value_bets
from app.core.config import get_settings
from app.core.frontend import frontend_dist_dir, resolve_frontend_path

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


# For a same-machine self-hosted deployment (install.sh), the API also
# serves the built frontend, so there's a single process/port and no CORS
# to configure. A no-op — the route below simply isn't registered — when no
# build is present, which is the case for the test suite and for a
# split-host deployment (e.g. the frontend on Vercel) where the frontend is
# served elsewhere entirely.
_frontend_dist = frontend_dist_dir()

if _frontend_dist.is_dir():

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str) -> FileResponse:
        return FileResponse(resolve_frontend_path(_frontend_dist, full_path))
