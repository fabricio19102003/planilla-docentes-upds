import axios from 'axios'

export const AUTH_RETURN_URL_KEY = 'auth_return_url'
export const AUTH_LOGOUT_REASON_KEY = 'auth_logout_reason'

let isHandlingUnauthorized = false

export function getSafeLocalPath(value: string | null): string | null {
  if (!value || !value.startsWith('/') || value.startsWith('//')) return null

  try {
    const url = new URL(value, window.location.origin)
    if (url.origin !== window.location.origin) return null
    return `${url.pathname}${url.search}${url.hash}`
  } catch {
    return null
  }
}

export function consumePostLoginReturnUrl(role: 'admin' | 'docente'): string | null {
  const returnUrl = getSafeLocalPath(sessionStorage.getItem(AUTH_RETURN_URL_KEY))
  sessionStorage.removeItem(AUTH_RETURN_URL_KEY)
  if (!returnUrl) return null

  const pathname = new URL(returnUrl, window.location.origin).pathname
  if (role === 'docente') {
    return pathname === '/portal' || pathname.startsWith('/portal/') ? returnUrl : null
  }

  const adminRoots = new Set([
    '', 'upload', 'attendance', 'attendance-audit', 'observations', 'planilla',
    'teachers', 'users', 'requests', 'reports', 'contracts', 'activity', 'backup',
    'practice-attendance', 'practice-planilla', 'settings',
  ])
  return adminRoots.has(pathname.split('/')[1] ?? '') ? returnUrl : null
}

export const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Attach auth token from localStorage on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Expire protected sessions on 401 without swallowing login credential errors.
api.interceptors.response.use(
  (response) => {
    const requestPath = response.config.url?.split('?')[0]
    if (requestPath === '/auth/login' || requestPath === '/api/auth/login') {
      isHandlingUnauthorized = false
    }
    return response
  },
  (error) => {
    const requestPath = error.config?.url?.split('?')[0]
    const isLoginRequest = requestPath === '/auth/login' || requestPath === '/api/auth/login'
    const hasSession = Boolean(localStorage.getItem('auth_token'))

    if (error.response?.status === 401 && !isLoginRequest && hasSession && !isHandlingUnauthorized) {
      isHandlingUnauthorized = true
      localStorage.removeItem('auth_token')
      sessionStorage.setItem(AUTH_LOGOUT_REASON_KEY, 'session-expired')

      const currentPath = getSafeLocalPath(
        `${window.location.pathname}${window.location.search}${window.location.hash}`,
      )
      if (currentPath && window.location.pathname !== '/login' && window.location.pathname !== '/change-password') {
        sessionStorage.setItem(AUTH_RETURN_URL_KEY, currentPath)
      }

      if (window.location.pathname !== '/login') {
        window.location.replace('/login')
      } else {
        isHandlingUnauthorized = false
      }
    }
    return Promise.reject(error)
  }
)
