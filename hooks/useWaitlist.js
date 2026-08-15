'use client'
import { useState } from 'react'

/**
 * Shared waitlist form logic used across all landing pages.
 * @param {string} product — 'detailbook' | 'gage-doumi' | 'persona-hub' | 'simple-order'
 */
export function useWaitlist(product) {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!email || submitting) return
    setSubmitting(true)
    setError('')
    try {
      const res = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, product }),
      })
      const data = await res.json()
      if (!res.ok && res.status !== 200) throw new Error(data.error || 'Something went wrong')
      setSubmitted(true)
    } catch (err) {
      setError(err.message || 'Network error — please try again')
    } finally {
      setSubmitting(false)
    }
  }

  return { email, setEmail, submitted, submitting, error, handleSubmit }
}
