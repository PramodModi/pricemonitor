import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'
import { useAppStore } from '@/store/useAppStore'

/**
 * Preview a product URL before subscribing.
 * POST /v1/products/preview  { url }
 *
 * On success: stores result in Zustand previewResult and advances trackStep.
 * The mutation takes the URL string as its argument.
 */
export function usePreview() {
  const { setPreviewResult, setTrackStep } = useAppStore()

  return useMutation({
    mutationFn: async (url) => {
      const { data } = await api.post('/v1/products/preview', { url })
      return data
    },
    onSuccess: (data) => {
      setPreviewResult(data)
      setTrackStep('preview')
    },
    onError: () => {
      setTrackStep('input')
    },
  })
}
