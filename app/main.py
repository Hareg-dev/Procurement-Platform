from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.db import close_db, init_db
from app.core.request_context import (
    is_valid_request_id,
    new_request_id,
    reset_request_id,
    set_request_id,
)
from app.services.procurement.errors import DomainError


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events for the FastAPI application.
    """
    # Startup - create tables if they don't exist
    await init_db()
    yield
    # Shutdown
    await close_db()


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        FastAPI: Configured FastAPI application instance
    """
    app = FastAPI(
        title=settings.project_name,
        version=settings.project_version,
        openapi_url=f"{settings.api_v1_str}/openapi.json",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        """Attach a trace id to the request and echo it to the client."""
        supplied = request.headers.get("X-Request-ID", "")
        request_id = (
            supplied if is_valid_request_id(supplied) else new_request_id()
        )
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)
        response.headers["X-Request-ID"] = request_id
        return response

    # Set up CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    from app.api.v1.api import api_router
    from app.api.v2.api import api_v2_router

    app.include_router(api_router, prefix=settings.api_v1_str)
    app.include_router(api_v2_router, prefix=settings.api_v2_str)

    @app.exception_handler(DomainError)
    async def domain_error_handler(
        request: Request, exc: DomainError
    ) -> JSONResponse:
        """Map domain errors (409/403/404/400) to a consistent JSON shape."""
        return JSONResponse(
            status_code=exc.status_code, content={"detail": str(exc)}
        )

    @app.get("/")
    async def root():
        """Root endpoint for health check."""
        return {
            "message": "Welcome to Procurement Platform API",
            "version": settings.project_version,
            "environment": settings.environment,
        }

    @app.get("/health")
    def health_check():
        """Simple health check endpoint."""
        return {"status": "ok", "service": "procurement-platform"}

    return app


# Create the FastAPI application
app = create_application()