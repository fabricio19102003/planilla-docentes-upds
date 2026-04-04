import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { useChangePassword } from '@/api/hooks/useAuth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { AlertCircle, CheckCircle2, XCircle, Lock, Eye, EyeOff } from 'lucide-react'

// ─── Password strength bar ────────────────────────────────────────────────────

function PasswordStrengthBar({ password }: { password: string }) {
  const checks = [
    password.length >= 8,
    /[A-Z]/.test(password),
    /[a-z]/.test(password),
    /\d/.test(password),
  ]
  const strength = checks.filter(Boolean).length
  const colors = ['bg-red-400', 'bg-orange-400', 'bg-yellow-400', 'bg-green-500']
  const labels = ['Débil', 'Regular', 'Buena', 'Fuerte']

  if (!password) return null

  return (
    <div className="space-y-1.5 mt-2">
      <div className="flex gap-1">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className={`h-1.5 flex-1 rounded-full transition-colors duration-300 ${
              i < strength ? colors[strength - 1] : 'bg-gray-200'
            }`}
          />
        ))}
      </div>
      <p
        className={`text-xs font-medium ${
          strength <= 1
            ? 'text-red-400'
            : strength === 2
              ? 'text-orange-400'
              : strength === 3
                ? 'text-yellow-400'
                : 'text-green-400'
        }`}
      >
        {labels[strength - 1] ?? ''}
      </p>
    </div>
  )
}

// ─── Validation checklist ─────────────────────────────────────────────────────

function ValidationItem({ passes, label }: { passes: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2">
      {passes ? (
        <CheckCircle2 size={13} className="text-green-400 flex-shrink-0" />
      ) : (
        <XCircle size={13} className="text-white/30 flex-shrink-0" />
      )}
      <span className={`text-xs ${passes ? 'text-green-300' : 'text-white/50'}`}>{label}</span>
    </div>
  )
}

// ─── UPDSLogo (same as LoginPage) ─────────────────────────────────────────────

