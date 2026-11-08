"""FastAPI application factory (docs/02-architecture.md §1/§4).

Run model: uvicorn on localhost:8000, CORS for http://localhost:3000 (02 §1).
"""

from fastapi import FastAPI

from app.routers.healthz import router as healthz_router
from app.version import __version__


def create_app() -> FastAPI:
    app = FastAPI(title="InvestFlow API", version=__version__)
    app.include_router(healthz_router)
    return app


app = create_app()
