import { useRef, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Pencil,
  Save,
  X,
  Trash2,
  IdCard,
  GraduationCap,
  CreditCard,
  Camera,
  Upload,
  FileDown,
  AlertCircle,
  ClipboardList,
  CheckCircle2,
  Clock,
  XCircle,
  LogOut,
  UserX,
} from 'lucide-react'
import {
  useTeacherDetail,
  useUpdateTeacher,
  useDeleteTeacher,
  useUploadTeacherPhoto,
  useDeleteTeacherPhoto,
  downloadTeacherPhoto,
  downloadTeacherSchedule,
} from '@/api/hooks/useTeachers'
import { WhatsAppConsentCard } from '@/components/teachers/WhatsAppConsentCard'
import { TEACHER_TYPE_OPTIONS, teacherTypeLabel } from '@/domain/teacherTypes'
import { DataTable } from '@/components/shared/DataTable'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { EmptyState } from '@/components/shared/EmptyState'
import { ConfirmAlertDialog } from '@/components/shared/ConfirmAlertDialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectItem,
  SelectPopup,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ScheduleSlot, TeacherDetail, TeacherWorkload } from '@/api/types'
import type { Column } from '@/components/shared/DataTable'
import { apiErrorMessage } from '@/lib/userCredentials'

const GENDER_ITEMS = [
  { value: 'M', label: 'Masculino' },
  { value: 'F', label: 'Femenino' },
]

function formatSchedule(schedule: ScheduleSlot[]): string {
  if (!schedule || schedule.length === 0) return '—'
  return schedule
    .map((slot) => {
      const day = slot.day ?? slot.dia ?? ''
      const start = slot.start_time ?? slot.hora_inicio ?? ''
      const end = slot.end_time ?? slot.hora_fin ?? ''
      const hours = slot.hours_academicas ?? slot.horas_academicas ?? ''
      const parts = [day, start && end ? `${start}-${end}` : '', hours ? `${hours}h` : ''].filter(Boolean)
      return parts.join(' ')
    })
    .filter(Boolean)
    .join('; ')
}

const designationColumns: Column<TeacherWorkload>[] = [
  {
    key: 'subject',
    header: 'Materia',
    render: (item) => <span className="font-medium text-foreground">{item.subject}</span>,
  },
  { key: 'semester', header: 'Semestre' },
  { key: 'group_code', header: 'Grupo' },
  {
    key: 'source_kind',
    header: 'Fuente',
    render: (item) => item.source_kind === 'published' ? 'Publicado' : 'Legado',
  },
  {
    key: 'schedule_json',
    header: 'Horario',
    render: (item) => (
      <span className="text-xs text-muted-foreground">{formatSchedule(item.schedule_json)}</span>
    ),
  },
  {
    key: 'weekly_hours',
    header: 'Hs Semanales',
    align: 'right',
    render: (item) => {
      return `${item.weekly_hours}h`
    },
  },
  {
    key: 'monthly_hours',
    header: 'Hs Mensuales',
    align: 'right',
    render: (item) => (item.monthly_hours != null ? `${item.monthly_hours}h` : '—'),
  },
]

function InfoRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium text-foreground">{value ?? '—'}</dd>
    </div>
  )
}

function toEditForm(teacher: TeacherDetail): Record<string, string> {
  return {
    ci: teacher.ci ?? '',
    full_name: teacher.full_name ?? '',
    email: teacher.email ?? '',
    phone: teacher.phone ?? '',
    gender: teacher.gender ?? '',
    external_permanent: teacher.external_permanent ?? '',
    academic_level: teacher.academic_level ?? '',
    profession: teacher.profession ?? '',
    specialty: teacher.specialty ?? '',
    bank: teacher.bank ?? '',
    account_number: teacher.account_number ?? '',
    sap_code: teacher.sap_code ?? '',
    invoice_retention: teacher.invoice_retention ?? '',
  }
}

