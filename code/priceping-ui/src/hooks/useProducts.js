import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

/**
 * Fetch products from the catalogue, paginating backend automatically.
 * Full list cached for 5 minutes — platform/category filtering is server-side.
 *
 * Backend caps at limit=100 per request — we loop with offset until exhausted.
 *
 * @param {string[]} platforms   - selected platforms (empty = all)
 * @param {string[]} categories  - selected categories (empty = all)
 * @param {boolean}  onlyDropped - when true, sends has_drop=true to backend
 *                                 (only products where current_price < all_time_high)
 */
const PAGE_SIZE = 100

export function useProducts(platforms = [], categories = [], onlyDropped = false) {
  // When multiple platforms/categories selected, make parallel calls per combo
  const platformList = platforms.length > 0 ? platforms : [null]
  const categoryList = categories.length > 0 ? categories : [null]
  const pairs = platformList.flatMap(p => categoryList.map(c => ({ platform: p, category: c })))

  return useQuery({
    queryKey: ['products', platforms, categories, onlyDropped],
    queryFn: async () => {
      // Fetch all pages for each (platform, category) pair in parallel
      const allPairItems = await Promise.all(
        pairs.map(async ({ platform, category }) => {
          const items = []
          let offset = 0
          while (true) {
            const params = { limit: PAGE_SIZE, offset }
            if (platform)    params.platform  = platform
            if (category)    params.category  = category
            if (onlyDropped) params.has_drop  = true
            const res = await api.get('/v1/products', { params })
            const batch = res.data.items ?? []
            items.push(...batch)
            if (batch.length < PAGE_SIZE) break
            offset += PAGE_SIZE
          }
          return items
        })
      )

      // Merge and deduplicate across pairs
      const seen  = new Set()
      const items = []
      for (const pairItems of allPairItems) {
        for (const item of pairItems) {
          if (!seen.has(item.product_id)) {
            seen.add(item.product_id)
            items.push(item)
          }
        }
      }

      // Re-sort by watcher_count desc after merge
      items.sort((a, b) => (b.watcher_count ?? 0) - (a.watcher_count ?? 0))

      return { total: items.length, items }
    },
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Fetch the full unfiltered catalogue count — used for subtitle
 * ("X deals out of Y tracked products").
 */
export function useAllProductsCount() {
  return useQuery({
    queryKey: ['products', 'count'],
    queryFn: async () => {
      const res = await api.get('/v1/products', { params: { limit: 1, offset: 0 } })
      return res.data.total ?? 0
    },
    staleTime: 5 * 60 * 1000,
  })
}
