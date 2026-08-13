/**
 * searchUtils.js — shared search utility functions for the frontend.
 *
 * File: src/lib/searchUtils.js
 *
 * Backend equivalent: app/utils/search_scorer.py → query_title_similarity()
 * Keep both in sync when updating the algorithm.
 */

const _STOPWORDS = new Set([
  'the', 'and', 'for', 'with', 'from', 'this', 'that',
  'buy', 'a', 'an', 'in', 'of', 'to', 'is', 'are', 'at',
  'by', 'on', 'it', 'be', 'as', 'or', 'get',
])

/**
 * Tokenize a string into meaningful lowercase tokens.
 * Splits on whitespace and common punctuation, strips stopwords and short tokens.
 *
 * @param {string} text
 * @returns {Set<string>}
 */
function _tokenize(text) {
  return new Set(
    text
      .toLowerCase()
      .split(/[\s,()[\]|&]+/)
      .filter((t) => t.length >= 2 && !_STOPWORDS.has(t))
  )
}

/**
 * Token overlap similarity between a search query and a result title.
 * Returns 0.0–1.0.
 *
 * Used to validate search results — if top result similarity is below
 * a threshold (e.g. 0.6), the results are likely wrong category/product
 * and the frontend should fall back to live store search.
 *
 * Strips common portal prefixes like "Buy " before scoring.
 * Ignores stopwords and short tokens (< 2 chars).
 *
 * Backend equivalent: app/utils/search_scorer.query_title_similarity()
 *
 * @param {string} query  - Raw user search query
 * @param {string} title  - Result title from DB or Tavily
 * @returns {number}      - Similarity score 0.0–1.0
 *
 * @example
 * queryTitleSimilarity('Boat Wanderer Smart Kids Watch', 'Buy boAt Wanderer Smart Kids Watch GPS')
 * // → 0.6
 *
 * queryTitleSimilarity('Samsung TV', 'boAt Speaker 200')
 * // → 0.0
 */
export function queryTitleSimilarity(query, title) {
  if (!query || !title) return 0

  // Strip common portal prefixes
  const cleanTitle = title.toLowerCase().replace(/^buy\s+/i, '').trim()

  const qTokens = _tokenize(query)
  const tTokens = _tokenize(cleanTitle)

  if (!qTokens.size || !tTokens.size) return 0

  const intersection = [...qTokens].filter((t) => tTokens.has(t))
  return intersection.length / Math.max(qTokens.size, tTokens.size)
}
