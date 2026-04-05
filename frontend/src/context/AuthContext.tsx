import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/api/client'
import type { AuthUser, LoginResponse } from '@/api/types'

interface AuthContextType {
  user: AuthUser | null
  token: string | null
  isAuthenticated: boolean
  isAdmin: boolean
  isDocente: boolean
  mustChangePassword: boolean
  login: (ci: string, password: string) => Promise<void>
  logout: () => void
  isLoading: boolean
}

const AuthContext = createContext<AuthContextType | null>(null)

const TOKEN_KEY = 'auth_token'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const navigate = useNavigate()

  // On mount: restore session from localStorage
  useEffect(() => {
    const savedToken = localStorage.getItem(TOKEN_KEY)
    if (!savedToken) {
      setIsLoading(false)
      return
    }

    // Validate token by calling /api/auth/me
    api
      .get<AuthUser>('/auth/me', {
        headers: { Authorization: `Bearer ${savedToken}` },
      })
      .then((res) => {
        setToken(savedToken)
        setUser(res.data)
        // Force password change on session restore too
        if (res.data.must_change_password) {
          navigate('/change-password')
        }
      })
      .catch(() => {
        // Token invalid or expired
        localStorage.removeItem(TOKEN_KEY)
      })
      .finally(() => {
        setIsLoading(false)
      })
  }, [])

  const login = useCallback(async (ci: string, password: string) => {
    const res = await api.post<LoginResponse>('/auth/login', { ci, password })
    const { access_token, user: loggedUser, must_change_password } = res.data

    localStorage.setItem(TOKEN_KEY, access_token)
    setToken(access_token)
    setUser(loggedUser)

    // Force password change if required
    if (must_change_password) {
      navigate('/change-password')
      return
    }

    // Redirect based on role
    if (loggedUser.role === 'admin') {
      navigate('/')
    } else {
      navigate('/portal')
    }
  }, [navigate])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUser(null)
    navigate('/login')
  }, [navigate])

  const mustChangePassword = user?.must_change_password ?? false

  const value: AuthContextType = {
    user,
    token,
    isAuthenticated: Boolean(user),
    isAdmin: user?.role === 'admin',
    isDocente: user?.role === 'docente',
    mustChangePassword,
    login,
    logout,
    isLoading,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  }
  return ctx
}
