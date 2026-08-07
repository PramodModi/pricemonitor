import axios from 'axios'
import { getErrorMessage } from './errors'

/**
 * Configured Axios instance.
 *
 * Base URL: NEXT_PUBLIC_API_URL (env var)
 *   - Local dev:   http://localhost:8001
 *   - Production:  https://api.priceping.in
 *
 * Timeout: 35 000ms — the preview endpoint triggers a live Playwright scrape
 * (10–20s). All other endpoints respond in under 2s. One timeout for simplicity.
 *
 * Auth interceptor: attaches JWT from Zustand store as Bearer token when present.
 * Error interceptor: maps API error codes → user-facing messages.
 */
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  timeout: 35_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ─── Request interceptor — attach JWT ─────────────────────────────
api.interceptors.request.use((config) => {
  // Dynamically import store to avoid circular dep / SSR issues.
  // useAppStore.getState() is safe to call outside React components.
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { useAppStore } = require('@/store/useAppStore')
    const token = useAppStore.getState().authToken
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
  } catch {
    // Store not available (SSR context) — no token attached
  }
  return config
})

// ─── Response interceptor — normalise errors ──────────────────────
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.code === 'ECONNABORTED') {
      return Promise.reject({
        code: 'TIMEOUT',
        message: getErrorMessage('TIMEOUT'),
      })
    }

    if (!error.response) {
      return Promise.reject({
        code: 'CONNECTION_ERROR',
        message: getErrorMessage('CONNECTION_ERROR'),
      })
    }

    const { status, data } = error.response
    const code = data?.error?.code ?? inferCodeFromStatus(status)
    const message = data?.error?.message ?? getErrorMessage(code)

    return Promise.reject({ code, message, status })
  }
)

function inferCodeFromStatus(status) {
  if (status === 401) return 'UNAUTHORIZED'
  if (status === 404) return 'PRODUCT_NOT_FOUND'
  if (status === 422) return 'VALIDATION_ERROR'
  if (status === 502) return 'SCRAPE_FAILED'
  if (status === 503) return 'SERVICE_UNAVAILABLE'
  return 'INTERNAL_ERROR'
}

export default api
