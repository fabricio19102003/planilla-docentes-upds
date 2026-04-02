import { useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { AlertCircle, LogIn, Eye, EyeOff } from 'lucide-react'

function UPDSLogo() {
  return (
    <div className="flex flex-col items-center gap-2 mb-8">
      <div className="font-black tracking-widest text-6xl leading-none select-none">
        <span style={{ color: '#4DA8DA' }}>U</span>
        <span style={{ color: '#0099FF' }}>P</span>
        <span style={{ color: '#4DA8DA' }}>D</span>
        <span style={{ color: '#FFFFFF' }}>S</span>
      </div>
      <p className="text-white/50 text-xs tracking-[0.3em] uppercase font-medium mt-1">
        Universidad Privada Domingo Savio
      </p>
    </div>
  )
}

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
      if (axiosErr?.response?.status === 401) {
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
    <div
      className="min-h-screen flex items-center justify-center p-4"
      style={{
        background: 'linear-gradient(135deg, #001a33 0%, #003366 50%, #004080 100%)',
      }}
    >
      {/* Decorative background circles */}
      <div
        className="absolute inset-0 overflow-hidden pointer-events-none"
        aria-hidden="true"
      >
        <div
          className="absolute -top-32 -left-32 w-96 h-96 rounded-full opacity-10"
          style={{ backgroundColor: '#4DA8DA' }}
        />
        <div
          className="absolute -bottom-32 -right-32 w-96 h-96 rounded-full opacity-10"
          style={{ backgroundColor: '#0066CC' }}
        />
        <div
          className="absolute top-1/2 left-1/4 w-64 h-64 rounded-full opacity-5"
          style={{ backgroundColor: '#4DA8DA' }}
        />
      </div>

      {/* Card */}
      <div
        className="relative w-full max-w-sm rounded-2xl shadow-2xl p-8"
        style={{
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          backdropFilter: 'blur(20px)',
          border: '1px solid rgba(255,255,255,0.1)',
        }}
      >
        <UPDSLogo />

        {/* Title */}
        <div className="text-center mb-8">
          <h1 className="text-white text-xl font-semibold tracking-wide">
            Sistema de Planillas
          </h1>
          <p className="text-white/40 text-sm mt-1">
            Ingresá con tu cuenta institucional
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* CI */}
          <div className="space-y-1.5">
            <Label className="text-white/70 text-sm font-medium">
              Cédula de Identidad
            </Label>
            <Input
              type="text"
              placeholder="Ej: 12345678"
              value={ci}
              onChange={(e) => setCi(e.target.value)}
              autoComplete="username"
              disabled={isLoading}
              className="h-11 bg-white/10 border-white/20 text-white placeholder:text-white/30 focus:border-[#4DA8DA] focus:ring-[#4DA8DA]/20"
            />
          </div>

          {/* Password */}
          <div className="space-y-1.5">
            <Label className="text-white/70 text-sm font-medium">
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
                className="h-11 bg-white/10 border-white/20 text-white placeholder:text-white/30 focus:border-[#4DA8DA] focus:ring-[#4DA8DA]/20 pr-11"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70 transition-colors"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-start gap-2.5 bg-red-500/15 border border-red-500/30 rounded-lg px-3 py-2.5">
              <AlertCircle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
              <p className="text-red-300 text-sm leading-snug">{error}</p>
            </div>
          )}

          {/* Submit */}
          <Button
            type="submit"
            disabled={isLoading}
            className="w-full h-11 font-semibold text-white gap-2 mt-2"
            style={{ backgroundColor: '#0066CC' }}
          >
            {isLoading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Ingresando...
              </>
            ) : (
              <>
                <LogIn size={16} />
                Ingresar
              </>
            )}
          </Button>
        </form>

        {/* Footer */}
        <p className="text-center text-white/25 text-xs mt-8">
          Sistema de Planillas Docentes v1.0
        </p>
      </div>
    </div>
  )
}
