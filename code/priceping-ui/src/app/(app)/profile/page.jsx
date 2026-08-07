'use client'

import { useState } from 'react'
import { User, Bell, AlertTriangle, Eye, EyeOff, Loader2 } from 'lucide-react'
import { useAppStore } from '@/store/useAppStore'
import api from '@/lib/api'
import { toast } from 'sonner'

/**
 * Profile page — personal settings.
 * Phase: 1 | Rendering: Client Component
 *
 * Sections:
 *   1. Account — email, password (set or change)
 *   2. Notification preferences — master pause toggle (placeholder for full prefs)
 *   3. Danger zone — delete account
 */
export default function ProfilePage() {
  const userEmail  = useAppStore((state) => state.userEmail)
  const authToken  = useAppStore((state) => state.authToken)
  const clearAuth  = useAppStore((state) => state.clearAuth)

  if (!userEmail) {
    return (
      <div className="mx-auto max-w-lg pt-10 text-center">
        <p className="text-slate-500">Please go to the Dashboard and enter your email first.</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      {/* Section 1: Account */}
      <AccountSection
        email={userEmail}
        hasPassword={Boolean(authToken)}
      />

      {/* Section 2: Notification preferences (Phase 1 placeholder) */}
      <NotificationSection />

      {/* Section 3: Danger zone */}
      <DangerZoneSection
        email={userEmail}
        onDeleted={clearAuth}
      />
    </div>
  )
}

// ─── Account section ──────────────────────────────────────────────

function AccountSection({ email, hasPassword }) {
  const [mode, setMode]           = useState('idle')  // 'idle' | 'set-password' | 'change-password'
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [showNew, setShowNew]     = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError]         = useState('')

  const handleSetPassword = async (e) => {
    e.preventDefault()
    if (newPassword.length < 8) { setError('Password must be at least 8 characters.'); return }
    if (newPassword !== confirmPassword) { setError('Passwords do not match.'); return }
    setError('')
    setIsSubmitting(true)
    try {
      // Phase 1: trigger OTP send then set password
      await api.post('/v1/auth/set-password', {
        email,
        new_password: newPassword,
      })
      toast.success('Password set successfully. Your dashboard is now protected.')
      setMode('idle')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setError(err.message ?? 'Could not set password. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="card p-6 space-y-5">
      <div className="flex items-center gap-2">
        <User size={18} className="text-slate-400" />
        <h2 className="font-display text-base font-semibold text-slate-900">Account</h2>
      </div>

      {/* Email */}
      <div>
        <p className="text-xs font-medium text-slate-500 mb-1">Email address</p>
        <div className="flex items-center justify-between rounded-lg border border-slate-200
                        bg-slate-50 px-4 py-2.5">
          <span className="text-sm font-medium text-slate-700">{email}</span>
          <span className="text-xs text-slate-400">Read-only</span>
        </div>
      </div>

      {/* Password */}
      <div>
        <p className="text-xs font-medium text-slate-500 mb-1.5">Password</p>
        {!hasPassword && mode === 'idle' && (
          <div className="flex items-center justify-between rounded-lg border border-amber-100
                          bg-amber-50 px-4 py-3">
            <p className="text-sm text-amber-700">
              No password set — anyone with your email can view your dashboard.
            </p>
            <button
              onClick={() => setMode('set-password')}
              className="ml-3 shrink-0 text-sm font-medium text-primary-600 hover:text-primary-800"
            >
              Set password
            </button>
          </div>
        )}

        {hasPassword && mode === 'idle' && (
          <div className="flex items-center justify-between rounded-lg border border-green-100
                          bg-green-50 px-4 py-2.5">
            <p className="text-sm text-green-700">Dashboard is password-protected.</p>
            <button
              onClick={() => setMode('change-password')}
              className="ml-3 shrink-0 text-sm font-medium text-primary-600 hover:text-primary-800"
            >
              Change
            </button>
          </div>
        )}

        {(mode === 'set-password' || mode === 'change-password') && (
          <form onSubmit={handleSetPassword} className="space-y-3">
            {mode === 'change-password' && (
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Current password"
                className="input"
                disabled={isSubmitting}
              />
            )}
            <div className="relative">
              <input
                type={showNew ? 'text' : 'password'}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="New password (min 8 characters)"
                className="input pr-10"
                disabled={isSubmitting}
              />
              <button
                type="button"
                onClick={() => setShowNew(!showNew)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700"
              >
                {showNew ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm new password"
              className="input"
              disabled={isSubmitting}
            />
            {error && <p className="text-xs text-red-600">{error}</p>}
            <div className="flex gap-3">
              <button type="button" onClick={() => setMode('idle')} className="btn-ghost">
                Cancel
              </button>
              <button type="submit" disabled={isSubmitting} className="btn-primary flex-1 justify-center">
                {isSubmitting ? <><Loader2 size={15} className="animate-spin" /> Saving…</> : 'Save password'}
              </button>
            </div>
          </form>
        )}
      </div>
    </section>
  )
}

// ─── Notification preferences section ────────────────────────────

function NotificationSection() {
  return (
    <section className="card p-6 space-y-4">
      <div className="flex items-center gap-2">
        <Bell size={18} className="text-slate-400" />
        <h2 className="font-display text-base font-semibold text-slate-900">
          Notification preferences
        </h2>
      </div>
      <div className="rounded-xl border border-slate-100 bg-slate-50 px-4 py-4 text-sm text-slate-500">
        <p className="font-medium text-slate-600">Per-item notification settings are coming soon.</p>
        <p className="mt-1">
          You'll be able to pause alerts, set price thresholds, and control how you're notified
          for each tracked product.
        </p>
      </div>
    </section>
  )
}

// ─── Danger zone section ──────────────────────────────────────────

function DangerZoneSection({ email, onDeleted }) {
  const [confirming, setConfirming] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  const handleDelete = async () => {
    setIsDeleting(true)
    try {
      await api.delete('/v1/users/me', { params: { email } })
      toast.success('Account deleted. All your tracking data has been removed.')
      onDeleted()
    } catch (err) {
      toast.error(err.message ?? 'Could not delete account. Please try again.')
    } finally {
      setIsDeleting(false)
      setConfirming(false)
    }
  }

  return (
    <section className="card border-red-100 p-6 space-y-4">
      <div className="flex items-center gap-2">
        <AlertTriangle size={18} className="text-red-400" />
        <h2 className="font-display text-base font-semibold text-red-700">Danger zone</h2>
      </div>

      <p className="text-sm text-slate-500">
        Deleting your account removes all your subscriptions. Products remain in the
        PricePing catalog for other users.
      </p>

      {!confirming ? (
        <button
          onClick={() => setConfirming(true)}
          className="text-sm font-medium text-red-600 hover:text-red-800 transition-colors"
        >
          Delete my account
        </button>
      ) : (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 space-y-3">
          <p className="text-sm font-medium text-red-700">
            Are you sure? This cannot be undone.
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => setConfirming(false)}
              disabled={isDeleting}
              className="btn-ghost"
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              disabled={isDeleting}
              className="inline-flex items-center justify-center gap-2 rounded-xl
                         bg-red-600 px-4 py-2 text-sm font-semibold text-white
                         hover:bg-red-700 disabled:opacity-50 transition-colors"
            >
              {isDeleting ? <><Loader2 size={14} className="animate-spin" /> Deleting…</> : 'Yes, delete'}
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
