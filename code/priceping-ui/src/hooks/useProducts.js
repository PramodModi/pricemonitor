import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

/**
 * Fetch products from the catalogue, ordered by watcher count descending.
 * Used by the /offers page.
 *
 * @param {string[]} platforms  - selected platforms e.g. ['amazon','flipkart'] (empty = all)
 * @param {string[]} categories - selected categories e.g. ['mobiles'] (empty = all)
 *
 * When multiple platforms or categories are selected, we make parallel API
 * calls (one per combination) and merge the results client-side.
 * The backend supports one platform + one category per request.
 *
 * @returns TanStack Query result — { data, isLoading, isError, refetch }
 *   data shape: { total, count, platform, items: ProductListItem[] }
 */
export function useProducts(platforms = [], categories = []) {
  // Build the list of (platform, category) pairs to fetch.
  // Empty arrays mean "no filter" → one call with null values.
  const platformList = platforms.length > 0 ? platforms : [null]
  const categoryList = categories.length > 0 ? categories : [null]

  // Cartesian product — e.g. [amazon, flipkart] × [mobiles] → 2 calls
  const pairs = platformList.flatMap(p =>
    categoryList.map(c => ({ platform: p, category: c }))
  )

  return useQuery({
    queryKey: ['products', platforms, categories],
    queryFn: async () => {
      const results = await Promise.all(
        pairs.map(async ({ platform, category }) => {
          const params = { limit: 50, offset: 0 }
          if (platform) params.platform = platform
          if (category) params.category = category
          const res = await api.get('/v1/products', { params })
          return res.data
        })
      )

      // Single call — return as-is
      if (results.length === 1) return results[0]

      // Multiple calls — merge and deduplicate by product_id
      const seen = new Set()
      const items = []
      for (const result of results) {
        for (const item of result.items ?? []) {
          if (!seen.has(item.product_id)) {
            seen.add(item.product_id)
            items.push(item)
          }
        }
      }

      // Re-sort by watcher_count desc (each batch was sorted, merge needs resort)
      items.sort((a, b) => (b.watcher_count ?? 0) - (a.watcher_count ?? 0))

      return {
        total: items.length,
        count: items.length,
        platform: platforms.length === 1 ? platforms[0] : null,
        items,
      }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}
