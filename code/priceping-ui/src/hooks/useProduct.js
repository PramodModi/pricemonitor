import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

/**
 * Fetches full product detail including price_stats.
 * GET /v1/products/{productId}
 *
 * Response shape (API spec v3.0 + v3.1 metadata):
 * {
 *   product_id, marketplace_product_id, url, platform,
 *   name, brand, image_url, current_price, currency, availability,
 *   rating, review_count, seller, last_checked_at, created_at,
 *   watcher_count,
 *   mrp, special_price, discount_pct, offers,     ← v3.0
 *   product_metadata: {                             ← v3.1
 *     description, images, category, subcategory,
 *     specs, features, sizes_available, material, fit, style_notes
 *   },
 *   price_stats: {
 *     all_time_low, all_time_high, drop_count, first_tracked_at
 *   }
 * }
 */
export function useProduct(productId) {
  return useQuery({
    queryKey: ['product', productId],
    queryFn: async () => {
      const { data } = await api.get(`/v1/products/${productId}`)
      return data
    },
    enabled: !!productId,
    staleTime: 60_000,   // treat fresh for 1 minute
    retry: 1,
  })
}
