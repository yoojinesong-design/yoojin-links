'use client'
import { useState } from 'react'

const MESSAGES = {
  en: { failed: 'Something went wrong — please try again', network: 'Network error — please try again' },
  ko: { failed: '오류가 발생했어요. 다시 시도해 주세요', network: '네트워크 오류 — 다시 시도해 주세요' },
}

/**
 * Shared waitlist form logic used across all landing pages.
 * @param {'detailbook' | 'gage-doumi' | 'persona-hub' | 'simple-order'} product
 * @param {'en' | 'ko'} lang — language for error messages
 */
export function useWaitlist(product, lang = 'en') {
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
      if (res.ok) setSubmitted(true)
      else setError(MESSAGES[lang].failed)
    } catch {
      setError(MESSAGES[lang].network)
    } finally {
      setSubmitting(false)
    }
  }

  return { email, setEmail, submitted, submitting, error, handleSubmit }
}
