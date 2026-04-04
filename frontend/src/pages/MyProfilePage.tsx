import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useMyProfile, useChangePassword, useUpdateProfile, useMySchedule } from '@/api/hooks/useAuth'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  User,
  Mail,
  Phone,
  BookOpen,
  Lock,
  CheckCircle,
  AlertCircle,
  Pencil,
  X,
  Save,
  Calendar,
  CreditCard,
  CheckCircle2,
  XCircle,
  Eye,
  EyeOff,
  ChevronRight,
} from 'lucide-react'

// ─── Types ────────────────────────────────────────────────────────────────────

interface ProfileData {
  ci: string
  full_name: string
  email: string | null
  phone: string | null
  gender: string | null
  external_permanent: string | null
  academic_level: string | null
  profession: string | null
  specialty: string | null
  bank: string | null
  account_number: string | null
  designation_count: number
}

// ─── Shared display components ────────────────────────────────────────────────

function InfoRow({ icon: Icon, label, value }: { icon: typeof User; label: string; value: string | null }) {
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-gray-100 last:border-0">
      <div
        className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
        style={{ backgroundColor: 'rgba(0,51,102,0.08)' }}
      >
        <Icon size={15} style={{ color: '#003366' }} />
      </div>
      <div>
        <p className="text-xs text-gray-400 font-medium">{label}</p>
        <p className="text-sm text-gray-700 font-medium mt-0.5">{value || '—'}</p>
      </div>
    </div>
  )
}

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
    <div className="space-y-1.5 mt-1">
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
            ? 'text-red-500'
            : strength === 2
              ? 'text-orange-500'
              : strength === 3
                ? 'text-yellow-600'
                : 'text-green-600'
        }`}
      >
        {labels[strength - 1] ?? ''}
      </p>
    </div>
  )
}

function ValidationItem({ passes, label }: { passes: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2">
      {passes ? (
        <CheckCircle2 size={13} className="text-green-500 flex-shrink-0" />
      ) : (
        <XCircle size={13} className="text-gray-300 flex-shrink-0" />
      )}
      <span className={`text-xs ${passes ? 'text-green-700' : 'text-gray-400'}`}>{label}</span>
    </div>
  )
}

// ─── Editable personal data card ──────────────────────────────────────────────

function PersonalDataCard({ p }: { p: ProfileData }) {
  const updateProfile = useUpdateProfile()
  const [editMode, setEditMode] = useState(false)
  const [editForm, setEditForm] = useState({
    email: '',
    phone: '',
    bank: '',
    account_number: '',
  })
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    setEditForm({
      email: p.email ?? '',
      phone: p.phone ?? '',
      bank: p.bank ?? '',
      account_number: p.account_number ?? '',
    })
  }, [p])

  const handleSave = async () => {
    setSaveError(null)
    try {
      await updateProfile.mutateAsync({
        email: editForm.email || undefined,
        phone: editForm.phone || undefined,
        bank: editForm.bank || undefined,
        account_number: editForm.account_number || undefined,
      })
      setSaveSuccess(true)
      setEditMode(false)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setSaveError(axiosErr?.response?.data?.detail ?? 'Error al guardar los cambios')
    }
  }

  const handleCancel = () => {
    setEditForm({
      email: p.email ?? '',
      phone: p.phone ?? '',
      bank: p.bank ?? '',
      account_number: p.account_number ?? '',
    })
    setSaveError(null)
    setEditMode(false)
  }

  return (
    <div className="card-3d-static overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
        <User size={16} style={{ color: '#003366' }} />
        <h3 className="text-base font-semibold flex-1" style={{ color: '#003366' }}>
          Datos Personales
        </h3>
        {!editMode ? (
          <button
            onClick={() => setEditMode(true)}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-[#003366] transition-colors px-2 py-1 rounded hover:bg-gray-100"
          >
            <Pencil size={12} />
            Editar
          </button>
        ) : (
          <div className="flex items-center gap-1.5">
            <button
              onClick={handleCancel}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 transition-colors px-2 py-1 rounded hover:bg-gray-100"
            >
              <X size={12} />
              Cancelar
            </button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={updateProfile.isPending}
              className="h-7 text-xs gap-1 text-white"
              style={{ backgroundColor: '#003366' }}
            >
              <Save size={12} />
              {updateProfile.isPending ? 'Guardando...' : 'Guardar'}
            </Button>
          </div>
        )}
      </div>

      <div className="p-5 space-y-1">
        {/* Success toast */}
        {saveSuccess && (
          <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-lg px-3 py-2.5 mb-3">
            <CheckCircle size={14} className="text-green-600" />
            <p className="text-green-700 text-sm font-medium">Perfil actualizado correctamente</p>
          </div>
        )}
        {saveError && (
          <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2.5 mb-3">
            <AlertCircle size={14} className="text-red-500 flex-shrink-0 mt-0.5" />
            <p className="text-red-600 text-sm">{saveError}</p>
          </div>
        )}

        {/* Read-only fields */}
        <InfoRow icon={User} label="Nombre Completo" value={p.full_name} />
        <InfoRow icon={User} label="Cédula de Identidad" value={p.ci} />
        <InfoRow icon={User} label="Género" value={p.gender} />
        <InfoRow icon={BookOpen} label="Nivel Académico" value={p.academic_level} />
        <InfoRow icon={BookOpen} label="Profesión" value={p.profession} />
        <InfoRow icon={BookOpen} label="Especialidad" value={p.specialty} />

        {/* Editable fields */}
        {!editMode ? (
          <>
            <InfoRow icon={Mail} label="Email" value={p.email} />
            <InfoRow icon={Phone} label="Teléfono" value={p.phone} />
            <InfoRow icon={CreditCard} label="Banco" value={p.bank} />
            <InfoRow icon={CreditCard} label="N° de Cuenta" value={p.account_number} />
          </>
        ) : (
          <div className="pt-2 space-y-3 border-t border-dashed border-gray-200 mt-1">
            <p className="text-xs text-gray-400 font-medium">Campos editables:</p>

            <div className="space-y-1.5">
              <Label className="text-xs text-gray-500">
                <Mail size={11} className="inline mr-1" />
                Email
              </Label>
              <Input
                type="email"
                value={editForm.email}
                onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))}
                placeholder="tu@email.com"
                className="h-9 text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs text-gray-500">
                <Phone size={11} className="inline mr-1" />
                Teléfono
              </Label>
              <Input
                type="text"
                value={editForm.phone}
                onChange={(e) => setEditForm((f) => ({ ...f, phone: e.target.value }))}
                placeholder="Ej: 70012345"
                className="h-9 text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs text-gray-500">
                <CreditCard size={11} className="inline mr-1" />
                Banco
              </Label>
              <Input
                type="text"
                value={editForm.bank}
                onChange={(e) => setEditForm((f) => ({ ...f, bank: e.target.value }))}
                placeholder="Ej: Banco Unión"
                className="h-9 text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs text-gray-500">
                <CreditCard size={11} className="inline mr-1" />
                Número de Cuenta
              </Label>
              <Input
                type="text"
                value={editForm.account_number}
                onChange={(e) => setEditForm((f) => ({ ...f, account_number: e.target.value }))}
                placeholder="Ej: 1234567890"
                className="h-9 text-sm"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Schedule summary card (links to dedicated SchedulePage) ─────────────────

function ScheduleSummaryCard() {
  const { data: schedule } = useMySchedule()

  return (
    <div className="card-3d overflow-hidden">
      <Link
        to="/portal/schedule"
        className="flex items-center justify-between p-5 group"
      >
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ background: 'linear-gradient(135deg, #003366 0%, #0066CC 100%)' }}
          >
            <Calendar size={18} className="text-white" />
          </div>
          <div>
            <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
              Mi Horario Semanal
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              {schedule
                ? `${schedule.designation_count} materia(s) · ${schedule.total_weekly_hours}h/semana`
                : 'Cargando...'}
            </p>
          </div>
        </div>
        <ChevronRight
          size={18}
          className="text-gray-400 group-hover:text-[#0066CC] transition-colors flex-shrink-0"
        />
      </Link>
    </div>
  )
}

// ─── Change password card ─────────────────────────────────────────────────────

function ChangePasswordCard() {
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
      setForm({ current: '', newPwd: '', confirm: '' })
      setTimeout(() => setSuccess(false), 4000)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: unknown } } }
      const detail = axiosErr?.response?.data?.detail
      if (typeof detail === 'string') {
        setError(detail)
      } else if (Array.isArray(detail)) {
        const msgs = (detail as Array<{ msg: string }>).map((d) => d.msg).join(' | ')
        setError(msgs)
      } else {
        setError('Contraseña actual incorrecta.')
      }
    }
  }

  return (
    <div className="card-3d-static overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
        <Lock size={16} style={{ color: '#003366' }} />
        <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
          Cambiar Contraseña
        </h3>
      </div>
      <div className="p-5">
        {success ? (
          <div className="flex items-center gap-2.5 bg-green-50 border border-green-200 rounded-lg px-4 py-3">
            <CheckCircle size={16} className="text-green-600" />
            <p className="text-green-700 font-medium text-sm">¡Contraseña actualizada correctamente!</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 max-w-sm">
            {/* Current password */}
            <div className="space-y-1.5">
              <Label className="text-sm">Contraseña actual *</Label>
              <div className="relative">
                <Input
                  type={showCurrent ? 'text' : 'password'}
                  value={form.current}
                  onChange={(e) => setForm((f) => ({ ...f, current: e.target.value }))}
                  placeholder="••••••••"
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowCurrent((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                  tabIndex={-1}
                >
                  {showCurrent ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {/* New password */}
            <div className="space-y-1.5">
              <Label className="text-sm">Nueva contraseña *</Label>
              <div className="relative">
                <Input
                  type={showNew ? 'text' : 'password'}
                  value={form.newPwd}
                  onChange={(e) => setForm((f) => ({ ...f, newPwd: e.target.value }))}
                  placeholder="Mínimo 8 caracteres"
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowNew((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                  tabIndex={-1}
                >
                  {showNew ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              <PasswordStrengthBar password={form.newPwd} />
            </div>

            {/* Confirm */}
            <div className="space-y-1.5">
              <Label className="text-sm">Confirmar nueva contraseña *</Label>
              <div className="relative">
                <Input
                  type={showConfirm ? 'text' : 'password'}
                  value={form.confirm}
                  onChange={(e) => setForm((f) => ({ ...f, confirm: e.target.value }))}
                  placeholder="••••••••"
                  className={`pr-10 ${form.confirm && !passwordsMatch ? 'border-red-300' : ''}`}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                  tabIndex={-1}
                >
                  {showConfirm ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              {form.confirm && !passwordsMatch && (
                <p className="text-red-500 text-xs">Las contraseñas no coinciden</p>
              )}
            </div>

            {/* Validation checklist */}
            {form.newPwd && (
              <div className="rounded-lg bg-gray-50 p-3 space-y-1.5">
                <p className="text-xs text-gray-400 font-medium mb-1">Requisitos:</p>
                <ValidationItem passes={checks.length} label="Mínimo 8 caracteres" />
                <ValidationItem passes={checks.upper} label="Al menos una mayúscula" />
                <ValidationItem passes={checks.lower} label="Al menos una minúscula" />
                <ValidationItem passes={checks.digit} label="Al menos un número" />
              </div>
            )}

            {error && (
              <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2.5">
                <AlertCircle size={14} className="text-red-500 flex-shrink-0 mt-0.5" />
                <p className="text-red-600 text-sm">{error}</p>
              </div>
            )}

            <Button
              type="submit"
              disabled={!canSubmit || changePwd.isPending}
              className="text-white disabled:opacity-40"
              style={{ backgroundColor: '#003366' }}
            >
              {changePwd.isPending ? 'Guardando...' : 'Cambiar Contraseña'}
            </Button>
          </form>
        )}
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function MyProfilePage() {
  const { user } = useAuth()
  const { data: profile, isLoading } = useMyProfile()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-2 border-[#003366]/30 border-t-[#003366] rounded-full animate-spin" />
      </div>
    )
  }

  const p = profile as ProfileData | undefined

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Profile header */}
      <div
        className="rounded-xl p-6 text-white"
        style={{ background: 'linear-gradient(135deg, #003366 0%, #0066CC 100%)' }}
      >
        <div className="flex items-center gap-5">
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center text-2xl font-black flex-shrink-0"
            style={{ backgroundColor: 'rgba(255,255,255,0.15)' }}
          >
            {user?.full_name?.charAt(0).toUpperCase() ?? 'D'}
          </div>
          <div>
            <h2 className="text-xl font-bold">{p?.full_name ?? user?.full_name}</h2>
            <p className="text-white/70 text-sm mt-0.5">CI: {p?.ci ?? user?.ci}</p>
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <Badge className="bg-white/20 text-white border-white/30 text-xs">Docente</Badge>
              {p?.designation_count != null && p.designation_count > 0 && (
                <span className="text-white/60 text-xs">
                  {p.designation_count}{' '}
                  {p.designation_count === 1 ? 'materia asignada' : 'materias asignadas'}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Personal data — editable */}
      {p && <PersonalDataCard p={p} />}

      {/* Weekly schedule — compact link to dedicated page */}
      <ScheduleSummaryCard />

      {/* Change Password */}
      <ChangePasswordCard />
    </div>
  )
}
