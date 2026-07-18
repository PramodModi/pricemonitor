from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    InvalidURLError,
    UnsupportedPlatformError,
    ScrapeBotDetectedError,
    ScrapeError,
    PreviewNotFoundError,
    SubscriptionNotFoundError,
    DatabaseConnectionError,
)


def register_error_handlers(app: FastAPI) -> None:
    """Register all domain exception handlers on the FastAPI app."""

    @app.exception_handler(InvalidURLError)
    async def invalid_url_handler(request: Request, exc: InvalidURLError):
        return JSONResponse(
            status_code=400,
            content={"error": {
                "code": "INVALID_URL",
                "message": "The submitted URL is not a supported product page.",
                "detail": exc.detail,
            }},
        )

    @app.exception_handler(UnsupportedPlatformError)
    async def unsupported_platform_handler(request: Request, exc: UnsupportedPlatformError):
        return JSONResponse(
            status_code=400,
            content={"error": {
                "code": "UNSUPPORTED_PLATFORM",
                "message": f"{exc.domain} is not a supported platform.",
            }},
        )

    @app.exception_handler(ScrapeBotDetectedError)
    async def scrape_blocked_handler(request: Request, exc: ScrapeBotDetectedError):
        return JSONResponse(
            status_code=502,
            content={"error": {
                "code": "SCRAPE_BLOCKED",
                "message": "The marketplace blocked our request. Please try again.",
            }},
        )

    @app.exception_handler(ScrapeError)
    async def scrape_failed_handler(request: Request, exc: ScrapeError):
        return JSONResponse(
            status_code=502,
            content={"error": {
                "code": "SCRAPE_FAILED",
                "message": "Could not extract product details. Please check the URL.",
            }},
        )

    @app.exception_handler(PreviewNotFoundError)
    async def preview_not_found_handler(request: Request, exc: PreviewNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": {
                "code": "PREVIEW_NOT_FOUND",
                "message": "Preview not found or expired. Please search again.",
            }},
        )

    @app.exception_handler(SubscriptionNotFoundError)
    async def subscription_not_found_handler(request: Request, exc: SubscriptionNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": {
                "code": "SUBSCRIPTION_NOT_FOUND",
                "message": "Subscription not found.",
            }},
        )

    @app.exception_handler(DatabaseConnectionError)
    async def db_connection_handler(request: Request, exc: DatabaseConnectionError):
        return JSONResponse(
            status_code=503,
            content={"error": {
                "code": "SERVICE_UNAVAILABLE",
                "message": "Service temporarily unavailable. Try again shortly.",
            }},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
            }},
        )