function TeacherPhotoControl({ teacher }: { teacher: TeacherDetail }) {
  const [confirmDeletePhoto, setConfirmDeletePhoto] = useState(false)
  const uploadPhoto = useUploadTeacherPhoto()
  const deletePhoto = useDeleteTeacherPhoto()
  const inputRef = useRef<HTMLInputElement>(null)
  const [imageError, setImageError] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isDownloading, setIsDownloading] = useState(false)
  const initials = teacher.full_name
    .split(' ')
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
  const showImage = Boolean(teacher.avatar_url) && !imageError
  const busy = uploadPhoto.isPending || deletePhoto.isPending || isDownloading

  const handleUpload = async (file: File) => {
    setMessage(null)
    setError(null)
    try {
      await uploadPhoto.mutateAsync({ ci: teacher.ci, file })
      setImageError(false)
      setMessage('Foto actualizada para este docente.')
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'No se pudo actualizar la foto del docente.'))
    } finally {
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const handleDelete = async () => {
    setMessage(null)
    setError(null)
    try {
      await deletePhoto.mutateAsync(teacher.ci)
      setImageError(false)
      setMessage('Foto eliminada. El docente verá sus iniciales como avatar.')
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'No se pudo eliminar la foto del docente.'))
    } finally {
      setConfirmDeletePhoto(false)
    }
  }

  const handleDownload = async () => {
    setMessage(null)
    setError(null)
    setIsDownloading(true)
    try {
      await downloadTeacherPhoto(teacher.ci)
    } catch {
      setError('No se pudo descargar la foto del docente.')
    } finally {
      setIsDownloading(false)
    }
  }

  return (
    <section aria-label="Foto institucional">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="flex size-32 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-primary/10 text-4xl font-black text-primary ring-1 ring-border">
          {showImage ? (
            <img
              src={teacher.avatar_url ?? undefined}
              alt={`Foto de perfil de ${teacher.full_name}`}
              className="h-full w-full object-cover"
              onError={() => setImageError(true)}
            />
          ) : (
            initials
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-foreground">
            <Camera size={15} aria-hidden="true" />
            <p className="text-sm font-semibold">Foto institucional</p>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">JPG, PNG o WEBP hasta 2 MB. El cambio impacta el portal y el encabezado del docente.</p>
          {message && <p role="status" aria-live="polite" className="mt-2 text-xs font-medium text-success-foreground">{message}</p>}
          {error && <p role="alert" className="mt-2 text-xs font-medium text-destructive-foreground">{error}</p>}
          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void handleUpload(file)
            }}
            disabled={busy}
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <Button type="button" variant="secondary" onClick={() => inputRef.current?.click()} disabled={busy}>
              <Upload aria-hidden="true" />
              {uploadPhoto.isPending ? 'Subiendo...' : teacher.avatar_url ? 'Cambiar foto' : 'Subir foto'}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => void handleDownload()}
              disabled={busy || !teacher.avatar_url}
            >
              <FileDown aria-hidden="true" />
              {isDownloading ? 'Descargando...' : 'Descargar foto'}
            </Button>
            <Button
              type="button"
              variant="destructive-outline"
              onClick={() => setConfirmDeletePhoto(true)}
              disabled={busy || !teacher.avatar_url}
            >
              <Trash2 aria-hidden="true" />
              Eliminar foto
            </Button>
          </div>
        </div>
      </div>

      <ConfirmAlertDialog
        summary={
          confirmDeletePhoto
            ? {
                title: 'Eliminar foto institucional',
                confirmLabel: 'Eliminar foto',
                tone: 'destructive',
                rows: [
                  { label: 'Docente', value: teacher.full_name },
                  { label: 'C.I.', value: teacher.ci },
                ],
                consequence: 'El portal y el encabezado del docente volverán a mostrar sus iniciales.',
              }
            : null
        }
        pending={deletePhoto.isPending}
        onConfirm={() => void handleDelete()}
        onCancel={() => setConfirmDeletePhoto(false)}
      />
    </section>
  )
}

