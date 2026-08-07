'use client'

import { toast } from 'sonner'
import { useAppStore } from '@/store/useAppStore'
import { useDeleteSubscription } from '@/hooks/useDeleteSubscription'

/**
 * DeleteDialog
 * Reads deleteTarget from global Zustand store.
 * Renders only when deleteTarget is non-null.
 * Uses a simple modal (no shadcn dependency needed for this simple case).
 */
export default function DeleteDialog() {
  const { deleteTarget, setDeleteTarget, userEmail } = useAppStore()
  const { mutate, isPending } = useDeleteSubscription()

  if (!deleteTarget) return null

  const { subscriptionId, productName } = deleteTarget

  function handleCancel() {
    setDeleteTarget(null)
  }

  function handleConfirm() {
    mutate(
      { subscriptionId, email: userEmail },
      {
        onSuccess: () => {
          toast.success(`"${productName}" removed from your list.`)
          setDeleteTarget(null)
        },
        onError: (error) => {
          toast.error(error.message ?? 'Failed to remove item. Please try again.')
          setDeleteTarget(null)
        },
      }
    )
  }

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={handleCancel}
    >
      {/* Dialog panel */}
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-slate-800 mb-2">
          Remove product?
        </h2>
        <p className="text-sm text-slate-600 mb-6">
          Remove{' '}
          <span className="font-medium text-slate-800">
            &ldquo;{productName}&rdquo;
          </span>{' '}
          from your monitoring list? You can always add it again.
        </p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={handleCancel}
            disabled={isPending}
            className="btn-ghost"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={isPending}
            className="px-4 py-2 rounded-lg bg-red-500 hover:bg-red-600 text-white text-sm font-medium transition-colors disabled:opacity-60"
          >
            {isPending ? 'Removing…' : 'Yes, Remove'}
          </button>
        </div>
      </div>
    </div>
  )
}
