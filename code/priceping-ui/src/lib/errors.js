/**
 * Maps API error codes to user-facing messages.
 * Mirrors API Specification v3.0 error codes.
 * All messages are written from the user's side — no technical jargon.
 */
export const ERROR_MESSAGES = {
  INVALID_URL:
    "That URL doesn't look like a product page. Use a direct product URL from Amazon, Flipkart, or Myntra.",
  UNSUPPORTED_PLATFORM:
    'Only Amazon India, Flipkart, and Myntra are supported right now.',
  INVALID_EMAIL:
    'Please enter a valid email address.',
  SCRAPE_FAILED:
    "Couldn't fetch product details. Please check the URL and try again.",
  SCRAPE_BLOCKED:
    'The marketplace blocked our request. Try again in a few minutes.',
  PREVIEW_NOT_FOUND:
    'Your preview expired. Please search for the product again.',
  SUBSCRIPTION_NOT_FOUND:
    'That tracking item was not found.',
  PRODUCT_NOT_FOUND:
    'Product not found.',
  RUN_NOT_FOUND:
    'Scheduler run not found.',
  UNAUTHORIZED:
    'Session expired. Please log in again.',
  VALIDATION_ERROR:
    'Something looks wrong with the form. Please check your input.',
  INTERNAL_ERROR:
    'Something went wrong on our end. Please try again shortly.',
  SERVICE_UNAVAILABLE:
    'PricePing is temporarily unavailable. Please try again in a moment.',
  CONNECTION_ERROR:
    'Cannot reach the server. Check your connection.',
  TIMEOUT:
    'The request timed out — the scraper is taking longer than usual. Please try again.',
}

/**
 * Returns a user-facing message for a given error code.
 * Falls back to a generic message for unknown codes.
 */
export function getErrorMessage(code) {
  return ERROR_MESSAGES[code] ?? 'Something went wrong. Please try again.'
}
