import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'
import { useAppStore } from '@/store/useAppStore'

/**
 * Log in with email + password.
 * POST /v1/auth/login  { email, password }
 * Response: { token: string, email: string }
 *
 * On success: stores JWT and email in Zustand (+ localStorage via persist).
 */
export function useLogin() {
  const { setAuthToken, setUserEmail } = useAppStore()

  return useMutation({
    mutationFn: async ({ email, password }) => {
      const { data } = await api.post('/v1/auth/login', { email, password })
      return data
    },
    onSuccess: (data) => {
      setAuthToken(data.token)
      setUserEmail(data.email)
    },
  })
}
