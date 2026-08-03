'use client'
import { useState } from 'react'
import { getSupabase } from '../../../lib/supabase-browser'
import Link from 'next/link'

export default function AuthPage() {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)

    const supabase = getSupabase()

    if (mode === 'login') {
      const { error: err } = await supabase.auth.signInWithPassword({ email, password })
      if (err) {
        setError(err.message)
      } else {
        window.location.href = '/persona-hub/dashboard'
      }
    } else {
      const { error: err } = await supabase.auth.signUp({ email, password })
      if (err) {
        setError(err.message)
      } else {
        setMessage('Check your email for a confirmation link.')
      }
    }

    setLoading(false)
  }

  const handleOAuth = async (provider) => {
    const supabase = getSupabase()
    await supabase.auth.signInWithOAuth({
      provider,
      options: { redirectTo: `${window.location.origin}/persona-hub/dashboard` },
    })
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex items-center justify-center px-5">
      <div className="w-full max-w-sm">
        <Link href="/persona-hub" className="block text-center mb-8">
          <span className="text-2xl font-bold tracking-tight">Persona<span className="text-violet-400">Hub</span></span>
        </Link>

        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6">
          <div className="flex mb-6 bg-neutral-800 rounded-lg p-1">
            <button
              onClick={() => setMode('login')}
              className={`flex-1 text-sm py-2 rounded-md font-medium transition ${mode === 'login' ? 'bg-violet-500 text-white' : 'text-neutral-400 hover:text-neutral-200'}`}
            >
              Log In
            </button>
            <button
              onClick={() => setMode('signup')}
              className={`flex-1 text-sm py-2 rounded-md font-medium transition ${mode === 'signup' ? 'bg-violet-500 text-white' : 'text-neutral-400 hover:text-neutral-200'}`}
            >
              Sign Up
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2.5 text-sm text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-violet-500 transition"
                placeholder="your@email.com"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Password</label>
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2.5 text-sm text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-violet-500 transition"
                placeholder="Min 6 characters"
              />
            </div>

            {error && <p className="text-red-400 text-sm">{error}</p>}
            {message && <p className="text-green-400 text-sm">{message}</p>}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-violet-500 hover:bg-violet-400 disabled:opacity-50 text-white py-2.5 rounded-lg font-semibold text-sm transition"
            >
              {loading ? '...' : mode === 'login' ? 'Log In' : 'Create Account'}
            </button>
          </form>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-neutral-800" /></div>
            <div className="relative flex justify-center"><span className="bg-neutral-900 px-3 text-xs text-neutral-500">or</span></div>
          </div>

          <div className="space-y-2">
            <button
              onClick={() => handleOAuth('google')}
              className="w-full flex items-center justify-center gap-2 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 text-neutral-200 py-2.5 rounded-lg text-sm transition"
            >
              <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
              Continue with Google
            </button>
          </div>
        </div>

        <p className="text-center text-xs text-neutral-600 mt-6">
          <Link href="/persona-hub" className="hover:text-neutral-400 transition">Back to PersonaHub</Link>
        </p>
      </div>
    </div>
  )
}
