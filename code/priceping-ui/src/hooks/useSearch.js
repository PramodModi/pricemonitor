'use client'

import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'

/**
 * useSearch — calls GET /v1/search?q=<query>&limit=20
 *
 * Used by TrackPageClient when the user types a product name instead of a URL.
 * Returns canonical products with all portal listings attached.
 *
 * Implemented as a mutation (not a query) because it's triggered by user action
 * (form submit), not by component mount. Same pattern as usePreview.
 *
 * Response shape:
 *   { query, count, results: [{ canonical_id, name, brand, category, image_url,
 *     model_number, best_price, best_platform, listings: [...] }] }
 */
export function useSearch() {
  return useMutation({
    mutationFn: async (query) => {
      const { data } = await api.get('/v1/search', {
        params: { q: query, limit: 20 },
      })
      return data
    },
  })
}
