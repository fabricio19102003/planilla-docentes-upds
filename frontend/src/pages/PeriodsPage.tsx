import { useState } from 'react'
import {
  Calendar,
  Plus,
  Edit2,
  Trash2,
  Loader2,
  AlertTriangle,
  Clock,
  Users,
  ChevronDown,
  ChevronUp,
  Play,
  Square,
  ArrowLeft,
} from 'lucide-react'
import {
  usePeriods,
  useCreatePeriod,
  useUpdatePeriod,
  useActivatePeriod,
  useClosePeriod,
  useShifts,
  useGroups,
  useCreateGroup,
  useUpdateGroup,
  useDeleteGroup,
  useCareers,
  useCareer,
} from '@/api/hooks/useScheduling'
import type { AcademicPeriod, Shift, Group } from '@/api/hooks/useScheduling'
import { LoadingPage } from '@/components/shared/LoadingSpinner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

// ─── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: AcademicPeriod['status'] }) {
  const config = {
    planning: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'Planificacion' },
    active: { bg: 'bg-green-100', text: 'text-green-700', label: 'Activo' },
    closed: { bg: 'bg-gray-100', text: 'text-gray-600', label: 'Cerrado' },
  }
  const c = config[status]
  return (
    <span className={`text-xs px-2 py-0.5 ${c.bg} ${c.text} rounded-full font-medium`}>
      {c.label}
    </span>
  )
}

// ─── Create Period Dialog ─────────────────────────────────────────────────────

