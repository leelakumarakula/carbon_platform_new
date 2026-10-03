"""FastAPI application factory."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.metrics import router as metrics_router
from app.api.v1.router import api_router
from app.audit.access_log import db_access_log_writer
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logs import configure_logging
from app.core.middleware import install_middleware

configure_logging(get_settings().LOG_FORMAT, get_settings().LOG_LEVEL)   # D44: structured JSON logs


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=s.APP_NAME,
        version="0.1.0",
        description="Agricultural carbon project platform — farmer onboarding to credit retirement and payout.",
        # F1 (D47): no Swagger UI / OpenAPI document in production
        openapi_url=None if s.is_production else f"{s.API_PREFIX}/openapi.json",
        docs_url=None if s.is_production else "/docs",
        redoc_url=None,
    )
    install_middleware(app)
    app.add_middleware(  # outermost so CORS headers are added to every response, including errors
        CORSMiddleware, allow_origins=s.CORS_ORIGINS, allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"], expose_headers=["X-Request-ID"],
    )
    install_error_handlers(app)
    app.include_router(api_router, prefix=s.API_PREFIX)
    app.include_router(metrics_router)                      # GET /metrics (outside the API prefix; token-protected; D43)
    app.state.access_log_writer = db_access_log_writer
    return app


app = create_app()