// ─── Edit Form Field helper ───────────────────────────────────────────────────
function EditField({
  label,
  field,
  value,
  onChange,
  type = 'text',
  placeholder,
}: {
  label: string
  field: string
  value: string
  onChange: (field: string, value: string) => void
  type?: string
  placeholder?: string
}) {
  return (
    <Field>
      <FieldLabel>{label}</FieldLabel>
      <Input
        type={type}
        value={value}
        onChange={(e) => onChange(field, e.target.value)}
        placeholder={placeholder}
      />
    </Field>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export function TeacherDetailPage() {
  const { ci } = useParams<{ ci: string }>()
  const navigate = useNavigate()
  const { data: teacher, isLoading, error } = useTeacherDetail(ci)
  const updateTeacher = useUpdateTeacher()
  const deleteTeacher = useDeleteTeacher()

  const [editMode, setEditMode] = useState(false)
  const [editFormOverride, setEditFormOverride] = useState<Record<string, string> | null>(null)
  const [editError, setEditError] = useState<string | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [scheduleDownloading, setScheduleDownloading] = useState(false)
  const [scheduleDownloadError, setScheduleDownloadError] = useState<string | null>(null)
  const editForm = teacher ? (editFormOverride ?? toEditForm(teacher)) : {}

  const handleFieldChange = (field: string, value: string) => {
    if (!teacher) return
    setEditFormOverride((f) => ({ ...(f ?? toEditForm(teacher)), [field]: value }))
  }

  const handleSave = async () => {
    if (!ci) return
    setEditError(null)
    try {
      const payload: Record<string, string | null> = {}
      for (const [k, v] of Object.entries(editForm)) {
        payload[k] = v === '' ? null : v
      }
      await updateTeacher.mutateAsync({ ci, data: payload })
      setEditFormOverride(null)
      setEditMode(false)
      // If CI changed, redirect to the new URL
      if (editForm.ci && editForm.ci !== ci) {
        navigate(`/teachers/${editForm.ci}`, { replace: true })
      }
    } catch (err: unknown) {
      setEditError(apiErrorMessage(err, 'No se pudo actualizar el docente.'))
    }
  }

  const handleDeleteTeacher = async () => {
    if (!teacher) return
    setDeleteError(null)
    try {
      await deleteTeacher.mutateAsync(teacher.ci)
      navigate('/teachers')
    } catch {
      setDeleteError('No se pudo eliminar el docente. Intentá nuevamente.')
    }
  }

  const handleCancelEdit = () => {
    setEditFormOverride(null)
    setEditError(null)
    setEditMode(false)
  }

  const handleScheduleDownload = async () => {
    if (!teacher) return
    setScheduleDownloadError(null)
    setScheduleDownloading(true)
    try {
      await downloadTeacherSchedule(teacher.ci, teacher.full_name)
    } catch {
      setScheduleDownloadError('No se pudo descargar el horario del docente.')
    } finally {
      setScheduleDownloading(false)
    }
  }

  if (isLoading) {
    return (
      <div role="status" aria-live="polite" aria-label="Cargando docente" className="space-y-6">
        <Skeleton className="h-16 w-full max-w-md" />
        <Skeleton className="h-64 rounded-2xl" />
        <Skeleton className="h-48 rounded-2xl" />
      </div>
    )
  }

  if (error || !teacher) {
    return (
      <Card>
        <EmptyState
          icon={UserX}
          title={`No se encontró el docente con C.I.: ${ci}`}
          action={
            <Button variant="outline" onClick={() => navigate('/teachers')}>
              <ArrowLeft aria-hidden="true" />
              Volver a Docentes
            </Button>
          }
        />
      </Card>
    )
  }

  const attendance = teacher.attendance_summary

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumb={
          <Button variant="ghost" size="sm" onClick={() => navigate('/teachers')} className="-ml-2">
            <ArrowLeft aria-hidden="true" />
            Volver a Docentes
          </Button>
        }
        title={editMode ? editForm.full_name || teacher.full_name : teacher.full_name}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <span>C.I.: {teacher.ci}</span>
            {!editMode && teacher.external_permanent && (
              <StatusBadge tone="info">{teacherTypeLabel(teacher.external_permanent)}</StatusBadge>
            )}
            {!editMode && teacher.gender && <StatusBadge>{teacher.gender}</StatusBadge>}
          </span>
        }
        actions={
          editMode ? (
            <>
              <Button variant="outline" onClick={handleCancelEdit}>
                <X aria-hidden="true" />
                Cancelar
              </Button>
              <Button onClick={handleSave} loading={updateTeacher.isPending}>
                {updateTeacher.isPending ? (
                  'Guardando...'
                ) : (
                  <>
                    <Save aria-hidden="true" />
                    Guardar Cambios
                  </>
                )}
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={() => void handleScheduleDownload()} disabled={scheduleDownloading}>
                <FileDown aria-hidden="true" />
                {scheduleDownloading ? 'Generando...' : 'Descargar horario'}
              </Button>
              <Button variant="outline" onClick={() => setEditMode(true)}>
                <Pencil aria-hidden="true" />
                Editar
              </Button>
              <Button variant="destructive-outline" onClick={() => setDeleteOpen(true)}>
                <Trash2 aria-hidden="true" />
                Eliminar
              </Button>
            </>
          )
        }
      />

      {scheduleDownloadError && (
        <Alert variant="error">
          <AlertCircle aria-hidden="true" />
          <AlertDescription>{scheduleDownloadError}</AlertDescription>
        </Alert>
      )}

      {/* Teacher Info Card */}
      <Card className="divide-y">
        {!editMode && (
          <div className="p-6">
            <TeacherPhotoControl teacher={teacher} />
          </div>
        )}

        <div className="space-y-6 p-6">
          {editError && (
            <Alert variant="error">
              <AlertCircle aria-hidden="true" />
              <AlertDescription>{editError}</AlertDescription>
            </Alert>
          )}

          {editMode ? (
            <>
              {/* Edit: Identificación */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <IdCard size={14} className="text-muted-foreground" />
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Identificación
                  </p>
                </div>
                {editForm.ci && editForm.ci !== ci && (
                  <Alert variant="warning" className="mb-3">
                    <AlertCircle aria-hidden="true" />
                    <AlertDescription>
                      Al guardar, el docente ingresará al portal con el C.I. {editForm.ci}. Su contraseña no cambia.
                    </AlertDescription>
                  </Alert>
                )}
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
                  <EditField
                    label="C.I. *"
                    field="ci"
                    value={editForm.ci}
                    onChange={handleFieldChange}
                    placeholder="12345678"
                  />
                  <EditField
                    label="Nombre Completo *"
                    field="full_name"
                    value={editForm.full_name}
                    onChange={handleFieldChange}
                    placeholder="Juan Pérez García"
                  />
                </div>
              </div>

              {/* Edit: Datos Personales */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <IdCard size={14} className="text-muted-foreground" />
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Datos Personales
                  </p>
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
                  <EditField
                    label="Email"
                    field="email"
                    value={editForm.email}
                    onChange={handleFieldChange}
                    type="email"
                    placeholder="docente@upds.edu.bo"
                  />
                  <EditField
                    label="Teléfono"
                    field="phone"
                    value={editForm.phone}
                    onChange={handleFieldChange}
                    placeholder="70012345"
                  />
                  <Field>
                    <FieldLabel>Género</FieldLabel>
                    <Select
                      value={editForm.gender || null}
                      items={GENDER_ITEMS}
                      onValueChange={(v) => handleFieldChange('gender', v ?? '')}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Seleccionar..." />
                      </SelectTrigger>
                      <SelectPopup>
                        <SelectItem value="M">Masculino</SelectItem>
                        <SelectItem value="F">Femenino</SelectItem>
                      </SelectPopup>
                    </Select>
                  </Field>
                  <Field>
                    <FieldLabel>Tipo</FieldLabel>
                    <Select
                      value={editForm.external_permanent || null}
                      items={TEACHER_TYPE_OPTIONS}
                      onValueChange={(v) => handleFieldChange('external_permanent', v ?? '')}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Seleccionar..." />
                      </SelectTrigger>
                      <SelectPopup>
                        {TEACHER_TYPE_OPTIONS.map((option) => (
                          <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                        ))}
                      </SelectPopup>
                    </Select>
                  </Field>
                </div>
              </div>

              {/* Edit: Datos Académicos */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <GraduationCap size={14} className="text-muted-foreground" />
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Datos Académicos
                  </p>
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
                  <Field>
                    <FieldLabel>Nivel Académico</FieldLabel>
                    <Select
                      value={editForm.academic_level || null}
                      onValueChange={(v) => handleFieldChange('academic_level', v ?? '')}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Seleccionar..." />
                      </SelectTrigger>
                      <SelectPopup>
                        <SelectItem value="Licenciatura">Licenciatura</SelectItem>
                        <SelectItem value="Maestría">Maestría</SelectItem>
                        <SelectItem value="Doctorado">Doctorado</SelectItem>
                        <SelectItem value="Especialidad">Especialidad</SelectItem>
                        <SelectItem value="Técnico Superior">Técnico Superior</SelectItem>
                      </SelectPopup>
                    </Select>
                  </Field>
                  <EditField
                    label="Profesión"
                    field="profession"
                    value={editForm.profession}
                    onChange={handleFieldChange}
                    placeholder="Ej: Ingeniero de Sistemas"
                  />
                  <EditField
                    label="Especialidad"
                    field="specialty"
                    value={editForm.specialty}
                    onChange={handleFieldChange}
                    placeholder="Ej: Desarrollo de Software"
                  />
                  <EditField
                    label="Código SAP"
                    field="sap_code"
                    value={editForm.sap_code}
                    onChange={handleFieldChange}
                    placeholder="Ej: SAP-001"
                  />
                </div>
              </div>

              {/* Edit: Datos Bancarios */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <CreditCard size={14} className="text-muted-foreground" />
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Datos Bancarios
                  </p>
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
                  <EditField
                    label="Banco"
                    field="bank"
                    value={editForm.bank}
                    onChange={handleFieldChange}
                    placeholder="Ej: Banco Unión"
                  />
                  <EditField
                    label="Número de Cuenta"
                    field="account_number"
                    value={editForm.account_number}
                    onChange={handleFieldChange}
                    placeholder="Ej: 1234567890"
                  />
                  <EditField
                    label="Retención Factura"
                    field="invoice_retention"
                    value={editForm.invoice_retention}
                    onChange={handleFieldChange}
                    placeholder="Ej: IT, IUE"
                  />
                </div>
              </div>
            </>
          ) : (
            /* Read-only view */
            <dl className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
              <InfoRow label="Correo Electrónico" value={teacher.email} />
              <InfoRow label="Teléfono de contacto (no es consentimiento de WhatsApp)" value={teacher.phone} />
              <InfoRow label="Género" value={teacher.gender} />
              <InfoRow label="Tipo" value={teacherTypeLabel(teacher.external_permanent)} />
              <InfoRow label="Nivel Académico" value={teacher.academic_level} />
              <InfoRow label="Profesión" value={teacher.profession} />
              <InfoRow label="Especialidad" value={teacher.specialty} />
              <InfoRow label="Código SAP" value={teacher.sap_code} />
              <InfoRow label="Banco" value={teacher.bank} />
              <InfoRow label="Nro. de Cuenta" value={teacher.account_number} />
              <InfoRow label="Retención Factura" value={teacher.invoice_retention} />
            </dl>
          )}
        </div>
      </Card>

      <WhatsAppConsentCard ci={teacher.ci} />

      {/* Attendance Summary */}
      {attendance && (
        <section aria-label="Resumen de Asistencia" className="space-y-3">
          <h3 className="text-base font-semibold text-foreground">Resumen de Asistencia</h3>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 2xl:grid-cols-5">
            <StatCard icon={ClipboardList} title="Total Registros" value={attendance.total_records} tone="primary" />
            <StatCard icon={CheckCircle2} title="Asistencias" value={attendance.attended} tone="success" />
            <StatCard icon={Clock} title="Tardanzas" value={attendance.late} tone="warning" />
            <StatCard icon={XCircle} title="Ausencias" value={attendance.absent} tone="destructive" />
            <StatCard icon={LogOut} title="Sin Salida" value={attendance.no_exit} tone="neutral" />
          </div>
          {attendance.total_academic_hours > 0 && (
            <p className="text-sm text-muted-foreground">
              Total horas académicas: <strong className="tabular-nums text-foreground">{attendance.total_academic_hours}h</strong>
            </p>
          )}
        </section>
      )}

      {/* Designations */}
      <section aria-label="Designaciones" className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-semibold text-foreground">Designaciones ({teacher.designations.length})</h3>
          <Button variant="outline" size="sm" render={<Link to={`/designations?teacher=${encodeURIComponent(teacher.ci)}`} />}>
            Gestionar designaciones
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">Para crear, corregir horarios y fechas, o finalizar una materia de este docente, usá Gestionar designaciones.</p>
        <DataTable
          columns={designationColumns}
          data={teacher.designations}
          emptyMessage="Este docente no tiene designaciones registradas"
        />
      </section>

      <ConfirmAlertDialog
        summary={
          deleteOpen
            ? {
                title: 'Eliminar Docente',
                confirmLabel: 'Eliminar',
                tone: 'destructive',
                rows: [
                  { label: 'Docente', value: teacher.full_name },
                  { label: 'C.I.', value: teacher.ci },
                  { label: 'Designaciones', value: String(teacher.designations.length) },
                ],
                warning: 'Esta acción eliminará también todas sus designaciones y registros de asistencia.',
                consequence: 'No se puede deshacer.',
              }
            : null
        }
        pending={deleteTeacher.isPending}
        description={deleteError ?? '¿Estás seguro de que querés eliminar a este docente?'}
        onConfirm={() => void handleDeleteTeacher()}
        onCancel={() => {
          setDeleteOpen(false)
          setDeleteError(null)
        }}
      />
    </div>
  )
}
