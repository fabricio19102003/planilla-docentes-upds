import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { useChangePassword } from '@/api/hooks/useAuth'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Field, FieldError, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Logo } from '@/components/layout/Logo'
import { consumePostLoginReturnUrl } from '@/api/client'
import { cn } from '@/lib/utils'
import { AlertCircle, CheckCircle2, XCircle, Lock, Eye, EyeOff } from 'lucide-react'

// ─── Password strength bar ────────────────────────────────────────────────────

const STRENGTH_BAR = ['bg-destructive', 'bg-warning', 'bg-warning', 'bg-success']
const STRENGTH_TEXT = [
  'text-destructive-foreground',
  'text-warning-foreground',
  'text-warning-foreground',
  'text-success-foreground',
]

function PasswordStrengthBar({ password }: { password: string }) {
  const checks = [
    password.length >= 8,
    /[A-Z]/.test(password),
    /[a-z]/.test(password),
    /\d/.test(password),
  ]
  const strength = checks.filter(Boolean).length
  const labels = ['Débil', 'Regular', 'Buena', 'Fuerte']

  if (!password) return null

  return (
    <div className="mt-2 w-full space-y-1.5">
      <div className="flex gap-1">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className={cn(
              'h-1.5 flex-1 rounded-full transition-colors duration-300',
              i < strength ? STRENGTH_BAR[strength - 1] : 'bg-muted',
            )}
          />
        ))}
      </div>
      <p className={cn('text-xs font-medium', STRENGTH_TEXT[strength - 1])}>{labels[strength - 1] ?? ''}</p>
    </div>
  )
}

// ─── Validation checklist ─────────────────────────────────────────────────────

function ValidationItem({ passes, label }: { passes: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2">
      {passes ? (
        <CheckCircle2 size={13} className="shrink-0 text-success-foreground" aria-hidden="true" />
      ) : (
        <XCircle size={13} className="shrink-0 text-muted-foreground" aria-hidden="true" />
      )}
      <span className={cn('text-xs', passes ? 'text-success-foreground' : 'text-muted-foreground')}>{label}</span>
    </div>
  )
}

