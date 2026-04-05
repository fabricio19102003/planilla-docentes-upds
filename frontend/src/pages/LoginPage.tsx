import { useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { AlertCircle, LogIn, Eye, EyeOff, ShieldAlert } from 'lucide-react'

export function LoginPage() {
  const { login } = useAuth()
  const [ci, setCi] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
    <div className="min-h-screen flex flex-col lg:flex-row">
      {/* ── Left panel: Branding ─────────────────────────────────── */}
      <div
        className="hidden lg:flex lg:w-[55%] relative flex-col items-center justify-center p-12 overflow-hidden"
        style={{
          background: 'linear-gradient(160deg, #001a33 0%, #003366 40%, #004d99 70%, #0066CC 100%)',
        }}
      >
        {/* Decorative elements */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden="true">
          <div className="absolute -top-40 -left-40 w-[500px] h-[500px] rounded-full opacity-[0.07]" style={{ backgroundColor: '#4DA8DA' }} />
          <div className="absolute -bottom-40 -right-40 w-[600px] h-[600px] rounded-full opacity-[0.05]" style={{ backgroundColor: '#0099FF' }} />
          <div className="absolute top-1/3 right-1/4 w-80 h-80 rounded-full opacity-[0.04]" style={{ backgroundColor: '#4DA8DA' }} />
          {/* Grid pattern overlay */}
          <div
            className="absolute inset-0 opacity-[0.03]"
            style={{
              backgroundImage: 'linear-gradient(rgba(255,255,255,.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.1) 1px, transparent 1px)',
              backgroundSize: '60px 60px',
            }}
          />
        </div>

        <div className="relative z-10 text-center max-w-lg">
          {/* UPDS Letters */}
          <div className="mb-8">
            <div className="font-black tracking-[0.2em] text-8xl leading-none select-none" style={{ textShadow: '0 4px 30px rgba(0,102,204,0.4)' }}>
              <span style={{ color: '#4DA8DA' }}>U</span>
              <span style={{ color: '#7CC0E8' }}>P</span>
              <span style={{ color: '#4DA8DA' }}>D</span>
              <span className="text-white">S</span>
            </div>
            <p className="text-white/40 text-sm tracking-[0.4em] uppercase font-medium mt-4">
              Universidad Privada Domingo Savio
            </p>
          </div>

          {/* Divider */}
          <div className="flex items-center gap-4 my-8">
            <div className="flex-1 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />
          </div>

          {/* SIPAD branding */}
          <div>
            <h1 className="text-white text-3xl font-bold tracking-wide" style={{ textShadow: '0 2px 20px rgba(0,102,204,0.3)' }}>
              SIPAD
            </h1>
            <p className="text-white/50 text-base mt-2 font-light">
              Sistema Integrado de Pago Docente
            </p>
          </div>

          {/* Stats decorative */}
          <div className="flex items-center justify-center gap-8 mt-12">
            <div className="text-center">
              <p className="text-white/80 text-2xl font-bold">100+</p>
              <p className="text-white/30 text-xs uppercase tracking-wider mt-1">Docentes</p>
            </div>
            <div className="w-px h-10 bg-white/10" />
            <div className="text-center">
              <p className="text-white/80 text-2xl font-bold">400+</p>
              <p className="text-white/30 text-xs uppercase tracking-wider mt-1">Designaciones</p>
            </div>
            <div className="w-px h-10 bg-white/10" />
            <div className="text-center">
              <p className="text-white/80 text-2xl font-bold">24/7</p>
              <p className="text-white/30 text-xs uppercase tracking-wider mt-1">Disponible</p>
            </div>
          </div>
        </div>

        {/* Bottom text */}
        <p className="absolute bottom-6 text-white/20 text-xs tracking-wider">
          Sede Cobija — Gestión {new Date().getFullYear()}
        </p>
      </div>

      {/* ── Mobile header (lg:hidden) ────────────────────────────── */}
      <div className="lg:hidden w-full">
        <div
          className="w-full py-8 px-6 text-center"
          style={{ background: 'linear-gradient(160deg, #001a33 0%, #003366 50%, #0066CC 100%)' }}
        >
          <div className="font-black tracking-[0.15em] text-5xl leading-none select-none mb-2" style={{ textShadow: '0 2px 20px rgba(0,102,204,0.3)' }}>
            <span style={{ color: '#4DA8DA' }}>U</span>
            <span style={{ color: '#7CC0E8' }}>P</span>
            <span style={{ color: '#4DA8DA' }}>D</span>
            <span className="text-white">S</span>
          </div>
          <p className="text-white/40 text-xs tracking-[0.3em] uppercase font-medium">
            Universidad Privada Domingo Savio
          </p>
          <div className="flex items-center gap-3 justify-center my-3">
            <div className="flex-1 max-w-[60px] h-px bg-white/20" />
            <span className="text-white/50 text-xs">•</span>
            <div className="flex-1 max-w-[60px] h-px bg-white/20" />
          </div>
          <h1 className="text-white text-xl font-bold tracking-wide">SIPAD</h1>
          <p className="text-white/40 text-xs mt-1">Sistema Integrado de Pago Docente</p>
        </div>
      </div>

      {/* ── Right panel: Login form ──────────────────────────────── */}
      <div
        className="flex-1 flex flex-col items-center justify-center p-6 lg:p-12"
        style={{ backgroundColor: '#f8fafc' }}
      >
        <div className="w-full max-w-sm">
          {/* Welcome text */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold" style={{ color: '#003366' }}>
              Bienvenido
            </h2>
            <p className="text-gray-500 mt-1">
              Ingresá con tu cuenta institucional
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* CI */}
            <div className="space-y-2">
              <Label className="text-sm font-medium text-gray-700">
                Cédula de Identidad
              </Label>
              <Input
                type="text"
                placeholder="Ej: 12345678"
                value={ci}
                onChange={(e) => setCi(e.target.value)}
                autoComplete="username"
                disabled={isLoading}
                className="h-12 bg-white border-gray-200 text-gray-800 placeholder:text-gray-400 focus:border-[#0066CC] focus:ring-[#0066CC]/20 rounded-xl shadow-sm"
              />
            </div>

            {/* Password */}
            <div className="space-y-2">
              <Label className="text-sm font-medium text-gray-700">
                Contraseña
              </Label>
              <div className="relative">
                <Input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  disabled={isLoading}
                  className="h-12 bg-white border-gray-200 text-gray-800 placeholder:text-gray-400 focus:border-[#0066CC] focus:ring-[#0066CC]/20 pr-12 rounded-xl shadow-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div
                className={`flex items-start gap-2.5 rounded-xl px-4 py-3 ${
                  error.includes('deshabilitada')
                    ? 'bg-orange-50 border border-orange-200'
                    : 'bg-red-50 border border-red-200'
                }`}
              >
                {error.includes('deshabilitada') ? (
                  <ShieldAlert size={16} className="text-orange-500 flex-shrink-0 mt-0.5" />
                ) : (
                  <AlertCircle size={16} className="text-red-500 flex-shrink-0 mt-0.5" />
                )}
                <p
                  className={`text-sm leading-snug ${
                    error.includes('deshabilitada') ? 'text-orange-700' : 'text-red-600'
                  }`}
                >
                  {error}
                </p>
              </div>
            )}

            {/* Submit */}
            <Button
              type="submit"
              disabled={isLoading}
              className="w-full h-12 font-semibold text-white gap-2 rounded-xl shadow-lg hover:shadow-xl transition-shadow"
              style={{ backgroundColor: '#003366' }}
            >
              {isLoading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Ingresando...
                </>
              ) : (
                <>
                  <LogIn size={18} />
                  Ingresar al Sistema
                </>
              )}
            </Button>
          </form>

          {/* Footer */}
          <div className="mt-10 pt-6 border-t border-gray-200">
            <p className="text-center text-gray-400 text-xs">
              SIPAD — Sistema Integrado de Pago Docente
            </p>
            <p className="text-center text-gray-300 text-xs mt-1">
              © {new Date().getFullYear()} UPDS — Sede Cobija
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
