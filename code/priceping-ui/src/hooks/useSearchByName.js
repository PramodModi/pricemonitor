'use client'

import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'

/**
 * useSearchByName — calls POST /v1/products/search-by-name
 *
 * Used by ScrapeFailureCard when the user types a product name
 * and selects a platform after a scrape failure.
 *
 * Returns ProductCandidate list with url, name, image_url, platform.
 */
export function useSearchByName() {
  return useMutation({
    mutationFn: async ({ name, platform, limit = 5 }) => {
      const { data } = await api.post('/v1/products/search-by-name', {
        name,
        platform,
        limit,
      })
      return data
    },
  })
}
