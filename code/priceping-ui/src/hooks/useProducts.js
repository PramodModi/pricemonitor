import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

/**
 * Fetch all products from the catalogue, ordered by watcher count descending.
 * Used by the /offers page.
 *
 * @param {string|null} platform - 'amazon' | 'flipkart' | 'myntra' | null (all)
 * @returns TanStack Query result — { data, isLoading, isError, refetch }
 *   data shape: { total, count, platform, items: ProductListItem[] }
 */
export function useProducts(platform = null) {
  return useQuery({
    queryKey: ['products', platform],
    queryFn: async () => {
      const params = { limit: 50, offset: 0 }
      if (platform) params.platform = platform
      const res = await api.get('/v1/products', { params })
      return res.data
    },
    staleTime: 5 * 60 * 1000, // 5 minutes — prices change at cron cadence
  })
}
