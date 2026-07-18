import requests
from dataclasses import dataclass
from typing import Optional
from streamlit_app.config import settings


@dataclass
class APIResponse:
    ok: bool
    data: Optional[dict]
    error_code: Optional[str]
    error_message: Optional[str]


def _call(method: str, path: str, **kwargs) -> APIResponse:
    try:
        response = requests.request(
            method,
            f"{settings.api_base_url}{path}",
            timeout=120,  # preview scrape can take up to 60s
            **kwargs,
        )
        if response.ok:
            return APIResponse(
                ok=True,
                data=response.json(),
                error_code=None,
                error_message=None,
            )
        body = response.json()
        error = body.get("error", {})
        return APIResponse(
            ok=False,
            data=None,
            error_code=error.get("code", "UNKNOWN_ERROR"),
            error_message=error.get("message", "Something went wrong."),
        )
    except requests.exceptions.ConnectionError:
        return APIResponse(
            ok=False,
            data=None,
            error_code="CONNECTION_ERROR",
            error_message="Cannot reach the PriceMonitor server.",
        )
    except requests.exceptions.Timeout:
        return APIResponse(
            ok=False,
            data=None,
            error_code="TIMEOUT",
            error_message="The request timed out. Please try again.",
        )
    except Exception as e:
        return APIResponse(
            ok=False,
            data=None,
            error_code="UNKNOWN_ERROR",
            error_message=str(e),
        )


def preview_product(url: str) -> APIResponse:
    return _call("POST", "/v1/products/preview", json={"url": url})


def confirm_subscription(preview_id: str, email: str) -> APIResponse:
    return _call(
        "POST",
        "/v1/subscriptions",
        json={"preview_id": preview_id, "email": email},
    )


def get_items(email: str) -> APIResponse:
    return _call("GET", "/v1/items", params={"email": email})


def get_product(product_id: str) -> APIResponse:
    return _call("GET", f"/v1/products/{product_id}")


def delete_subscription(subscription_id: str, email: str) -> APIResponse:
    return _call(
        "DELETE",
        f"/v1/subscriptions/{subscription_id}",
        params={"email": email},
    )


def get_health() -> APIResponse:
    return _call("GET", "/health")