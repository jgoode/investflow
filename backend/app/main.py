"""FastAPI application factory (docs/02-architecture.md §1/§4).

Run model: uvicorn on localhost:8000, CORS for http://localhost:3000 (02 §1).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.accounts import ensure_seeded_coa
from app.auth import AuthRuntimeState, authenticate_request_cookie, ensure_csrf_for_mutation
from app.db.connection import resolve_db_path
from app.routers.accounts import router as accounts_router
from app.routers.auth import router as auth_router
from app.routers.healthz import router as healthz_router
from app.routers.users import router as users_router
from app.version import __version__

API_EXEMPT_PATHS = {"/api/auth/register", "/api/auth/login", "/api/healthz"}


class ApiAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            if request.url.path.startswith("/api"):
                ensure_csrf_for_mutation(request)
                if request.url.path not in API_EXEMPT_PATHS:
                    request.state.current_user = authenticate_request_cookie(request)
            return await call_next(request)
        except Exception as exc:
            from fastapi import HTTPException

            if isinstance(exc, HTTPException):
                return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
            raise


def create_app() -> FastAPI:
    app = FastAPI(title="InvestFlow API", version=__version__)
    app.state.db_path = resolve_db_path()
    app.state.auth_state = AuthRuntimeState()
    ensure_seeded_coa()
    app.add_middleware(ApiAuthMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    app.include_router(healthz_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(accounts_router)
    return app


app = create_app()
