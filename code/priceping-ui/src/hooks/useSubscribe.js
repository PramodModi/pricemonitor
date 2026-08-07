import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import api from '@/lib/api'
import { useAppStore } from '@/store/useAppStore'

/**
 * Confirm a subscription after preview.
 * POST /v1/subscriptions  { preview_id, email }
 *
 * On success: updates userEmail in store, advances to "success" step,
 *             invalidates items cache.
 */
export function useSubscribe() {
  const queryClient = useQueryClient()
  const { setTrackStep, setUserEmail, previewResult } = useAppStore()

  return useMutation({
    mutationFn: async ({ email }) => {
      const { data } = await api.post('/v1/subscriptions', {
        preview_id: previewResult?.preview_id,
        email,
      })
      return data
    },
    onSuccess: (data, variables) => {
      setUserEmail(variables.email)
      setTrackStep('success')
      queryClient.invalidateQueries({ queryKey: ['items', variables.email] })
    },
    onError: (error) => {
      if (error.code === 'PREVIEW_NOT_FOUND') {
        // Preview expired — reset to input step so user can re-search
        useAppStore.getState().resetTrack()
        toast.error('Your preview expired. Please search for the product again.')
      }
    },
  })
}