function UPDSLogo() {
  return (
    <div className="flex flex-col items-center gap-2 mb-6">
      <div className="font-black tracking-widest text-5xl leading-none select-none">
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

// ─── Page ─────────────────────────────────────────────────────────────────────

export function ForceChangePasswordPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const changePwd = useChangePassword()

  const [form, setForm] = useState({ current: '', newPwd: '', confirm: '' })
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const checks = {
    length: form.newPwd.length >= 8,
    upper: /[A-Z]/.test(form.newPwd),
    lower: /[a-z]/.test(form.newPwd),
    digit: /\d/.test(form.newPwd),
  }
  const allChecksPassed = Object.values(checks).every(Boolean)
  const passwordsMatch = form.newPwd === form.confirm && form.confirm.length > 0
  const canSubmit = form.current.length > 0 && allChecksPassed && passwordsMatch

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setError(null)

    try {
      await changePwd.mutateAsync({
        current_password: form.current,
        new_password: form.newPwd,
      })
      setSuccess(true)
      // Redirect after short delay
      setTimeout(() => {
        if (user?.role === 'admin') {
          navigate('/')
        } else {
          navigate('/portal')
        }
      }, 1500)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      const detail = axiosErr?.response?.data?.detail
      if (typeof detail === 'string') {
        setError(detail)
      } else if (Array.isArray(detail)) {
        // Pydantic validation errors
        const msgs = (detail as Array<{ msg: string }>).map((d) => d.msg).join(' | ')
        setError(msgs)
      } else {
        setError('No se pudo cambiar la contraseña. Verificá la contraseña actual.')
      }
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
      <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden="true">
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
        <div className="text-center mb-6">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Lock size={18} className="text-yellow-400" />
            <h1 className="text-white text-lg font-semibold">Debés cambiar tu contraseña</h1>
          </div>
          <p className="text-white/50 text-sm leading-relaxed">
            Tu cuenta tiene una contraseña temporal. Por seguridad, establecé una nueva contraseña
            antes de continuar.
          </p>
        </div>

        {success ? (
          <div className="flex flex-col items-center gap-3 py-6">
            <div className="w-14 h-14 rounded-full bg-green-500/20 flex items-center justify-center">
              <CheckCircle2 size={32} className="text-green-400" />
            </div>
            <p className="text-green-300 font-semibold text-center">
              ¡Contraseña actualizada correctamente!
            </p>
            <p className="text-white/40 text-sm text-center">Redirigiendo...</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Current password */}
            <div className="space-y-1.5">
              <Label className="text-white/70 text-sm">Contraseña temporal actual *</Label>
              <div className="relative">
                <Input
                  type={showCurrent ? 'text' : 'password'}
                  value={form.current}
                  onChange={(e) => setForm((f) => ({ ...f, current: e.target.value }))}
                  placeholder="Ingresá tu contraseña temporal"
                  disabled={changePwd.isPending}
                  className="h-10 bg-white/10 border-white/20 text-white placeholder:text-white/30 focus:border-[#4DA8DA] pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowCurrent((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70 transition-colors"
                  tabIndex={-1}
                >
                  {showCurrent ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {/* New password */}
            <div className="space-y-1.5">
              <Label className="text-white/70 text-sm">Nueva contraseña *</Label>
              <div className="relative">
                <Input
                  type={showNew ? 'text' : 'password'}
                  value={form.newPwd}
                  onChange={(e) => setForm((f) => ({ ...f, newPwd: e.target.value }))}
                  placeholder="Mínimo 8 caracteres"
                  disabled={changePwd.isPending}
                  className="h-10 bg-white/10 border-white/20 text-white placeholder:text-white/30 focus:border-[#4DA8DA] pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowNew((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70 transition-colors"
                  tabIndex={-1}
                >
                  {showNew ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              <PasswordStrengthBar password={form.newPwd} />
            </div>

            {/* Confirm password */}
            <div className="space-y-1.5">
              <Label className="text-white/70 text-sm">Confirmar nueva contraseña *</Label>
              <div className="relative">
                <Input
                  type={showConfirm ? 'text' : 'password'}
                  value={form.confirm}
                  onChange={(e) => setForm((f) => ({ ...f, confirm: e.target.value }))}
                  placeholder="Repetí la nueva contraseña"
                  disabled={changePwd.isPending}
                  className={`h-10 bg-white/10 border-white/20 text-white placeholder:text-white/30 focus:border-[#4DA8DA] pr-10 ${
                    form.confirm && !passwordsMatch ? 'border-red-400/60' : ''
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70 transition-colors"
                  tabIndex={-1}
                >
                  {showConfirm ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              {form.confirm && !passwordsMatch && (
                <p className="text-red-400 text-xs">Las contraseñas no coinciden</p>
              )}
            </div>

            {/* Validation checklist */}
            {form.newPwd && (
              <div
                className="rounded-lg p-3 space-y-1.5"
                style={{ backgroundColor: 'rgba(255,255,255,0.05)' }}
              >
                <p className="text-white/40 text-xs font-medium mb-2">Requisitos:</p>
                <ValidationItem passes={checks.length} label="Mínimo 8 caracteres" />
                <ValidationItem passes={checks.upper} label="Al menos una mayúscula" />
                <ValidationItem passes={checks.lower} label="Al menos una minúscula" />
                <ValidationItem passes={checks.digit} label="Al menos un número" />
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="flex items-start gap-2.5 bg-red-500/15 border border-red-500/30 rounded-lg px-3 py-2.5">
                <AlertCircle size={15} className="text-red-400 flex-shrink-0 mt-0.5" />
                <p className="text-red-300 text-sm leading-snug">{error}</p>
              </div>
            )}

            {/* Submit */}
            <Button
              type="submit"
              disabled={!canSubmit || changePwd.isPending}
              className="w-full h-10 font-semibold text-white mt-2 disabled:opacity-40"
              style={{ backgroundColor: '#0066CC' }}
            >
              {changePwd.isPending ? (
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Guardando...
                </div>
              ) : (
                'Establecer nueva contraseña'
              )}
            </Button>
          </form>
        )}
      </div>
    </div>
  )
}
