import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  useMyProfile,
  useChangePassword,
  useUpdateProfile,
  useMySchedule,
  useUploadOwnProfilePhoto,
  useDeleteOwnProfilePhoto,
} from '@/api/hooks/useAuth'
import { useAuth } from '@/context/AuthContext'
import { TEACHER_TYPE_OPTIONS, teacherTypeLabel } from '@/domain/teacherTypes'
import type { TeacherType } from '@/domain/teacherTypes'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { TONE_CHIP } from '@/components/shared/tones'
import { cn } from '@/lib/utils'
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
  Camera,
  Upload,
  Trash2,
  ShieldCheck,
} from 'lucide-react'

// ─── Types ────────────────────────────────────────────────────────────────────

interface ProfileData {
  ci: string
  full_name: string
  email: string | null
  phone: string | null
  gender: string | null
  external_permanent: TeacherType | null
  academic_level: string | null
  profession: string | null
  specialty: string | null
  bank: string | null
  account_number: string | null
  avatar_url: string | null
  docente_can_edit_profile: boolean
  docente_can_edit_photo: boolean
  designation_count: number
  subject_count?: number
  group_count?: number
}

interface ProfileForm {
  email: string
  phone: string
  gender: string
  external_permanent: TeacherType | ''
  academic_level: string
  profession: string
  specialty: string
  bank: string
  account_number: string
}

function toProfileForm(profile: ProfileData): ProfileForm {
  return {
    email: profile.email ?? '',
    phone: profile.phone ?? '',
    gender: profile.gender ?? '',
    external_permanent: profile.external_permanent ?? '',
    academic_level: profile.academic_level ?? '',
    profession: profile.profession ?? '',
    specialty: profile.specialty ?? '',
    bank: profile.bank ?? '',
    account_number: profile.account_number ?? '',
  }
}

function nullableText(value: string): string | null {
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

const SELECT_EMPTY = '__empty__'

const GENDER_OPTIONS = ['Femenino', 'Masculino', 'Otro', 'Prefiero no indicar']
const EXTERNAL_PERMANENT_OPTIONS = TEACHER_TYPE_OPTIONS.map((option) => option.value)
const ACADEMIC_LEVEL_OPTIONS = ['Técnico Superior', 'Licenciatura', 'Especialidad', 'Maestría', 'Doctorado']

function assignmentLabel(subjectCount = 0, groupCount = 0): string {
  if (subjectCount <= 0 && groupCount <= 0) return 'Sin asignaciones activas'
  const subjects = `${subjectCount} ${subjectCount === 1 ? 'materia' : 'materias'}`
  const groups = `${groupCount} ${groupCount === 1 ? 'grupo' : 'grupos'}`
  return `${subjects} · ${groups} asignados`
}

function SelectField({
  id,
  label,
  value,
  options,
  onChange,
  invalid = false,
  errorId,
}: {
  id: string
  label: string
  value: string
  options: string[]
  onChange: (value: string) => void
  invalid?: boolean
  errorId?: string
}) {
  const normalizedOptions = value && !options.includes(value) ? [value, ...options] : options

  return (
    <Field>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Select
        value={value || SELECT_EMPTY}
        items={[
          { value: SELECT_EMPTY, label: 'Sin especificar' },
          ...normalizedOptions.map((option) => ({ value: option, label: option })),
        ]}
        onValueChange={(next) => onChange(next === SELECT_EMPTY || next == null ? '' : next)}
      >
        <SelectTrigger
          id={id}
          aria-invalid={invalid}
          aria-describedby={invalid ? errorId : undefined}
        >
          <SelectValue placeholder="Seleccionar" />
        </SelectTrigger>
        <SelectPopup>
          <SelectItem value={SELECT_EMPTY}>Sin especificar</SelectItem>
          {normalizedOptions.map((option) => (
            <SelectItem key={option} value={option}>
              {option}
            </SelectItem>
          ))}
        </SelectPopup>
      </Select>
    </Field>
  )
}

// ─── Shared display components ────────────────────────────────────────────────

function InfoRow({ icon: Icon, label, value }: { icon: typeof User; label: string; value: string | null }) {
  return (
    <div className="flex items-start gap-3 border-b py-2.5 last:border-0">
      <div className={cn('mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg', TONE_CHIP.primary)}>
        <Icon size={15} aria-hidden="true" />
      </div>
      <div className="min-w-0">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p className="mt-0.5 break-words text-sm font-medium text-foreground">{value || '—'}</p>
      </div>
    </div>
  )
}

// ─── Password strength bar ────────────────────────────────────────────────────

const STRENGTH_BAR = ['bg-destructive', 'bg-warning', 'bg-info', 'bg-success']
const STRENGTH_TEXT = [
  'text-destructive-foreground',
  'text-warning-foreground',
  'text-info-foreground',
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
    <div className="mt-1 space-y-1.5">
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
      <p className={cn('text-xs font-medium', STRENGTH_TEXT[Math.max(strength, 1) - 1])}>
        {labels[strength - 1] ?? ''}
      </p>
    </div>
  )
}

