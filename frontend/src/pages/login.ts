// Alpine.js login page — cookie-based auth, no localStorage.
// Mounted by the SSR template at login.html via<script src="/dist/assets/login.js">
import { loginApi } from '../api/apiClient'

/**
 * Attempt to log in with the given API key.
 * @returns error message string on failure, or throws on network failure.
 */
export async function login(apiKey: string): Promise<string | never> {
  try {
    const response = await loginApi.login(apiKey)
    if (response.success) {
      // Redirect to dashboard on success
      window.location.href = '/dashboard'
      return ''
    }
    return 'Login failed'
  } catch (err) {
    const error = err as Error
    if (error.message.includes('Too many requests')) {
      return 'Too many requests — please wait before trying again'
    }
    if (error.message.includes('401') || error.message.includes('Unauthorized')) {
      return 'Invalid API key — authentication failed'
    }
    if (error.message.includes('Network failure') || error.message.includes('fetch')) {
      return 'Connection error — could not reach the server'
    }
    return error.message || 'Login failed'
  }
}

/**
 * Clear any error state (called on input change).
 */
export function clearError(): void {
  // Alpine data layer handles this via x-model
}

// Expose globally for Alpine.js inline templates
declare global {
  interface Window {
    login: typeof login
    clearError: typeof clearError
  }
}

if (typeof window !== 'undefined') {
  window.login = login
  window.clearError = clearError
}
