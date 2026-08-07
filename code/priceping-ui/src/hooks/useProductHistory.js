import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

/**
 * Fetches price history for a product.
 * GET /v1/products/{productId}/history?period=3m
 *
 * period: "1m" | "3m" | "6m" | "all"
 *
 * NOTE (DEF-003): This endpoint does not exist on the backend yet.
 * The hook returns { data: [], isLoading: false, isError: false }
 * gracefully when the API returns 404, so the chart shows an empty
 * state without breaking the page.
 *
 * Expected response: [{ price: number, checked_at: ISO string }, ...]
 */
export function useProductHistory(productId, period = '3m') {
  return useQuery({
    queryKey: ['product-history', productId, period],
    queryFn: async () => {
      try {
        const { data } = await api.get(`/v1/products/${productId}/history`, {
          params: { period },
        })
        // Normalise: API may return array directly or { history: [...] }
        return Array.isArray(data) ? data : (data.history ?? [])
      } catch (err) {
        // 404 = endpoint not yet implemented — return empty array gracefully
        if (err?.response?.status === 404 || err?.code === 'PRODUCT_NOT_FOUND') {
          return []
        }
        throw err
      }
    },
    enabled: !!productId,
    staleTime: 5 * 60_000,   // 5 minutes
    retry: 0,                 // don't retry a 404
  })
}
