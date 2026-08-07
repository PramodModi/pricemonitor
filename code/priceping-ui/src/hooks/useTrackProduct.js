import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import api from '@/lib/api'
import { useAppStore } from '@/store/useAppStore'

/**
 * Track a product directly from its product page (no scrape needed — product exists).
 * POST /v1/products/{productId}/track  { email }
 *
 * On success: invalidates items cache, shows toast.
 */
export function useTrackProduct(productId) {
  const queryClient = useQueryClient()
  const { userEmail, setUserEmail } = useAppStore()

  return useMutation({
    mutationFn: async ({ email }) => {
      const { data } = await api.post(`/v1/products/${productId}/track`, { email })
      return data
    },
    onSuccess: (data, variables) => {
      setUserEmail(variables.email)
      queryClient.invalidateQueries({ queryKey: ['items', variables.email] })
      toast.success("You're now tracking this product.")
    },
    onError: (error) => {
      toast.error(error.message ?? 'Could not start tracking. Please try again.')
    },
  })
}
