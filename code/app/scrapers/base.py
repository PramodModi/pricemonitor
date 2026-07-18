from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional
from playwright.sync_api import Page


@dataclass
class ScrapeResult:
    marketplace_product_id: str
    current_price: Decimal
    name: Optional[str] = None
    brand: Optional[str] = None
    image_url: Optional[str] = None
    availability: bool = True
    rating: Optional[Decimal] = None
    review_count: Optional[int] = None
    seller: Optional[str] = None
    currency: str = "INR"


class BaseScraper(ABC):

    @abstractmethod
    def extract(self, page: Page, url: str) -> ScrapeResult:
        raise NotImplementedError

    def _parse_price(self, raw: str) -> Decimal:
        cleaned = raw.replace("₹", "").replace(",", "").strip()
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            raise ValueError(f"Cannot parse price from: {raw!r}")