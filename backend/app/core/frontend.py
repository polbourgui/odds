import os
from pathlib import Path


def frontend_dist_dir() -> Path:
    default = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    return Path(os.environ.get("FRONTEND_DIST_DIR", default))


def resolve_frontend_path(dist_dir: Path, full_path: str) -> Path:
    """Map a request path to a file under the built frontend.

    A real built asset (JS/CSS bundle, favicon, ...) is served as-is;
    everything else (client-side routes like /stats, /events/3, or the
    root) falls back to index.html so React Router can take over.
    """
    candidate = dist_dir / full_path
    if full_path and candidate.is_file():
        return candidate
    return dist_dir / "index.html"
