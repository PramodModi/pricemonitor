import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

/**
 * Check if a user has set a password.
 * GET /v1/auth/check?email={email}
 *
 * Response: { requires_password: boolean, user_exists: boolean }
 * Only runs when email is provided.
 */
export function useAuthCheck(email) {
  return useQuery({
    queryKey: ['auth-check', email],
    queryFn: async () => {
      const { data } = await api.get('/v1/auth/check', { params: { email } })
      return data
    },
    enabled:   Boolean(email),
    staleTime: 60 * 1000,   // 1 minute
    retry:     1,
  })
}
