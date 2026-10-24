import { Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

interface ProtectedRouteProps {
  children: React.ReactNode
  requiredRole?: 'admin' | 'docente'
}

export function ProtectedRoute({ children, requiredRole }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, mustChangePassword, user } = useAuth()

  // While checking token on mount, show nothing (avoids flash)
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-primary">
        <div className="text-primary-foreground text-center">
          <div className="mx-auto mb-3 size-8 animate-spin rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground motion-reduce:animate-none" />
          <p className="text-sm text-primary-foreground/70">Verificando sesión...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (mustChangePassword) {
    return <Navigate to="/change-password" replace />
  }

  if (requiredRole && user?.role !== requiredRole) {
    // Wrong role: redirect to the correct home
    if (user?.role === 'admin') return <Navigate to="/" replace />
    return <Navigate to="/portal" replace />
  }

  return <>{children}</>
}