function ValidationItem({ passes, label }: { passes: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2">
      {passes ? (
        <CheckCircle2 size={13} className="shrink-0 text-success" aria-hidden="true" />
      ) : (
        <XCircle size={13} className="shrink-0 text-muted-foreground/50" aria-hidden="true" />
      )}
      <span className={cn('text-xs', passes ? 'text-success-foreground' : 'text-muted-foreground')}>{label}</span>
    </div>
  )
}

// ─── Editable personal data card ──────────────────────────────────────────────

function PersonalDataCard({ p, canEdit }: { p: ProfileData; canEdit: boolean }) {
  const updateProfile = useUpdateProfile()
  const [editMode, setEditMode] = useState(false)
  const [editFormOverride, setEditFormOverride] = useState<Partial<ProfileForm> | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const editForm = { ...toProfileForm(p), ...editFormOverride }

  const handleSave = async () => {
    setSaveError(null)
    try {
      await updateProfile.mutateAsync({
        email: nullableText(editForm.email),
        phone: nullableText(editForm.phone),
        gender: nullableText(editForm.gender),
        external_permanent: editForm.external_permanent || null,
        academic_level: nullableText(editForm.academic_level),
        profession: nullableText(editForm.profession),
        specialty: nullableText(editForm.specialty),
        bank: nullableText(editForm.bank),
        account_number: nullableText(editForm.account_number),
      })
      setEditFormOverride(null)
      setSaveSuccess(true)
      setEditMode(false)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setSaveError(axiosErr?.response?.data?.detail ?? 'Error al guardar los cambios')
    }
  }

  const handleCancel = () => {
    setEditFormOverride(null)
    setSaveError(null)
    setEditMode(false)
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b px-5 py-4">
        <User size={16} className="shrink-0 text-primary" aria-hidden="true" />
        <h3 className="grow whitespace-nowrap text-base font-semibold text-foreground">
          Datos Personales
        </h3>
        {!editMode ? (
          canEdit ? (
            <Button type="button" variant="ghost" size="sm" onClick={() => setEditMode(true)}>
              <Pencil size={12} aria-hidden="true" />
              Editar
            </Button>
          ) : (
            <StatusBadge tone="warning">Solo lectura</StatusBadge>
          )
        ) : (
          <div className="ml-auto flex items-center gap-1.5">
            <Button type="button" variant="ghost" size="sm" onClick={handleCancel}>
              <X size={12} aria-hidden="true" />
              Cancelar
            </Button>
            <Button size="sm" onClick={handleSave} disabled={updateProfile.isPending}>
              <Save size={12} aria-hidden="true" />
              {updateProfile.isPending ? 'Guardando...' : 'Guardar'}
            </Button>
          </div>
        )}
      </div>

      <div className="space-y-1 p-5">
        {!canEdit && (
          <Alert variant="warning" className="mb-3">
            <ShieldCheck aria-hidden="true" />
            <AlertDescription className="text-warning-foreground">
              La edición de datos está deshabilitada por administración. Podés revisar tu información y solicitar cambios por los canales institucionales.
            </AlertDescription>
          </Alert>
        )}
        {/* Success toast */}
        {saveSuccess && (
          <Alert variant="success" role="status" className="mb-3">
            <CheckCircle aria-hidden="true" />
            <AlertDescription className="font-medium text-success-foreground">Perfil actualizado correctamente</AlertDescription>
          </Alert>
        )}
        {saveError && (
          <Alert id="profile-save-error" variant="error" className="mb-3">
            <AlertCircle aria-hidden="true" />
            <AlertDescription className="text-destructive-foreground">{saveError}</AlertDescription>
          </Alert>
        )}

        {/* Read-only identity fields */}
        <InfoRow icon={User} label="Nombre Completo" value={p.full_name} />
        <InfoRow icon={User} label="Cédula de Identidad" value={p.ci} />

        {/* Editable fields */}
        {!editMode ? (
          <>
            <InfoRow icon={User} label="Género" value={p.gender} />
            <InfoRow icon={BookOpen} label="Nivel Académico" value={p.academic_level} />
            <InfoRow icon={BookOpen} label="Profesión" value={p.profession} />
            <InfoRow icon={BookOpen} label="Especialidad" value={p.specialty} />
            <InfoRow icon={User} label="Tipo docente" value={teacherTypeLabel(p.external_permanent)} />
            <InfoRow icon={Mail} label="Email" value={p.email} />
            <InfoRow icon={Phone} label="Teléfono" value={p.phone} />
            <InfoRow icon={CreditCard} label="Banco" value={p.bank} />
            <InfoRow icon={CreditCard} label="N° de Cuenta" value={p.account_number} />
          </>
        ) : (
          <div className="mt-3 rounded-xl bg-muted/40 p-4">
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-foreground">Actualizar perfil</p>
                <p className="mt-1 text-xs text-muted-foreground">Mantené tus datos personales y bancarios listos para contratos y pagos.</p>
              </div>
              <StatusBadge tone="primary">Editable</StatusBadge>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <SelectField
                id="profile-gender"
                label="Género"
                value={editForm.gender}
                options={GENDER_OPTIONS}
                onChange={(gender) => setEditFormOverride((f) => ({ ...f, gender }))}
                invalid={Boolean(saveError)}
                errorId="profile-save-error"
              />
              <SelectField
                id="profile-teacher-type"
                label="Tipo docente"
                value={editForm.external_permanent}
                options={EXTERNAL_PERMANENT_OPTIONS}
                onChange={(external_permanent) => setEditFormOverride((f) => ({ ...f, external_permanent: external_permanent as TeacherType }))}
                invalid={Boolean(saveError)}
                errorId="profile-save-error"
              />
              <SelectField
                id="profile-academic-level"
                label="Nivel académico"
                value={editForm.academic_level}
                options={ACADEMIC_LEVEL_OPTIONS}
                onChange={(academic_level) => setEditFormOverride((f) => ({ ...f, academic_level }))}
                invalid={Boolean(saveError)}
                errorId="profile-save-error"
              />
            </div>

            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="profile-profession">Profesión</FieldLabel>
                <Input
                  id="profile-profession"
                  type="text"
                  value={editForm.profession}
                  onChange={(e) => setEditFormOverride((f) => ({ ...f, profession: e.target.value }))}
                  placeholder="Ej: Médico Cirujano"
                  aria-invalid={Boolean(saveError)}
                  aria-describedby={saveError ? 'profile-save-error' : undefined}
                />
              </Field>

              <Field>
                <FieldLabel htmlFor="profile-specialty">Especialidad</FieldLabel>
                <Input
                  id="profile-specialty"
                  type="text"
                  value={editForm.specialty}
                  onChange={(e) => setEditFormOverride((f) => ({ ...f, specialty: e.target.value }))}
                  placeholder="Ej: Cirugía General"
                  aria-invalid={Boolean(saveError)}
                  aria-describedby={saveError ? 'profile-save-error' : undefined}
                />
              </Field>
            </div>

            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="profile-email">
                  <Mail size={11} aria-hidden="true" />
                  Email
                </FieldLabel>
                <Input
                  id="profile-email"
                  type="email"
                  value={editForm.email}
                  onChange={(e) => setEditFormOverride((f) => ({ ...f, email: e.target.value }))}
                  placeholder="tu@email.com"
                  aria-invalid={Boolean(saveError)}
                  aria-describedby={saveError ? 'profile-save-error' : undefined}
                />
              </Field>

              <Field>
                <FieldLabel htmlFor="profile-phone">
                  <Phone size={11} aria-hidden="true" />
                  Teléfono
                </FieldLabel>
                <Input
                  id="profile-phone"
                  type="text"
                  value={editForm.phone}
                  onChange={(e) => setEditFormOverride((f) => ({ ...f, phone: e.target.value }))}
                  placeholder="Ej: 70012345"
                  aria-invalid={Boolean(saveError)}
                  aria-describedby={saveError ? 'profile-save-error' : undefined}
                />
              </Field>

              <Field>
                <FieldLabel htmlFor="profile-bank">
                  <CreditCard size={11} aria-hidden="true" />
                  Banco
                </FieldLabel>
                <Input
                  id="profile-bank"
                  type="text"
                  value={editForm.bank}
                  onChange={(e) => setEditFormOverride((f) => ({ ...f, bank: e.target.value }))}
                  placeholder="Ej: Banco Unión"
                  aria-invalid={Boolean(saveError)}
                  aria-describedby={saveError ? 'profile-save-error' : undefined}
                />
              </Field>

              <Field>
                <FieldLabel htmlFor="profile-account-number">
                  <CreditCard size={11} aria-hidden="true" />
                  Número de Cuenta
                </FieldLabel>
                <Input
                  id="profile-account-number"
                  type="text"
                  value={editForm.account_number}
                  onChange={(e) => setEditFormOverride((f) => ({ ...f, account_number: e.target.value }))}
                  placeholder="Ej: 1234567890"
                  inputClassName="tabular-nums"
                  aria-invalid={Boolean(saveError)}
                  aria-describedby={saveError ? 'profile-save-error' : undefined}
                />
              </Field>
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}

// ─── Schedule summary card (links to dedicated SchedulePage) ─────────────────

function ScheduleSummaryCard() {
  const { data: schedule } = useMySchedule()

  return (
    <Card className="overflow-hidden">
      <Link
        to="/portal/schedule"
        className="group flex items-center justify-between rounded-[inherit] p-5 outline-none transition-colors hover:bg-accent/50 focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div className="flex items-center gap-3">
          <div className={cn('flex size-10 shrink-0 items-center justify-center rounded-lg', TONE_CHIP.primary)}>
            <Calendar size={18} aria-hidden="true" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-foreground">
              Mi Horario Semanal
            </h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {schedule
                ? `${assignmentLabel(schedule.subject_count, schedule.group_count)} · ${schedule.total_weekly_hours}h/semana`
                : 'Cargando...'}
            </p>
          </div>
        </div>
        <ChevronRight
          size={18}
          className="shrink-0 text-muted-foreground transition-colors group-hover:text-primary"
          aria-hidden="true"
        />
      </Link>
    </Card>
  )
}

function ProfilePhotoCard({ profile, initials }: { profile: ProfileData; initials: string }) {
  const uploadPhoto = useUploadOwnProfilePhoto()
  const deletePhoto = useDeleteOwnProfilePhoto()
  const { refreshUser } = useAuth()
  const inputRef = useRef<HTMLInputElement>(null)
  const [imageError, setImageError] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const canEditPhoto = profile.docente_can_edit_photo
  const avatarUrl = profile.avatar_url
  const showImage = Boolean(avatarUrl) && !imageError

  const handleUpload = async (file: File) => {
    setError(null)
    setMessage(null)
    try {
      await uploadPhoto.mutateAsync({ file })
      await refreshUser()
      setImageError(false)
      setMessage('Foto de perfil actualizada correctamente.')
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr?.response?.data?.detail ?? 'No se pudo actualizar la foto de perfil.')
    } finally {
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const handleDelete = async () => {
    setError(null)
    setMessage(null)
    try {
      await deletePhoto.mutateAsync()
      await refreshUser()
      setImageError(false)
      setMessage('Foto de perfil eliminada. Se mostrará el avatar con iniciales.')
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr?.response?.data?.detail ?? 'No se pudo eliminar la foto de perfil.')
    }
  }

  const busy = uploadPhoto.isPending || deletePhoto.isPending

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-2 border-b px-5 py-4">
        <Camera size={16} className="shrink-0 text-primary" aria-hidden="true" />
        <h3 className="flex-1 text-base font-semibold text-foreground">
          Foto de Perfil
        </h3>
        <StatusBadge tone={canEditPhoto ? 'primary' : 'warning'}>
          {canEditPhoto ? 'Editable' : 'Solo lectura'}
        </StatusBadge>
      </div>
      <div className="p-5">
        <div className="rounded-xl bg-muted/40 p-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <div className="flex size-24 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-primary text-3xl font-semibold text-primary-foreground ring-4 ring-background">
              {showImage ? (
                <img
                  src={avatarUrl ?? undefined}
                  alt={`Foto de perfil de ${profile.full_name}`}
                  className="h-full w-full object-cover"
                  onError={() => setImageError(true)}
                />
              ) : (
                <span>{initials}</span>
              )}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-foreground">Avatar institucional docente</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {canEditPhoto
                  ? 'Podés subir JPG, PNG o WEBP hasta 2 MB. Si no hay foto, el sistema usa tus iniciales.'
                  : 'La carga o eliminación de foto está deshabilitada por administración. Tu avatar seguirá usando la foto actual o iniciales.'}
              </p>
              {message && <p className="mt-2 text-sm font-medium text-success-foreground">{message}</p>}
              {error && <p className="mt-2 text-sm font-medium text-destructive-foreground">{error}</p>}
            </div>
          </div>

          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void handleUpload(file)
            }}
            disabled={!canEditPhoto || busy}
          />

          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              type="button"
              onClick={() => inputRef.current?.click()}
              disabled={!canEditPhoto || busy}
              className="gap-2"
            >
              <Upload size={14} aria-hidden="true" />
              {uploadPhoto.isPending ? 'Subiendo...' : avatarUrl ? 'Cambiar foto' : 'Subir foto'}
            </Button>
            <Button
              type="button"
              variant="destructive-outline"
              onClick={() => void handleDelete()}
              disabled={!canEditPhoto || busy || !avatarUrl}
              className="gap-2"
            >
              <Trash2 size={14} aria-hidden="true" />
              Eliminar foto
            </Button>
          </div>
        </div>
      </div>
    </Card>
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

  const eyeButtonClass =
    'absolute right-2 top-1/2 flex size-8 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-2 border-b px-5 py-4">
        <Lock size={16} className="shrink-0 text-primary" aria-hidden="true" />
        <h3 className="text-base font-semibold text-foreground">
          Cambiar Contraseña
        </h3>
      </div>
      <div className="p-5">
        {success ? (
          <Alert variant="success" role="status">
            <CheckCircle aria-hidden="true" />
            <AlertDescription className="font-medium text-success-foreground">¡Contraseña actualizada correctamente!</AlertDescription>
          </Alert>
        ) : (
          <form onSubmit={handleSubmit} className="max-w-sm space-y-4" autoComplete="off">
            {/* Current password */}
            <Field>
              <FieldLabel htmlFor="profile-current-password">Contraseña actual *</FieldLabel>
              <div className="relative w-full">
                <Input
                  id="profile-current-password"
                  type={showCurrent ? 'text' : 'password'}
                  value={form.current}
                  onChange={(e) => setForm((f) => ({ ...f, current: e.target.value }))}
                  placeholder=""
                  autoComplete="off"
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? 'profile-password-error' : undefined}
                  inputClassName="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowCurrent((v) => !v)}
                  className={eyeButtonClass}
                  aria-label={showCurrent ? 'Ocultar contraseña actual' : 'Mostrar contraseña actual'}
                >
                  {showCurrent ? <EyeOff size={15} aria-hidden="true" /> : <Eye size={15} aria-hidden="true" />}
                </button>
              </div>
            </Field>

            {/* New password */}
            <Field>
              <FieldLabel htmlFor="profile-new-password">Nueva contraseña *</FieldLabel>
              <div className="relative w-full">
                <Input
                  id="profile-new-password"
                  type={showNew ? 'text' : 'password'}
                  value={form.newPwd}
                  onChange={(e) => setForm((f) => ({ ...f, newPwd: e.target.value }))}
                  placeholder="Mínimo 8 caracteres"
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? 'profile-password-error' : undefined}
                  inputClassName="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowNew((v) => !v)}
                  className={eyeButtonClass}
                  aria-label={showNew ? 'Ocultar nueva contraseña' : 'Mostrar nueva contraseña'}
                >
                  {showNew ? <EyeOff size={15} aria-hidden="true" /> : <Eye size={15} aria-hidden="true" />}
                </button>
              </div>
              <PasswordStrengthBar password={form.newPwd} />
            </Field>

            {/* Confirm */}
            <Field>
              <FieldLabel htmlFor="profile-confirm-password">Confirmar nueva contraseña *</FieldLabel>
              <div className="relative w-full">
                <Input
                  id="profile-confirm-password"
                  type={showConfirm ? 'text' : 'password'}
                  value={form.confirm}
                  onChange={(e) => setForm((f) => ({ ...f, confirm: e.target.value }))}
                  placeholder="••••••••"
                  aria-invalid={Boolean((form.confirm && !passwordsMatch) || error)}
                  aria-describedby={form.confirm && !passwordsMatch ? 'profile-confirm-error' : error ? 'profile-password-error' : undefined}
                  inputClassName="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm((v) => !v)}
                  className={eyeButtonClass}
                  aria-label={showConfirm ? 'Ocultar confirmación de contraseña' : 'Mostrar confirmación de contraseña'}
                >
                  {showConfirm ? <EyeOff size={15} aria-hidden="true" /> : <Eye size={15} aria-hidden="true" />}
                </button>
              </div>
              {form.confirm && !passwordsMatch && (
                <p id="profile-confirm-error" role="alert" className="text-xs text-destructive-foreground">Las contraseñas no coinciden</p>
              )}
            </Field>

            {/* Validation checklist */}
            {form.newPwd && (
              <div className="space-y-1.5 rounded-lg bg-muted/50 p-3">
                <p className="mb-1 text-xs font-medium text-muted-foreground">Requisitos:</p>
                <ValidationItem passes={checks.length} label="Mínimo 8 caracteres" />
                <ValidationItem passes={checks.upper} label="Al menos una mayúscula" />
                <ValidationItem passes={checks.lower} label="Al menos una minúscula" />
                <ValidationItem passes={checks.digit} label="Al menos un número" />
              </div>
            )}

            {error && (
              <Alert id="profile-password-error" variant="error">
                <AlertCircle aria-hidden="true" />
                <AlertDescription className="text-destructive-foreground">{error}</AlertDescription>
              </Alert>
            )}

            <Button type="submit" disabled={!canSubmit || changePwd.isPending}>
              {changePwd.isPending ? 'Guardando...' : 'Cambiar Contraseña'}
            </Button>
          </form>
        )}
      </div>
    </Card>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function MyProfilePage() {
  const { user } = useAuth()
  const { data: profile, isLoading } = useMyProfile()
  const [failedHeroAvatarUrl, setFailedHeroAvatarUrl] = useState<string | null>(null)
  const p = profile as ProfileData | undefined
  const subjectCount = p?.subject_count ?? p?.designation_count ?? 0
  const groupCount = p?.group_count ?? p?.designation_count ?? 0
  const initials = (p?.full_name ?? user?.full_name ?? 'D')
    .split(' ')
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
  const showHeroImage = Boolean(p?.avatar_url) && failedHeroAvatarUrl !== p?.avatar_url

  if (isLoading) {
    return (
      <div className="max-w-2xl">
        <PageHeader title="Mi Perfil" description="Tus datos personales, tu foto y tu contraseña." />
        <div role="status" aria-busy="true" className="space-y-4">
          <span className="sr-only">Cargando perfil</span>
          <Skeleton className="h-28 w-full rounded-2xl" />
          <Skeleton className="h-72 w-full rounded-2xl" />
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl space-y-4 sm:space-y-6">
      <PageHeader
        title="Mi Perfil"
        description="Tus datos personales, tu foto y tu contraseña."
      />

      {/* Profile summary */}
      <Card className="p-4 sm:p-6">
        <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:gap-5">
          <div className="flex size-16 shrink-0 items-center justify-center overflow-hidden rounded-full bg-primary/10 text-2xl font-semibold text-primary ring-2 ring-border">
            {showHeroImage ? (
              <img
                src={p?.avatar_url ?? undefined}
                alt={`Foto de perfil de ${p?.full_name ?? user?.full_name ?? 'docente'}`}
                className="h-full w-full object-cover"
                onError={() => setFailedHeroAvatarUrl(p?.avatar_url ?? null)}
              />
            ) : (
              initials
            )}
          </div>
          <div className="min-w-0">
            <h3 className="break-words text-xl font-semibold tracking-tight text-foreground">{p?.full_name ?? user?.full_name}</h3>
            <p className="mt-0.5 text-sm text-muted-foreground">CI: <span className="tabular-nums">{p?.ci ?? user?.ci}</span></p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge variant="outline">Docente</Badge>
              <span className="text-xs text-muted-foreground">
                {assignmentLabel(subjectCount, groupCount)}
              </span>
            </div>
          </div>
        </div>
      </Card>

      {/* Personal data — editable */}
      {p && <PersonalDataCard p={p} canEdit={p.docente_can_edit_profile} />}

      {/* Profile photo permissions */}
      {p && <ProfilePhotoCard profile={p} initials={initials} />}

      {/* Weekly schedule — compact link to dedicated page */}
      <ScheduleSummaryCard />

      {/* Change Password */}
      <ChangePasswordCard />
    </div>
  )
}
