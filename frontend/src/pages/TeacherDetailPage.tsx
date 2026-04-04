import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  User,
  Pencil,
  Save,
  X,
  Trash2,
  Loader2,
  IdCard,
  GraduationCap,
  CreditCard,
} from 'lucide-react'
import { useTeacherDetail, useUpdateTeacher, useDeleteTeacher } from '@/api/hooks/useTeachers'
import { LoadingPage } from '@/components/shared/LoadingSpinner'
import { DataTable } from '@/components/shared/DataTable'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { Designation, ScheduleSlot } from '@/api/types'
import type { Column } from '@/components/shared/DataTable'

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

const designationColumns: Column<Designation>[] = [
  {
    key: 'subject',
    header: 'Materia',
    render: (item) => <span className="font-medium">{item.subject}</span>,
  },
  { key: 'semester', header: 'Semestre' },
  { key: 'group_code', header: 'Grupo' },
  {
    key: 'schedule_json',
    header: 'Horario',
    render: (item) => (
      <span className="text-xs text-gray-600">{formatSchedule(item.schedule_json)}</span>
    ),
  },
  {
    key: 'weekly_hours',
    header: 'Hs Semanales',
    render: (item) => {
      const h = item.weekly_hours ?? item.weekly_hours_calculated
      return h != null ? `${h}h` : '—'
    },
  },
  {
    key: 'monthly_hours',
    header: 'Hs Mensuales',
    render: (item) => (item.monthly_hours != null ? `${item.monthly_hours}h` : '—'),
  },
]

function InfoRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <dt className="text-xs font-medium text-gray-400 uppercase tracking-wide">{label}</dt>
      <dd className="mt-0.5 text-sm text-gray-800 font-medium">{value ?? '—'}</dd>
    </div>
  )
}

