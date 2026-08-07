import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

/**
 * Fetches all products tracked by the given email address.
 * GET /v1/items?email=
 *
 * Response shape (from API spec v3.0):
 * {
 *   email: string,
 *   count: number,
 *   items: [
 *     {
 *       subscription_id: UUID,
 *       subscribed_at: ISO string,
 *       product: {
 *         product_id: UUID,
 *         marketplace_product_id: string,
 *         url: string,
 *         platform: "amazon" | "flipkart" | "myntra",
 *         name: string,
 *         brand: string | null,
 *         image_url: string | null,
 *         current_price: number,
 *         currency: "INR",
 *         availability: boolean,
 *         rating: number | null,
 *         review_count: number | null,
 *         seller: string | null,
 *         last_checked_at: ISO string,
 *         mrp: number | null,           // v3.0 — affiliate enrichment
 *         special_price: number | null, // v3.0 — offer price
 *         discount_pct: number | null,  // v3.0
 *         offers: array | null,         // v3.0 — bank offers
 *       }
 *     }
 *   ]
 * }
 */
export function useItems(email) {
  return useQuery({
    queryKey: ['items', email],
    queryFn: async () => {
      const { data } = await api.get('/v1/items', { params: { email } })
      return data
    },
    enabled: !!email,        // only fires when email is non-empty
    staleTime: 30_000,       // treat data as fresh for 30s
    retry: 1,
  })
}
