import { useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Field, FieldLabel } from '@/components/ui/field'
import { Logo } from '@/components/layout/Logo'
import { AlertCircle, LogIn, Eye, EyeOff, ShieldAlert } from 'lucide-react'
import { AUTH_LOGOUT_REASON_KEY } from '@/api/client'

export function LoginPage() {
  const { login } = useAuth()
  const [ci, setCi] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionMessage] = useState(() => {
    const reason = sessionStorage.getItem(AUTH_LOGOUT_REASON_KEY)
    sessionStorage.removeItem(AUTH_LOGOUT_REASON_KEY)
    return reason === 'session-expired'
      ? 'Tu sesión venció. Ingresá nuevamente para continuar donde estabas.'
      : null
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!ci.trim() || !password.trim()) {
      setError('Ingresá tu CI y contraseña.')
      return
    }
    setError(null)
    setIsLoading(true)
    try {
      await login(ci.trim(), password)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } }
      if (axiosErr?.response?.status === 403) {
        setError(axiosErr.response?.data?.detail ?? 'Tu cuenta ha sido deshabilitada.')
      } else if (axiosErr?.response?.status === 401) {
        setError('CI o contraseña incorrectos.')
      } else if (axiosErr?.response?.data?.detail) {
        setError(axiosErr.response.data.detail)
      } else {
        setError('No se pudo conectar al servidor. Verificá que esté en línea.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-muted/40 p-4 sm:p-6">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <div className="rounded-2xl bg-primary px-8 py-5 shadow-sm">
            <Logo size="md" />
          </div>
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-foreground">SIPAD</h1>
            <p className="text-sm text-muted-foreground">Sistema Integrado de Pago Docente</p>
          </div>
        </div>

        <Card className="p-6 sm:p-8">
          {/* Welcome text */}
          <div className="mb-6">
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">Bienvenido</h2>
            <p className="mt-1 text-sm text-muted-foreground">Ingresá con tus credenciales de acceso</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {sessionMessage && (
              <Alert variant="warning">
                <AlertCircle aria-hidden="true" />
                <AlertDescription>{sessionMessage}</AlertDescription>
              </Alert>
            )}

            {/* CI */}
            <Field>
              <FieldLabel htmlFor="login-ci">Cédula de Identidad</FieldLabel>
              <Input
                id="login-ci"
                type="text"
                size="lg"
                placeholder="Ej: 12345678"
                value={ci}
                onChange={(e) => setCi(e.target.value)}
                autoComplete="username"
                disabled={isLoading}
                aria-invalid={Boolean(error)}
                aria-describedby={error ? 'login-error' : undefined}
              />
            </Field>

            {/* Password */}
            <Field>
              <FieldLabel htmlFor="login-password">Contraseña</FieldLabel>
              <div className="relative w-full">
                <Input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  size="lg"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  disabled={isLoading}
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? 'login-error' : undefined}
                  inputClassName="pr-11"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-1 top-1/2 -translate-y-1/2 text-muted-foreground"
                  aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                >
                  {showPassword ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
                </Button>
              </div>
            </Field>

            {/* Error */}
            {error && (
              <Alert id="login-error" variant={error.includes('deshabilitada') ? 'info' : 'error'}>
                {error.includes('deshabilitada') ? <ShieldAlert aria-hidden="true" /> : <AlertCircle aria-hidden="true" />}
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* Submit */}
            <Button type="submit" size="lg" loading={isLoading} className="w-full">
              {isLoading ? (
                'Ingresando...'
              ) : (
                <>
                  <LogIn aria-hidden="true" />
                  Ingresar al Sistema
                </>
              )}
            </Button>
          </form>
        </Card>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          © {new Date().getFullYear()} UPDS - Sede Cobija
        </p>
      </div>
    </main>
  )
}
