"""
ProductIdentityService — cross-portal product identity matching.

File: app/services/product_identity.py

Responsibilities:
  1. normalize_name()          — strip specs/variants from raw portal titles
  2. extract_model_number()    — pull manufacturer model number from specs dict
  3. extract_isbn()            — pull ISBN from specs dict (books)
  4. find_or_create_canonical()— find existing canonical product or create new one

Called from products.py PATH B (preview) after a successful scrape.
Called from scraper_worker._write_result() after a successful cron scrape (v5.1).

Design:
  - Stateless service — no instance state, no DB held as attribute
  - All DB operations go through CanonicalProductRepository
  - Never raises — returns None when matching fails so caller can proceed
  - f-strings only for logging (DEV-006)

v5.1: find_by_brand_and_name() in CanonicalProductRepository now uses PostgreSQL
      pg_trgm similarity() instead of Python-side Jaccard. No change to this
      service — the interface is identical, only the DB query changed.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.core.models.canonical_product import CanonicalProduct
from app.repositories.canonical_product_repo import CanonicalProductRepository

logger = logging.getLogger(__name__)

# ── Model number extraction ────────────────────────────────────────────────────
# Keys to look for in product_metadata["specs"] dict, in priority order.
# First key that returns a non-empty value wins.
_MODEL_NUMBER_KEYS = [
    "Model Number",
    "Model",
    "Model Name",
    "Part Number",
    "Manufacturer Part Number",
    "Item model number",
    "Style Code",         # footwear
    "Style",
    "SKU",
]

_ISBN_KEYS = [
    "ISBN-13",
    "ISBN-10",
    "ISBN",
    "ASIN",              # Amazon uses ASIN as ISBN equivalent for books
]

# ── Name normalization patterns ────────────────────────────────────────────────
# Parenthesized specs — (8GB RAM, 128GB), (Cobalt Violet, 128 GB)
# Only strip when content contains digits + storage/memory units
_SPEC_PAREN_RE = re.compile(
    r'\([^)]*\b(GB|TB|MB|RAM|ROM|mAh|mah|inch|cm|mm|Hz|W|MP|L|ml|kg|g)\b[^)]*\)',
    re.IGNORECASE,
)
# Amazon marketing suffix — everything after the first pipe
_PIPE_SUFFIX_RE = re.compile(r'\|.*$')
# Multiple spaces
_MULTI_SPACE_RE = re.compile(r'\s+')

# ── Known noise words to strip from the end of names ──────────────────────────
_NOISE_SUFFIXES = [
    "smartphone", "mobile phone", "cell phone",
    "laptop", "notebook",
    "truly wireless", "wireless earbuds", "earphones", "headphones",
    "smartwatch", "smart watch",
    "power bank",
]


class ProductIdentityService:
    """
    Stateless service for product identity matching and name normalization.

    Usage in products.py PATH B:

        from app.services.product_identity import product_identity_service

        identity = product_identity_service.find_or_create_canonical(
            db=db,
            platform=validated.platform,
            name=result.name,
            brand=result.brand,
            category=result.category or "other",
            image_url=result.image_url,
            specs=specs_from_metadata,
        )
        if identity:
            product_repo.update_canonical_id(db_product, identity.canonical_id)
            product_repo.update_model_number(db_product, identity.model_number)
            product_repo.update_normalized_name(db_product, identity.normalized_name)
    """

    # ── Public API ────────────────────────────────────────────────────────────

    def find_or_create_canonical(
        self,
        db: Session,
        platform: str,
        name: Optional[str],
        brand: Optional[str],
        category: str,
        image_url: Optional[str],
        specs: dict,
    ) -> Optional[CanonicalProduct]:
        """
        Find an existing canonical product or create a new one.

        Match priority:
          1. model_number exact match       — electronics, footwear (~90% hit rate)
          2. isbn exact match               — books (100% hit rate)
          3. brand + name similarity ≥ 0.85 — fuzzy fallback
          4. No match → create new canonical product

        Fashion category (category == "fashion") skips matching entirely —
        fashion products have no model numbers and names are too similar across
        variants (color, size) to match safely. Each fashion listing gets its
        own canonical product.

        Returns:
            CanonicalProduct on success (found or created).
            None when name and brand are both None (can't create meaningful record).
            Never raises.
        """
        try:
            if not name and not brand:
                logger.debug(
                    f"[IDENTITY] skipping — no name or brand — platform={platform}"
                )
                return None

            repo = CanonicalProductRepository(db)

            normalized = self.normalize_name(name or "", brand or "", specs)
            model_number = self.extract_model_number(specs)
            isbn = self.extract_isbn(specs)

            # Fallback: extract model number from name when specs are empty
            # Covers Amazon browser scrapes where specs=0 but model code is in title
            if not model_number and name:
                model_number = self.extract_model_number_from_name(name)
                if model_number:
                    logger.info(
                        f"[IDENTITY] model_number extracted from name — "
                        f"model_number={model_number!r}"
                    )

            logger.info(
                f"[IDENTITY] matching — "
                f"platform={platform} "
                f"normalized={normalized!r} "
                f"brand={brand!r} "
                f"model_number={model_number!r} "
                f"isbn={isbn!r} "
                f"category={category}"
            )

            # ── Fashion: skip cross-portal matching ───────────────────────────
            # Fashion items have no model numbers. Name similarity is unreliable
            # because "Blue Floral Dress" and "Red Floral Dress" would match at
            # high similarity but are different products (different color).
            # Each fashion listing gets its own canonical product.
            if category == "fashion":
                logger.info(
                    f"[IDENTITY] fashion category — "
                    f"skipping cross-portal match, creating new canonical"
                )
                return repo.create(
                    normalized_name=normalized,
                    brand=self._normalize_brand(brand),
                    category=category,
                    image_url=image_url,
                    model_number=None,
                    isbn=None,
                )

            # ── Step 1: model number exact match ──────────────────────────────
            if model_number:
                existing = repo.find_by_model_number(model_number)
                if existing:
                    logger.info(
                        f"[IDENTITY] model_number match — "
                        f"canonical_id={existing.canonical_id} "
                        f"model_number={model_number!r}"
                    )
                    # Update image if the existing canonical has none
                    if not existing.image_url and image_url:
                        repo.update_image(existing, image_url)
                    return existing

            # ── Step 2: ISBN exact match (books) ──────────────────────────────
            if isbn:
                existing = repo.find_by_isbn(isbn)
                if existing:
                    logger.info(
                        f"[IDENTITY] isbn match — "
                        f"canonical_id={existing.canonical_id} "
                        f"isbn={isbn!r}"
                    )
                    return existing

            # ── Step 3: brand + name similarity ──────────────────────────────
            if brand and normalized:
                existing = repo.find_by_brand_and_name(
                    brand=brand,
                    normalized_name=normalized,
                    threshold=0.85,
                )
                if existing:
                    logger.info(
                        f"[IDENTITY] name similarity match — "
                        f"canonical_id={existing.canonical_id} "
                        f"normalized={normalized!r}"
                    )
                    return existing

            # ── Step 4: no match — create new canonical product ───────────────
            logger.info(
                f"[IDENTITY] no match — creating new canonical product — "
                f"normalized={normalized!r} brand={brand!r}"
            )
            return repo.create(
                normalized_name=normalized,
                brand=self._normalize_brand(brand),
                category=category,
                image_url=image_url,
                model_number=model_number,
                isbn=isbn,
            )

        except Exception as exc:
            logger.warning(
                f"[IDENTITY] find_or_create_canonical failed — "
                f"platform={platform} name={name!r:.50} "
                f"error={type(exc).__name__}: {exc}"
            )
            return None

    def normalize_name(
        self,
        raw_name: str,
        brand: str,
        specs: dict,
    ) -> str:
        """
        Strip variant specs and marketing noise from a raw portal product title.

        Goal: "Samsung Galaxy S24 5G" not "SAMSUNG Galaxy S24 5G (8GB,128GB) | AI Phone"

        Steps:
          1. Strip everything after | (Amazon/Flipkart marketing suffix)
          2. Strip parenthesized specs containing storage/memory units
          3. Strip known color names found in specs
          4. Normalize brand casing (SAMSUNG → Samsung)
          5. Strip trailing noise words (case-insensitive)
          6. Clean up whitespace

        Returns the normalized name, or the original raw_name if normalization
        produces an empty string (safety fallback).
        """
        if not raw_name:
            return ""

        name = raw_name.strip()

        # Step 1: strip Amazon/Flipkart pipe suffix
        name = _PIPE_SUFFIX_RE.sub("", name).strip()

        # Step 2: strip parenthesized specs (8GB RAM, 128GB storage, etc.)
        name = _SPEC_PAREN_RE.sub("", name).strip()

        # Step 2b: strip parenthesized content up to 60 chars
        # Catches: "(Blue, 29)", "(Black)", "(Push Button)", "(Fry Pan, Kadhai, Pressure Cooker)"
        # 60-char threshold covers Flipkart accessory compatibility lists without
        # stripping legitimate longer parenthetical product descriptions.
        name = re.sub(r'\([^)]{0,60}\)', '', name).strip()

        # Step 3: strip color from name when it's in specs
        color = (
            specs.get("Color")
            or specs.get("Colour")
            or specs.get("color")
            or ""
        )
        if color and len(color) > 2:
            # Only strip if color appears as a standalone word (not substring)
            color_pattern = re.compile(
                r'\b' + re.escape(color) + r'\b', re.IGNORECASE
            )
            name = color_pattern.sub("", name).strip()

        # Step 4: normalize brand casing at start of name
        brand_clean = self._normalize_brand(brand) or ""
        if brand_clean and name.upper().startswith(brand_clean.upper()):
            name = brand_clean + name[len(brand_clean):]

        # Step 5: strip trailing noise suffixes
        for suffix in _NOISE_SUFFIXES:
            pattern = re.compile(r'\b' + re.escape(suffix) + r'\s*$', re.IGNORECASE)
            name = pattern.sub("", name).strip()

        # Step 6: clean up whitespace and trailing punctuation
        name = _MULTI_SPACE_RE.sub(" ", name).strip(" ,|-")

        return name if name else raw_name.strip()

    def extract_model_number(self, specs: dict) -> Optional[str]:
        """
        Extract manufacturer model number from the specs dict.

        Tries keys in _MODEL_NUMBER_KEYS priority order.
        Returns the first non-empty value found, uppercased and stripped.
        Returns None when no model number is present.

        The returned value is stored on both products.model_number and
        canonical_products.model_number for fast cross-portal lookup.
        """
        if not specs:
            return None

        for key in _MODEL_NUMBER_KEYS:
            value = specs.get(key)
            if value and isinstance(value, str) and value.strip():
                clean = value.strip().upper()
                # Reject generic placeholder values
                if clean in ("N/A", "NA", "NONE", "NULL", "-", "NOT APPLICABLE"):
                    continue
                # Reject values that are too short to be a real model number.
                # Single digits or 2-3 char values are almost always a product
                # series number (e.g. "29" for Prestige 29 series) not a model
                # number suitable for cross-portal matching.
                if len(clean) < 4:
                    continue
                # Reject values that are pure integers — these are sizes/wattage/
                # capacity specs that leaked into the model number field.
                # Real model numbers contain at least one letter.
                if re.match(r'^\d+$', clean):
                    continue
                return clean

        return None

    def extract_model_number_from_name(self, name: str) -> Optional[str]:
        """
        Fallback: extract a model number from the raw product name when specs
        are empty (e.g. Amazon browser scrape that returned specs=0).

        Matches patterns commonly found in product titles:
          HD4928/01  — Philips model codes (letters + digits + slash + digits)
          SM-S921B   — Samsung model codes (letters + hyphen + alphanumeric)
          AH8050-002 — Nike style codes
          PIC16.0    — Prestige codes

        Rules:
          - Must start with 2+ uppercase letters
          - Must contain at least one digit
          - Must be 4+ chars total
          - Must not be a pure integer
          - Avoids matching common abbreviations: "W" (watts), "V" (volts),
            "Hz", "GHz", "USB", "LED" etc.

        Returns the first match or None.
        """
        if not name:
            return None

        # Common abbreviations/words that look like model numbers but aren't
        _NOISE_TOKENS = {
            "USB", "LED", "LCD", "LPG", "PNG", "JPG", "RGB", "API",
            "CPU", "GPU", "RAM", "ROM", "SSD", "HDD", "UHD", "HDR",
            "UPS", "GPS", "NFC", "OTG", "MIC", "AUX", "RMS", "HDMI",
            "WiFi", "WIFI", "ISI", "BIS", "MRP", "EMI", "GST",
        }

        # Pattern: 2+ uppercase letters, then digit(s), then optional
        # alphanumeric/separator chars — the core structure of a model number
        candidates = re.findall(
            r'\b([A-Z]{2,}[0-9][A-Z0-9/\-\.]{1,}|[A-Z]{1,2}-[A-Z0-9]{3,})\b',
            name,
        )

        for candidate in candidates:
            if len(candidate) < 4:
                continue
            if re.match(r'^\d+$', candidate):
                continue
            if candidate.upper() in _NOISE_TOKENS:
                continue
            # Must contain at least one digit to be a model number
            if not re.search(r'\d', candidate):
                continue
            return candidate

        return None

    def extract_isbn(self, specs: dict) -> Optional[str]:
        """
        Extract ISBN from specs dict. For books only.
        Strips hyphens and spaces before returning.
        Returns None when not found.
        """
        if not specs:
            return None

        for key in _ISBN_KEYS:
            value = specs.get(key)
            if value and isinstance(value, str):
                clean = value.replace("-", "").replace(" ", "").strip()
                # Basic ISBN validation: 10 or 13 digits
                if re.match(r'^\d{10}$|^\d{13}$', clean):
                    return clean

        return None

    # ── Private helpers ───────────────────────────────────────────────────────

    def _normalize_brand(self, brand: Optional[str]) -> Optional[str]:
        """
        Normalize brand to title case.
        Handles all-caps brands (SAMSUNG → Samsung, BOAT → boAt special cases).
        """
        if not brand:
            return None

        # Known brands with non-standard casing
        _BRAND_OVERRIDES = {
            "BOAT": "boAt",
            "IQOO": "iQOO",
            "ONEPLUS": "OnePlus",
            "REALME": "realme",
        }

        upper = brand.strip().upper()
        if upper in _BRAND_OVERRIDES:
            return _BRAND_OVERRIDES[upper]

        # Title case for all-caps brands, preserve mixed-case brands
        if brand.strip().isupper():
            return brand.strip().title()

        return brand.strip()


# ── Module-level singleton ────────────────────────────────────────────────────
product_identity_service = ProductIdentityService()
