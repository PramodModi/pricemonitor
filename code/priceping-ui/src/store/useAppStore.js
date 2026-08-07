import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/**
 * Global client state for PricePing.
 *
 * Persisted to localStorage: userEmail, authToken
 * Session-only (resets on page reload): trackStep, previewResult, deleteTarget
 */
export const useAppStore = create(
  persist(
    (set) => ({
      // ─── Persisted ───────────────────────────────────────────────────────
      userEmail: null,
      authToken: null,

      setUserEmail: (email) => set({ userEmail: email }),
      setAuthToken: (token) => set({ authToken: token }),
      clearAuth: () => set({ userEmail: null, authToken: null }),

      // ─── Session-only ────────────────────────────────────────────────────
      // Track page state machine
      trackStep: 'input',          // "input" | "loading" | "preview" | "confirming" | "success"
      previewResult: null,         // full POST /v1/products/preview response

      setTrackStep: (step) => set({ trackStep: step }),
      setPreviewResult: (result) => set({ previewResult: result }),
      resetTrack: () => set({ trackStep: 'input', previewResult: null }),

      // Delete confirmation dialog
      deleteTarget: null,          // { subscriptionId, productName } | null

      setDeleteTarget: (target) => set({ deleteTarget: target }),
    }),
    {
      name: 'priceping-store',
      // Only persist these two keys — everything else resets on page reload
      partialize: (state) => ({
        userEmail: state.userEmail,
        authToken: state.authToken,
      }),
    }
  )
)