function CreatePeriodDialog({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const createPeriod = useCreatePeriod()
  const currentYear = new Date().getFullYear()
  const [form, setForm] = useState({
    code: '',
    name: '',
    year: String(currentYear),
    semester_number: '1',
    start_date: '',
    end_date: '',
  })
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.code.trim() || !form.name.trim() || !form.start_date || !form.end_date) {
      setError('Todos los campos marcados con * son obligatorios.')
      return
    }
    const codePattern = /^(I|II)\/\d{4}$/
    if (!codePattern.test(form.code.trim())) {
      setError('El codigo debe tener formato I/YYYY o II/YYYY.')
      return
    }
    setError(null)
    try {
      await createPeriod.mutateAsync({
        code: form.code.trim(),
        name: form.name.trim(),
        year: Number(form.year),
        semester_number: Number(form.semester_number),
        start_date: form.start_date,
        end_date: form.end_date,
      })
      setForm({
        code: '',
        name: '',
        year: String(currentYear),
        semester_number: '1',
        start_date: '',
        end_date: '',
      })
      onClose()
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr?.response?.data?.detail ?? 'No se pudo crear el periodo.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg p-0 overflow-hidden">
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <Calendar size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Nuevo Periodo Academico</h2>
              <p className="text-white/60 text-sm">Configurar un nuevo periodo</p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Codigo *</Label>
              <Input
                value={form.code}
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
                placeholder="I/2026"
              />
              <p className="text-xs text-gray-400">Formato: I/YYYY o II/YYYY</p>
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Nombre *</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Primer Semestre 2026"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Año *</Label>
              <Input
                type="number"
                min="2020"
                max="2100"
                value={form.year}
                onChange={(e) => setForm((f) => ({ ...f, year: e.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Semestre *</Label>
              <Select
                value={form.semester_number}
                onValueChange={(v) => setForm((f) => ({ ...f, semester_number: v }))}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">1 - Primer semestre</SelectItem>
                  <SelectItem value="2">2 - Segundo semestre</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Fecha inicio *</Label>
              <Input
                type="date"
                value={form.start_date}
                onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Fecha fin *</Label>
              <Input
                type="date"
                value={form.end_date}
                onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))}
              />
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
              <AlertTriangle size={14} />
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={createPeriod.isPending}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {createPeriod.isPending && <Loader2 size={16} className="animate-spin mr-1" />}
              Crear Periodo
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ─── Edit Period Dialog ───────────────────────────────────────────────────────

function EditPeriodDialog({
  open,
  onClose,
  period,
}: {
  open: boolean
  onClose: () => void
  period: AcademicPeriod
}) {
  const updatePeriod = useUpdatePeriod()
  const [form, setForm] = useState({
    name: period.name,
    start_date: period.start_date,
    end_date: period.end_date,
  })
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim()) {
      setError('El nombre es obligatorio.')
      return
    }
    setError(null)
    try {
      await updatePeriod.mutateAsync({
        id: period.id,
        name: form.name.trim(),
        start_date: form.start_date,
        end_date: form.end_date,
      })
      onClose()
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr?.response?.data?.detail ?? 'No se pudo actualizar el periodo.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg p-0 overflow-hidden">
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <Edit2 size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Editar Periodo</h2>
              <p className="text-white/60 text-sm">{period.code}</p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="space-y-1.5">
            <Label className="text-sm">Nombre *</Label>
            <Input
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Fecha inicio</Label>
              <Input
                type="date"
                value={form.start_date}
                onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Fecha fin</Label>
              <Input
                type="date"
                value={form.end_date}
                onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))}
              />
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
              <AlertTriangle size={14} />
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={updatePeriod.isPending}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {updatePeriod.isPending && <Loader2 size={16} className="animate-spin mr-1" />}
              Guardar
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ─── Create Group Dialog ──────────────────────────────────────────────────────

function CreateGroupDialog({
  open,
  onClose,
  periodId,
  shifts,
  semesters,
  existingGroups,
}: {
  open: boolean
  onClose: () => void
  periodId: number
  shifts: Shift[]
  semesters: { id: number; number: number; name: string }[]
  existingGroups: Group[]
}) {
  const createGroup = useCreateGroup()
  const [form, setForm] = useState({
    semester_id: '',
    shift_id: '',
    number: '',
    is_special: false,
    student_count: '',
  })
  const [error, setError] = useState<string | null>(null)

  // Auto-suggest next group number when shift changes
  const handleShiftChange = (shiftId: string) => {
    const semId = Number(form.semester_id)
    const sId = Number(shiftId)
    if (semId > 0 && sId > 0) {
      const existing = existingGroups.filter(
        (g) => g.semester_id === semId && g.shift_id === sId,
      )
      const maxNum = existing.reduce((max, g) => Math.max(max, g.number), 0)
      setForm((f) => ({ ...f, shift_id: shiftId, number: String(maxNum + 1) }))
    } else {
      setForm((f) => ({ ...f, shift_id: shiftId }))
    }
  }

  const handleSemesterChange = (semesterId: string) => {
    const sId = Number(form.shift_id)
    const semId = Number(semesterId)
    if (semId > 0 && sId > 0) {
      const existing = existingGroups.filter(
        (g) => g.semester_id === semId && g.shift_id === sId,
      )
      const maxNum = existing.reduce((max, g) => Math.max(max, g.number), 0)
      setForm((f) => ({ ...f, semester_id: semesterId, number: String(maxNum + 1) }))
    } else {
      setForm((f) => ({ ...f, semester_id: semesterId }))
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.semester_id || !form.shift_id || !form.number) {
      setError('Semestre, turno y numero son obligatorios.')
      return
    }
    setError(null)
    try {
      await createGroup.mutateAsync({
        academic_period_id: periodId,
        semester_id: Number(form.semester_id),
        shift_id: Number(form.shift_id),
        number: Number(form.number),
        is_special: form.is_special,
        student_count: form.student_count ? Number(form.student_count) : undefined,
      })
      setForm({ semester_id: '', shift_id: '', number: '', is_special: false, student_count: '' })
      onClose()
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr?.response?.data?.detail ?? 'No se pudo crear el grupo.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg p-0 overflow-hidden">
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <Users size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Nuevo Grupo</h2>
              <p className="text-white/60 text-sm">Agregar grupo al periodo</p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="space-y-1.5">
            <Label className="text-sm">Semestre *</Label>
            <Select value={form.semester_id} onValueChange={handleSemesterChange}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Seleccionar semestre" />
              </SelectTrigger>
              <SelectContent>
                {semesters.map((sem) => (
                  <SelectItem key={sem.id} value={String(sem.id)}>
                    {sem.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Turno *</Label>
              <Select value={form.shift_id} onValueChange={handleShiftChange}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Seleccionar turno" />
                </SelectTrigger>
                <SelectContent>
                  {shifts.map((shift) => (
                    <SelectItem key={shift.id} value={String(shift.id)}>
                      {shift.name} ({shift.code})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Numero *</Label>
              <Input
                type="number"
                min="1"
                value={form.number}
                onChange={(e) => setForm((f) => ({ ...f, number: e.target.value }))}
                placeholder="1"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Cant. Estudiantes</Label>
              <Input
                type="number"
                min="0"
                value={form.student_count}
                onChange={(e) => setForm((f) => ({ ...f, student_count: e.target.value }))}
                placeholder="Opcional"
              />
            </div>
            <div className="flex items-end pb-1">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.is_special}
                  onChange={(e) => setForm((f) => ({ ...f, is_special: e.target.checked }))}
                  className="rounded border-gray-300"
                />
                <span className="text-sm text-gray-700">Grupo Especial (G.E.)</span>
              </label>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
              <AlertTriangle size={14} />
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={createGroup.isPending}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {createGroup.isPending && <Loader2 size={16} className="animate-spin mr-1" />}
              Agregar Grupo
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ─── Edit Group Dialog ────────────────────────────────────────────────────────

function EditGroupDialog({
  open,
  onClose,
  group,
}: {
  open: boolean
  onClose: () => void
  group: Group
}) {
  const updateGroup = useUpdateGroup()
  const [form, setForm] = useState({
    student_count: group.student_count !== null ? String(group.student_count) : '',
    is_active: group.is_active,
  })
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await updateGroup.mutateAsync({
        id: group.id,
        student_count: form.student_count ? Number(form.student_count) : undefined,
        is_active: form.is_active,
      })
      onClose()
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr?.response?.data?.detail ?? 'No se pudo actualizar el grupo.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-sm p-0 overflow-hidden">
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <Edit2 size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Editar Grupo</h2>
              <p className="text-white/60 text-sm">{group.code}</p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="space-y-1.5">
            <Label className="text-sm">Cant. Estudiantes</Label>
            <Input
              type="number"
              min="0"
              value={form.student_count}
              onChange={(e) => setForm((f) => ({ ...f, student_count: e.target.value }))}
              placeholder="Opcional"
            />
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
              className="rounded border-gray-300"
            />
            <span className="text-sm text-gray-700">Grupo activo</span>
          </label>

          {error && (
            <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
              <AlertTriangle size={14} />
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={updateGroup.isPending}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {updateGroup.isPending && <Loader2 size={16} className="animate-spin mr-1" />}
              Guardar
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ─── Shifts Reference Panel ───────────────────────────────────────────────────

function ShiftsPanel({ shifts }: { shifts: Shift[] }) {
  return (
    <div className="card-3d-static overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
        <Clock size={16} className="text-gray-500" />
        <h4 className="text-sm font-semibold" style={{ color: '#003366' }}>
          Turnos Disponibles
        </h4>
      </div>
      <div className="p-4">
        <div className="flex flex-wrap gap-3">
          {shifts
            .slice()
            .sort((a, b) => a.display_order - b.display_order)
            .map((shift) => (
              <div
                key={shift.id}
                className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2"
              >
                <span className="text-xs font-bold px-2 py-0.5 bg-[#003366] text-white rounded">
                  {shift.code}
                </span>
                <div>
                  <p className="text-sm font-medium text-gray-700">{shift.name}</p>
                  <p className="text-xs text-gray-500">
                    {shift.start_time.slice(0, 5)} - {shift.end_time.slice(0, 5)}
                  </p>
                </div>
              </div>
            ))}
        </div>
      </div>
    </div>
  )
}

// ─── Groups by Semester Section ───────────────────────────────────────────────

function GroupsBySemester({
  semesterName,
  semesterNumber,
  groups,
}: {
  semesterName: string
  semesterNumber: number
  groups: Group[]
}) {
  const [expanded, setExpanded] = useState(groups.length > 0)
  const deleteGroup = useDeleteGroup()
  const [editGroup, setEditGroup] = useState<Group | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const handleDelete = async (id: number) => {
    if (!window.confirm('Eliminar este grupo?')) return
    setDeletingId(id)
    try {
      await deleteGroup.mutateAsync(id)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#003366]/10 flex items-center justify-center">
            <span className="text-xs font-bold text-[#003366]">{semesterNumber}</span>
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-800">{semesterName}</p>
            <p className="text-xs text-gray-500">
              {groups.length} grupo{groups.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
        {expanded ? (
          <ChevronUp size={18} className="text-gray-400" />
        ) : (
          <ChevronDown size={18} className="text-gray-400" />
        )}
      </button>

      {expanded && (
        <div className="p-4">
          {groups.length === 0 ? (
            <div className="py-6 text-center">
              <Users size={28} className="mx-auto text-gray-300 mb-2" />
              <p className="text-sm text-gray-400">No hay grupos para este semestre</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {groups
                .slice()
                .sort((a, b) => {
                  if (a.shift_code !== b.shift_code) return a.shift_code.localeCompare(b.shift_code)
                  return a.number - b.number
                })
                .map((group) => (
                  <div
                    key={group.id}
                    className={`border rounded-lg p-3 ${
                      group.is_active
                        ? 'border-gray-200 bg-white'
                        : 'border-gray-200 bg-gray-50 opacity-60'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold font-mono text-[#003366]">
                          {group.code}
                        </span>
                        {group.is_special && (
                          <span className="text-[10px] px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded font-medium">
                            G.E.
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => setEditGroup(group)}
                          className="p-1 rounded-md hover:bg-blue-50 text-gray-400 hover:text-blue-600 transition-colors"
                          title="Editar"
                        >
                          <Edit2 size={13} />
                        </button>
                        <button
                          onClick={() => handleDelete(group.id)}
                          disabled={deletingId === group.id}
                          className="p-1 rounded-md hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors disabled:opacity-50"
                          title="Eliminar"
                        >
                          {deletingId === group.id ? (
                            <Loader2 size={13} className="animate-spin" />
                          ) : (
                            <Trash2 size={13} />
                          )}
                        </button>
                      </div>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-gray-500">
                        Turno: <span className="font-medium text-gray-700">{group.shift_name}</span>
                      </p>
                      {group.student_count !== null && (
                        <p className="text-xs text-gray-500">
                          Estudiantes:{' '}
                          <span className="font-medium text-gray-700">{group.student_count}</span>
                        </p>
                      )}
                    </div>
                    <div className="mt-2">
                      {group.is_active ? (
                        <span className="text-[10px] px-1.5 py-0.5 bg-green-100 text-green-700 rounded-full font-medium">
                          Activo
                        </span>
                      ) : (
                        <span className="text-[10px] px-1.5 py-0.5 bg-red-100 text-red-700 rounded-full font-medium">
                          Inactivo
                        </span>
                      )}
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>
      )}

      {editGroup && (
        <EditGroupDialog
          open={!!editGroup}
          onClose={() => setEditGroup(null)}
          group={editGroup}
        />
      )}
    </div>
  )
}

// ─── Period Detail View ───────────────────────────────────────────────────────

function PeriodDetailView({
  period,
  onBack,
}: {
  period: AcademicPeriod
  onBack: () => void
}) {
  const { data: shifts, isLoading: shiftsLoading } = useShifts()
  const { data: careers } = useCareers(true)
  const [editOpen, setEditOpen] = useState(false)
  const [createGroupOpen, setCreateGroupOpen] = useState(false)
  const activatePeriod = useActivatePeriod()
  const closePeriod = useClosePeriod()
  const [selectedCareerId, setSelectedCareerId] = useState<number | null>(null)

  // Auto-select first career
  const effectiveCareerId = selectedCareerId ?? careers?.[0]?.id ?? null
  const { data: careerDetail } = useCareer(effectiveCareerId ?? 0, !!effectiveCareerId)
  const { data: groups, isLoading: groupsLoading } = useGroups(period.id)

  const handleActivate = async () => {
    if (!window.confirm(`Activar el periodo "${period.name}"? Esto desactivara cualquier otro periodo activo.`))
      return
    await activatePeriod.mutateAsync(period.id)
  }

  const handleClose = async () => {
    if (!window.confirm(`Cerrar el periodo "${period.name}"? Esta accion no se puede deshacer.`))
      return
    await closePeriod.mutateAsync(period.id)
  }

  // Build semesters list from career detail
  const semesters = careerDetail?.semesters?.map((s) => ({
    id: s.id,
    number: s.number,
    name: s.name || `Semestre ${s.number}`,
  })) ?? []

  // Group the groups by semester
  const groupsBySemester = semesters.map((sem) => ({
    ...sem,
    groups: (groups ?? []).filter((g) => g.semester_id === sem.id),
  }))

  if (shiftsLoading) return <LoadingPage />

  return (
    <div className="space-y-6">
      {/* Back & Period header */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={onBack}
              className="flex items-center gap-1 text-sm text-[#0066CC] hover:underline font-medium"
            >
              <ArrowLeft size={14} />
              Periodos
            </button>
            <span className="text-gray-300">/</span>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold" style={{ color: '#003366' }}>
                  {period.name}
                </h2>
                <span className="text-xs font-mono px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
                  {period.code}
                </span>
                <StatusBadge status={period.status} />
              </div>
              <p className="text-sm text-gray-500 mt-0.5">
                {period.start_date} a {period.end_date} | Año {period.year}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {period.status === 'planning' && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleActivate}
                disabled={activatePeriod.isPending}
                className="gap-1 text-green-700 border-green-200 hover:bg-green-50"
              >
                {activatePeriod.isPending ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Play size={14} />
                )}
                Activar
              </Button>
            )}
            {period.status === 'active' && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleClose}
                disabled={closePeriod.isPending}
                className="gap-1 text-amber-700 border-amber-200 hover:bg-amber-50"
              >
                {closePeriod.isPending ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Square size={14} />
                )}
                Cerrar Periodo
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setEditOpen(true)}
              className="gap-1"
            >
              <Edit2 size={14} />
              Editar
            </Button>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card-3d-static p-4">
          <p className="text-xs text-gray-500 uppercase font-semibold tracking-wider">Estado</p>
          <div className="mt-2">
            <StatusBadge status={period.status} />
          </div>
        </div>
        <div className="card-3d-static p-4">
          <p className="text-xs text-gray-500 uppercase font-semibold tracking-wider">Grupos</p>
          <p className="text-2xl font-bold mt-1" style={{ color: '#003366' }}>
            {groups?.length ?? period.group_count}
          </p>
        </div>
        <div className="card-3d-static p-4">
          <p className="text-xs text-gray-500 uppercase font-semibold tracking-wider">Periodo</p>
          <p className="text-sm font-medium text-gray-700 mt-2">
            Semestre {period.semester_number} / {period.year}
          </p>
        </div>
      </div>

      {/* Shifts reference */}
      {shifts && shifts.length > 0 && <ShiftsPanel shifts={shifts} />}

      {/* Career selector + Groups */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
              Grupos del Periodo
            </h3>
            {careers && careers.length > 1 && (
              <Select
                value={String(effectiveCareerId ?? '')}
                onValueChange={(v) => setSelectedCareerId(Number(v))}
              >
                <SelectTrigger className="w-auto">
                  <SelectValue placeholder="Carrera" />
                </SelectTrigger>
                <SelectContent>
                  {careers.map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
          <Button
            size="sm"
            onClick={() => setCreateGroupOpen(true)}
            disabled={semesters.length === 0 || !shifts?.length}
            className="gap-1 text-white"
            style={{ backgroundColor: '#003366' }}
          >
            <Plus size={14} />
            Agregar Grupo
          </Button>
        </div>

        <div className="p-5 space-y-3">
          {groupsLoading ? (
            <LoadingPage />
          ) : semesters.length === 0 ? (
            <div className="py-12 text-center">
              <Users size={40} className="mx-auto text-gray-300 mb-3" />
              <p className="text-gray-400 font-medium">
                No hay carreras con semestres registrados.
              </p>
              <p className="text-sm text-gray-400 mt-1">
                Primero registra una carrera con semestres en la Malla Curricular.
              </p>
            </div>
          ) : (
            groupsBySemester.map((sem) => (
              <GroupsBySemester
                key={sem.id}
                semesterName={sem.name}
                semesterNumber={sem.number}
                groups={sem.groups}
              />
            ))
          )}
        </div>
      </div>

      {/* Dialogs */}
      {editOpen && (
        <EditPeriodDialog open={editOpen} onClose={() => setEditOpen(false)} period={period} />
      )}
      {createGroupOpen && shifts && (
        <CreateGroupDialog
          open={createGroupOpen}
          onClose={() => setCreateGroupOpen(false)}
          periodId={period.id}
          shifts={shifts}
          semesters={semesters}
          existingGroups={groups ?? []}
        />
      )}
    </div>
  )
}

// ─── Period Card ──────────────────────────────────────────────────────────────

function PeriodCard({
  period,
  onSelect,
}: {
  period: AcademicPeriod
  onSelect: (p: AcademicPeriod) => void
}) {
  return (
    <button
      onClick={() => onSelect(period)}
      className={`card-3d-static p-5 text-left hover:shadow-md transition-shadow w-full ${
        period.is_active ? 'ring-2 ring-green-400' : ''
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ backgroundColor: '#003366' }}
          >
            <Calendar size={20} className="text-white" />
          </div>
          <div>
            <p className="font-semibold text-gray-800">{period.name}</p>
            <p className="text-xs font-mono text-gray-500">{period.code}</p>
          </div>
        </div>
        <StatusBadge status={period.status} />
      </div>
      <div className="flex items-center gap-4 mt-4">
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <Calendar size={14} />
          <span>
            {period.start_date} — {period.end_date}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <Users size={14} />
          <span>
            {period.group_count} grupo{period.group_count !== 1 ? 's' : ''}
          </span>
        </div>
      </div>
      {period.is_active && (
        <div className="mt-3">
          <span className="text-[10px] px-2 py-0.5 bg-green-100 text-green-700 rounded-full font-bold uppercase tracking-wider">
            Periodo Activo
          </span>
        </div>
      )}
    </button>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function PeriodsPage() {
  const { data: periods, isLoading } = usePeriods()
  const [selectedPeriod, setSelectedPeriod] = useState<AcademicPeriod | null>(null)
  const [createOpen, setCreateOpen] = useState(false)

  // Period detail view
  if (selectedPeriod !== null) {
    return (
      <div className="space-y-6">
        {/* Page header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ backgroundColor: '#003366' }}
            >
              <Calendar size={22} className="text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold" style={{ color: '#003366' }}>
                Periodos Academicos
              </h1>
              <p className="text-sm text-gray-500">Gestion de periodos, turnos y grupos</p>
            </div>
          </div>
        </div>

        <PeriodDetailView
          period={selectedPeriod}
          onBack={() => setSelectedPeriod(null)}
        />
      </div>
    )
  }

  // Period list view
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ backgroundColor: '#003366' }}
          >
            <Calendar size={22} className="text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold" style={{ color: '#003366' }}>
              Periodos Academicos
            </h1>
            <p className="text-sm text-gray-500">
              Periodos, turnos y grupos academicos
            </p>
          </div>
        </div>
        <Button
          onClick={() => setCreateOpen(true)}
          className="gap-2 text-white"
          style={{ backgroundColor: '#003366' }}
        >
          <Plus size={16} />
          Nuevo Periodo
        </Button>
      </div>

      {/* Period list */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
            Periodos Registrados
          </h3>
          {periods && (
            <span className="text-sm text-gray-500 bg-gray-100 px-2.5 py-1 rounded-full font-medium">
              {periods.length} periodo{periods.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        <div className="p-5">
          {isLoading ? (
            <LoadingPage />
          ) : !periods?.length ? (
            <div className="py-16 text-center">
              <Calendar size={40} className="mx-auto text-gray-300 mb-3" />
              <p className="text-gray-400 font-medium">No hay periodos registrados</p>
              <p className="text-sm text-gray-400 mt-1">
                Crea un nuevo periodo academico para comenzar a gestionar grupos.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {periods
                .slice()
                .sort((a, b) => {
                  // Active first, then by year desc, then by semester_number desc
                  if (a.is_active !== b.is_active) return a.is_active ? -1 : 1
                  if (a.year !== b.year) return b.year - a.year
                  return b.semester_number - a.semester_number
                })
                .map((period) => (
                  <PeriodCard
                    key={period.id}
                    period={period}
                    onSelect={setSelectedPeriod}
                  />
                ))}
            </div>
          )}
        </div>
      </div>

      {createOpen && (
        <CreatePeriodDialog open={createOpen} onClose={() => setCreateOpen(false)} />
      )}
    </div>
  )
}
