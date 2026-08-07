import { useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'

/**
 * Removes a subscription.
 * DELETE /v1/subscriptions/{subscription_id}?email=
 *
 * mutate({ subscriptionId, email })
 */
export function useDeleteSubscription() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ subscriptionId, email }) => {
      const { data } = await api.delete(
        `/v1/subscriptions/${subscriptionId}`,
        { params: { email } }
      )
      return data
    },
    onSuccess: (_data, { email }) => {
      // Invalidate the items cache so the list refreshes without a page reload
      queryClient.invalidateQueries({ queryKey: ['items', email] })
    },
  })
}
