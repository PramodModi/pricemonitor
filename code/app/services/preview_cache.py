import uuid
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.exceptions import PreviewNotFoundError


PREVIEW_TTL_MINUTES = 10


@dataclass
class ProductSnapshot:
    """
    Cached result of POST /products/preview.
    live_data and catalog_data are plain dicts matching the LiveData /
    CatalogData schema shapes to avoid circular imports with the schema layer.
    """
    preview_id: uuid.UUID
    expires_at: datetime
    is_new_product: bool
    live_data: dict
    catalog_data: Optional[dict] = None

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at


class PreviewCache:
    """
    Thread-safe in-memory store for ProductSnapshot objects.
    Replace with Redis at Phase 2 scale (SAD ADR-012).
    """

    def __init__(self) -> None:
        self._store: dict[str, ProductSnapshot] = {}
        self._lock = threading.RLock()

    def store(self, snapshot: ProductSnapshot) -> None:
        with self._lock:
            self._store[str(snapshot.preview_id)] = snapshot

    def get(self, preview_id: str) -> ProductSnapshot:
        """Retrieve without removing. Raises PreviewNotFoundError if absent."""
        with self._lock:
            snapshot = self._store.get(str(preview_id))
            if snapshot is None:
                raise PreviewNotFoundError(str(preview_id))
            return snapshot

    def consume(self, preview_id: str) -> ProductSnapshot:
        """Retrieve and immediately delete. Raises PreviewNotFoundError if absent."""
        with self._lock:
            snapshot = self._store.pop(str(preview_id), None)
            if snapshot is None:
                raise PreviewNotFoundError(str(preview_id))
            return snapshot

    def purge_expired(self) -> int:
        """Remove all expired entries. Called by APScheduler every 15 min."""
        with self._lock:
            expired_keys = [k for k, v in self._store.items() if v.is_expired()]
            for k in expired_keys:
                del self._store[k]
            return len(expired_keys)

    @staticmethod
    def make_expires_at() -> datetime:
        return datetime.now(timezone.utc) + timedelta(minutes=PREVIEW_TTL_MINUTES)


# Module-level singleton shared across all FastAPI requests.
preview_cache = PreviewCache()