function PasswordInput({
  id,
  value,
  onChange,
  placeholder,
  disabled,
  invalid,
  describedBy,
  visible,
  onToggle,
  toggleLabel,
}: {
  id: string
  value: string
  onChange: (value: string) => void
  placeholder: string
  disabled: boolean
  invalid: boolean
  describedBy?: string
  visible: boolean
  onToggle: () => void
  toggleLabel: string
}) {
  return (
    <div className="relative w-full">
      <Input
        id={id}
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        aria-invalid={invalid}
        aria-describedby={describedBy}
        inputClassName="pr-10"
      />
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        onClick={onToggle}
        className="absolute right-1 top-1/2 -translate-y-1/2 text-muted-foreground"
        aria-label={toggleLabel}
      >
        {visible ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
      </Button>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function ForceChangePasswordPage() {
  const { refreshUser } = useAuth()
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
  const isDifferentPassword = form.newPwd.length > 0 && form.newPwd !== form.current
  const canSubmit = form.current.length > 0 && allChecksPassed && passwordsMatch && isDifferentPassword

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setError(null)

    try {
      await changePwd.mutateAsync({
        current_password: form.current,
        new_password: form.newPwd,
      })
      const nextUser = await refreshUser()
      setSuccess(true)
      // Redirect after short delay
      setTimeout(() => {
        const returnUrl = consumePostLoginReturnUrl(nextUser.role)
        navigate(returnUrl ?? (nextUser.role === 'admin' ? '/' : '/portal'))
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
    <main className="flex min-h-screen flex-col items-center justify-center bg-muted/40 p-4 sm:p-6">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <div className="rounded-2xl bg-primary px-8 py-5 shadow-sm">
            <Logo size="md" />
          </div>
        </div>

        <Card className="p-6 sm:p-8">
          {/* Title */}
          <div className="mb-6 text-center">
            <div className="mb-2 flex items-center justify-center gap-2">
              <Lock size={18} className="text-warning" aria-hidden="true" />
              <h1 className="text-lg font-semibold tracking-tight text-foreground">Debés cambiar tu contraseña</h1>
            </div>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Tu cuenta tiene una contraseña temporal. Por seguridad, establecé una nueva contraseña
              antes de continuar.
            </p>
          </div>

          {success ? (
            <div aria-live="polite" className="flex flex-col items-center gap-3 py-6">
              <div className="flex size-14 items-center justify-center rounded-full bg-success/10">
                <CheckCircle2 size={32} className="text-success" aria-hidden="true" />
              </div>
              <p className="text-center font-semibold text-success-foreground">
                ¡Contraseña actualizada correctamente!
              </p>
              <p className="text-center text-sm text-muted-foreground">Redirigiendo...</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Current password */}
              <Field>
                <FieldLabel htmlFor="force-current-password">Contraseña temporal actual *</FieldLabel>
                <PasswordInput
                  id="force-current-password"
                  value={form.current}
                  onChange={(value) => setForm((f) => ({ ...f, current: value }))}
                  placeholder="Ingresá tu contraseña temporal"
                  disabled={changePwd.isPending}
                  invalid={Boolean(error)}
                  describedBy={error ? 'force-password-error' : undefined}
                  visible={showCurrent}
                  onToggle={() => setShowCurrent((v) => !v)}
                  toggleLabel={showCurrent ? 'Ocultar contraseña actual' : 'Mostrar contraseña actual'}
                />
              </Field>

              {/* New password */}
              <Field>
                <FieldLabel htmlFor="force-new-password">Nueva contraseña *</FieldLabel>
                <PasswordInput
                  id="force-new-password"
                  value={form.newPwd}
                  onChange={(value) => setForm((f) => ({ ...f, newPwd: value }))}
                  placeholder="Mínimo 8 caracteres"
                  disabled={changePwd.isPending}
                  invalid={Boolean(error)}
                  describedBy={error ? 'force-password-error' : undefined}
                  visible={showNew}
                  onToggle={() => setShowNew((v) => !v)}
                  toggleLabel={showNew ? 'Ocultar nueva contraseña' : 'Mostrar nueva contraseña'}
                />
                <PasswordStrengthBar password={form.newPwd} />
              </Field>

              {/* Confirm password */}
              <Field>
                <FieldLabel htmlFor="force-confirm-password">Confirmar nueva contraseña *</FieldLabel>
                <PasswordInput
                  id="force-confirm-password"
                  value={form.confirm}
                  onChange={(value) => setForm((f) => ({ ...f, confirm: value }))}
                  placeholder="Repetí la nueva contraseña"
                  disabled={changePwd.isPending}
                  invalid={Boolean((form.confirm && !passwordsMatch) || error)}
                  describedBy={form.confirm && !passwordsMatch ? 'force-confirm-error' : error ? 'force-password-error' : undefined}
                  visible={showConfirm}
                  onToggle={() => setShowConfirm((v) => !v)}
                  toggleLabel={showConfirm ? 'Ocultar confirmación de contraseña' : 'Mostrar confirmación de contraseña'}
                />
                {form.confirm && !passwordsMatch && (
                  <FieldError id="force-confirm-error" role="alert" match>
                    Las contraseñas no coinciden
                  </FieldError>
                )}
              </Field>

              {/* Validation checklist */}
              {form.newPwd && (
                <div className="space-y-1.5 rounded-lg border bg-muted/40 p-3">
                  <p className="mb-2 text-xs font-medium text-muted-foreground">Requisitos:</p>
                  <ValidationItem passes={checks.length} label="Mínimo 8 caracteres" />
                  <ValidationItem passes={checks.upper} label="Al menos una mayúscula" />
                  <ValidationItem passes={checks.lower} label="Al menos una minúscula" />
                  <ValidationItem passes={checks.digit} label="Al menos un número" />
                  <ValidationItem passes={isDifferentPassword} label="Debe ser diferente de la contraseña actual" />
                </div>
              )}

              {/* Error */}
              {error && (
                <Alert id="force-password-error" variant="error">
                  <AlertCircle aria-hidden="true" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              {/* Submit */}
              <Button
                type="submit"
                size="lg"
                disabled={!canSubmit}
                loading={changePwd.isPending}
                className="mt-2 w-full"
              >
                {changePwd.isPending ? 'Guardando...' : 'Establecer nueva contraseña'}
              </Button>
            </form>
          )}
        </Card>
      </div>
    </main>
  )
}