// ─── Delete Confirmation Dialog ───────────────────────────────────────────────
function DeleteConfirmDialog({
  ci,
  name,
  open,
  onClose,
}: {
  ci: string
  name: string
  open: boolean
  onClose: () => void
}) {
  const deleteTeacher = useDeleteTeacher()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  const handleDelete = async () => {
    setError(null)
    try {
      await deleteTeacher.mutateAsync(ci)
      navigate('/teachers')
    } catch {
      setError('No se pudo eliminar el docente. Intentá nuevamente.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="text-red-600 flex items-center gap-2">
            <Trash2 size={18} />
            Eliminar Docente
          </DialogTitle>
        </DialogHeader>
        <p className="text-sm text-gray-600">
          ¿Estás seguro de que querés eliminar a{' '}
          <strong className="text-gray-800">{name}</strong>{' '}
          (CI: {ci})?
          <br />
          <span className="text-red-500 text-xs mt-1 block">
            Esta acción eliminará también todas sus designaciones y registros de asistencia.
          </span>
        </p>
        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            {error}
          </p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            className="bg-red-600 hover:bg-red-700 text-white"
            onClick={handleDelete}
            disabled={deleteTeacher.isPending}
          >
            {deleteTeacher.isPending ? (
              <>
                <Loader2 size={14} className="animate-spin mr-2" />
                Eliminando...
              </>
            ) : (
              <>
                <Trash2 size={14} className="mr-2" />
                Eliminar
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
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
    <div className="space-y-1.5">
      <Label className="text-sm">{label}</Label>
      <Input
        type={type}
        value={value}
        onChange={(e) => onChange(field, e.target.value)}
        placeholder={placeholder}
      />
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export function TeacherDetailPage() {
  const { ci } = useParams<{ ci: string }>()
  const navigate = useNavigate()
  const { data: teacher, isLoading, error } = useTeacherDetail(ci)
  const updateTeacher = useUpdateTeacher()

  const [editMode, setEditMode] = useState(false)
  const [editForm, setEditForm] = useState<Record<string, string>>({})
  const [editError, setEditError] = useState<string | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)

  useEffect(() => {
    if (teacher) {
      setEditForm({
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
      })
    }
  }, [teacher])

  const handleFieldChange = (field: string, value: string) => {
    setEditForm((f) => ({ ...f, [field]: value }))
  }

  const handleSave = async () => {
    if (!ci) return
    setEditError(null)
    try {
      // Build the update payload — send empty strings as null to the API
      const payload: Record<string, string | null> = {}
      for (const [k, v] of Object.entries(editForm)) {
        payload[k] = v === '' ? null : v
      }
      await updateTeacher.mutateAsync({ ci, data: payload })
      setEditMode(false)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setEditError(axiosErr?.response?.data?.detail ?? 'No se pudo actualizar el docente.')
    }
  }

  const handleCancelEdit = () => {
    if (teacher) {
      setEditForm({
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
      })
    }
    setEditError(null)
    setEditMode(false)
  }

  if (isLoading) return <LoadingPage />

  if (error || !teacher) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-400 font-medium">No se encontró el docente con C.I.: {ci}</p>
        <Button
          variant="outline"
          className="mt-4"
          onClick={() => navigate('/teachers')}
        >
          <ArrowLeft size={14} className="mr-2" />
          Volver a Docentes
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header actions */}
      <div className="flex items-center justify-between">
        <Button variant="outline" onClick={() => navigate('/teachers')} className="gap-2">
          <ArrowLeft size={14} />
          Volver a Docentes
        </Button>

        <div className="flex items-center gap-2">
          {editMode ? (
            <>
              <Button
                variant="outline"
                onClick={handleCancelEdit}
                className="gap-2 text-gray-600"
              >
                <X size={14} />
                Cancelar
              </Button>
              <Button
                onClick={handleSave}
                disabled={updateTeacher.isPending}
                style={{ backgroundColor: '#003366' }}
                className="gap-2 text-white"
              >
                {updateTeacher.isPending ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    Guardando...
                  </>
                ) : (
                  <>
                    <Save size={14} />
                    Guardar Cambios
                  </>
                )}
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                onClick={() => setEditMode(true)}
                className="gap-2"
              >
                <Pencil size={14} />
                Editar
              </Button>
              <Button
                variant="outline"
                onClick={() => setDeleteOpen(true)}
                className="gap-2 text-red-600 border-red-200 hover:bg-red-50"
              >
                <Trash2 size={14} />
                Eliminar
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Teacher Info Card */}
      <div className="card-3d-static overflow-hidden animate-fade-in-up stagger-1">
        {/* Gradient header strip */}
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
              <User size={26} className="text-white" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">
                {editMode ? editForm.full_name || teacher.full_name : teacher.full_name}
              </h2>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-white/70 text-sm">C.I.: {teacher.ci}</span>
                {!editMode && teacher.external_permanent && (
                  <Badge className="bg-white/20 text-white border-white/30 text-xs">
                    {teacher.external_permanent === 'EXTERNO' ? 'Externo' : 'Permanente'}
                  </Badge>
                )}
                {!editMode && teacher.gender && (
                  <Badge className="bg-white/20 text-white border-white/30 text-xs">
                    {teacher.gender}
                  </Badge>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="px-6 py-5 space-y-6">
          {editError && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {editError}
            </p>
          )}

          {editMode ? (
            <>
              {/* Edit: Identificación */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <IdCard size={14} className="text-gray-400" />
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Identificación
                  </p>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
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
                  <IdCard size={14} className="text-gray-400" />
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Datos Personales
                  </p>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
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
                  <div className="space-y-1.5">
                    <Label className="text-sm">Género</Label>
                    <Select
                      value={editForm.gender}
                      onValueChange={(v) => handleFieldChange('gender', v)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Seleccionar..." />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="M">Masculino</SelectItem>
                        <SelectItem value="F">Femenino</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-sm">Tipo</Label>
                    <Select
                      value={editForm.external_permanent}
                      onValueChange={(v) => handleFieldChange('external_permanent', v)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Seleccionar..." />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="EXTERNO">Externo</SelectItem>
                        <SelectItem value="PERMANENTE">Permanente</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>

              {/* Edit: Datos Académicos */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <GraduationCap size={14} className="text-gray-400" />
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Datos Académicos
                  </p>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  <div className="space-y-1.5">
                    <Label className="text-sm">Nivel Académico</Label>
                    <Select
                      value={editForm.academic_level}
                      onValueChange={(v) => handleFieldChange('academic_level', v)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Seleccionar..." />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Licenciatura">Licenciatura</SelectItem>
                        <SelectItem value="Maestría">Maestría</SelectItem>
                        <SelectItem value="Doctorado">Doctorado</SelectItem>
                        <SelectItem value="Especialidad">Especialidad</SelectItem>
                        <SelectItem value="Técnico Superior">Técnico Superior</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
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
                  <CreditCard size={14} className="text-gray-400" />
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Datos Bancarios
                  </p>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
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
            <dl className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              <InfoRow label="Correo Electrónico" value={teacher.email} />
              <InfoRow label="Teléfono" value={teacher.phone} />
              <InfoRow label="Género" value={teacher.gender} />
              <InfoRow label="Tipo" value={teacher.external_permanent} />
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
      </div>

      {/* Attendance Summary */}
      {teacher.attendance_summary && (
        <Card className="animate-fade-in-up stagger-2">
          <CardHeader>
            <CardTitle className="text-base" style={{ color: '#003366' }}>
              Resumen de Asistencia
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-gray-800">
                  {teacher.attendance_summary.total_records}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">Total Registros</p>
              </div>
              <div className="text-center p-3 bg-green-50 rounded-lg">
                <p className="text-2xl font-bold text-green-700">
                  {teacher.attendance_summary.attended}
                </p>
                <p className="text-xs text-green-500 mt-0.5">Asistencias</p>
              </div>
              <div className="text-center p-3 bg-yellow-50 rounded-lg">
                <p className="text-2xl font-bold text-yellow-700">
                  {teacher.attendance_summary.late}
                </p>
                <p className="text-xs text-yellow-500 mt-0.5">Tardanzas</p>
              </div>
              <div className="text-center p-3 bg-red-50 rounded-lg">
                <p className="text-2xl font-bold text-red-700">
                  {teacher.attendance_summary.absent}
                </p>
                <p className="text-xs text-red-500 mt-0.5">Ausencias</p>
              </div>
              <div className="text-center p-3 bg-orange-50 rounded-lg">
                <p className="text-2xl font-bold text-orange-700">
                  {teacher.attendance_summary.no_exit}
                </p>
                <p className="text-xs text-orange-500 mt-0.5">Sin Salida</p>
              </div>
            </div>
            {teacher.attendance_summary.total_academic_hours > 0 && (
              <p className="text-sm text-gray-500 mt-3">
                Total horas académicas:{' '}
                <strong>{teacher.attendance_summary.total_academic_hours}h</strong>
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Designations */}
      <Card className="animate-fade-in-up stagger-3">
        <CardHeader>
          <CardTitle className="text-base" style={{ color: '#003366' }}>
            Designaciones ({teacher.designations.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {teacher.designations.length === 0 ? (
            <p className="text-gray-400 text-sm text-center py-8">
              Este docente no tiene designaciones registradas
            </p>
          ) : (
            <DataTable
              columns={designationColumns}
              data={teacher.designations}
              emptyMessage="Sin designaciones"
            />
          )}
        </CardContent>
      </Card>

      {/* Delete confirmation dialog */}
      <DeleteConfirmDialog
        ci={teacher.ci}
        name={teacher.full_name}
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
      />
    </div>
  )
}
