import { useState, useMemo, useCallback, useEffect } from 'react'
import {
  Clock,
  Plus,
  Trash2,
  Loader2,
  AlertTriangle,
  CheckCircle,
  Users,
  Building2,
  Calendar,
  Search,
  ChevronRight,
  X,
} from 'lucide-react'
import {
  usePeriods,
  useActivePeriod,
  useRooms,
  useDesignationSlots,
  useRoomSlots,
  useCreateSlot,
  useDeleteSlot,
  useValidateSlot,
  useTeacherAvailability,
  useSetAvailability,
  usePeriodAvailabilities,
} from '@/api/hooks/useScheduling'
import type {
  Room,
  DesignationSlot,
  SlotConflict,
  TeacherAvailability,
  AvailabilitySlot,
} from '@/api/hooks/useScheduling'
import { useTeachers } from '@/api/hooks/useTeachers'
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

// ─── Constants ────────────────────────────────────────────────────────────────

const WEEKDAYS = [
  { value: 0, label: 'Lunes' },
  { value: 1, label: 'Martes' },
  { value: 2, label: 'Miércoles' },
  { value: 3, label: 'Jueves' },
  { value: 4, label: 'Viernes' },
  { value: 5, label: 'Sábado' },
]

const DAY_COLORS: Record<number, string> = {
  0: '#003366',
  1: '#0066CC',
  2: '#4DA8DA',
  3: '#16a34a',
  4: '#7c3aed',
  5: '#d97706',
}

type ViewMode = 'teacher' | 'room' | 'weekly'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function ErrorBanner({ error }: { error: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
      <AlertTriangle size={14} />
      {error}
    </div>
  )
}

interface AxiosErrorData {
  detail?: string
  blocked?: boolean
  conflicts?: SlotConflict[]
}

function getAxiosErrorResponse(err: unknown): { status?: number; data?: AxiosErrorData } | undefined {
  return (err as { response?: { status?: number; data?: AxiosErrorData } })?.response
}

function extractAxiosError(err: unknown, fallback: string): string {
  return getAxiosErrorResponse(err)?.data?.detail ?? fallback
}

function extractBlockedSlotPayload(err: unknown): AxiosErrorData | null {
  const response = getAxiosErrorResponse(err)
  const data = response?.data
  if (response?.status === 409 || data?.blocked) return data ?? {}
  return null
}

function timeToMinutes(time: string): number {
  const [h, m] = time.split(':').map(Number)
  return h * 60 + m
}

function minutesToTime(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

// ─── Conflict Display ─────────────────────────────────────────────────────────

function ConflictList({ conflicts }: { conflicts: SlotConflict[] }) {
  if (conflicts.length === 0) return null

  const hardConflicts = conflicts.filter((c) => c.severity === 'HARD')
  const softConflicts = conflicts.filter((c) => c.severity === 'SOFT')

  return (
    <div className="space-y-2">
      {hardConflicts.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-semibold text-red-600 uppercase tracking-wider">
            Conflictos Bloqueantes
          </p>
          {hardConflicts.map((c, i) => (
            <div
              key={i}
              className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 px-3 py-2 rounded-lg"
            >
              <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" />
              <div>
                <span className="font-medium">{c.type.replace(/_/g, ' ')}</span>
                <p className="text-xs text-red-600 mt-0.5">{c.message}</p>
              </div>
            </div>
          ))}
        </div>
      )}
      {softConflicts.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-semibold text-amber-600 uppercase tracking-wider">
            Advertencias
          </p>
          {softConflicts.map((c, i) => (
            <div
              key={i}
              className="flex items-start gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 px-3 py-2 rounded-lg"
            >
              <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" />
              <div>
                <span className="font-medium">{c.type.replace(/_/g, ' ')}</span>
                <p className="text-xs text-amber-600 mt-0.5">{c.message}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Create Slot Dialog ───────────────────────────────────────────────────────

interface CreateSlotDialogProps {
  open: boolean
  onClose: () => void
  rooms: Room[]
  defaultDay?: number
  defaultTime?: string
  defaultRoomId?: number
  designationId?: number
}

function CreateSlotDialog({
  open,
  onClose,
  rooms,
  defaultDay,
  defaultTime,
  defaultRoomId,
  designationId,
}: CreateSlotDialogProps) {
  const createSlot = useCreateSlot()
  const validateSlot = useValidateSlot()

  const [form, setForm] = useState({
    designation_id: designationId ? String(designationId) : '',
    day_of_week: defaultDay !== undefined ? String(defaultDay) : '',
    start_time: defaultTime ?? '',
    end_time: defaultTime ? minutesToTime(timeToMinutes(defaultTime) + 90) : '',
    room_id: defaultRoomId ? String(defaultRoomId) : '',
  })
  const [conflicts, setConflicts] = useState<SlotConflict[]>([])
  const [validated, setValidated] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const hasHardConflicts = conflicts.some((c) => c.severity === 'HARD')

  const handleValidate = async () => {
    if (!form.designation_id || form.day_of_week === '' || !form.start_time || !form.end_time) {
      setError('Completá designación, día, hora inicio y hora fin.')
      return
    }
    setError(null)
    try {
      const result = await validateSlot.mutateAsync({
        designation_id: Number(form.designation_id),
        day_of_week: Number(form.day_of_week),
        start_time: form.start_time,
        end_time: form.end_time,
        room_id: form.room_id ? Number(form.room_id) : undefined,
      })
      setConflicts(result)
      setValidated(true)
    } catch (err) {
      setError(extractAxiosError(err, 'Error al validar el slot.'))
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.designation_id || form.day_of_week === '' || !form.start_time || !form.end_time) {
      setError('Completá designación, día, hora inicio y hora fin.')
      return
    }
    if (!validated) {
      setError('Validá el slot antes de guardar.')
      return
    }
    if (hasHardConflicts) {
      setError('No se puede guardar con conflictos bloqueantes.')
      return
    }
    setError(null)
    try {
      const result = await createSlot.mutateAsync({
        designation_id: Number(form.designation_id),
        day_of_week: Number(form.day_of_week),
        start_time: form.start_time,
        end_time: form.end_time,
        room_id: form.room_id ? Number(form.room_id) : undefined,
      })
      if (result?.blocked) {
        setConflicts(result.conflicts ?? [])
        setValidated(true)
        setError('El backend bloqueó el slot por conflictos. Revisá y volvé a validar.')
        return
      }
      onClose()
    } catch (err) {
      const blockedPayload = extractBlockedSlotPayload(err)
      if (blockedPayload) {
        if (Array.isArray(blockedPayload.conflicts)) {
          setConflicts(blockedPayload.conflicts)
        }
        setValidated(true)
        setError(
          blockedPayload.detail ??
            'El backend bloqueó el slot por conflictos. Revisá los detalles y volvé a validar.'
        )
        return
      }
      setError(extractAxiosError(err, 'No se pudo crear el slot.'))
    }
  }

  const resetValidation = () => {
    setValidated(false)
    setConflicts([])
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg p-0 overflow-hidden max-h-[90vh] overflow-y-auto">
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <Plus size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Agregar Slot</h2>
              <p className="text-white/60 text-sm">Asignar horario a una designación</p>
            </div>
          </div>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="space-y-1.5">
            <Label className="text-sm">ID Designación *</Label>
            <Input
              type="number"
              value={form.designation_id}
              onChange={(e) => {
                setForm((f) => ({ ...f, designation_id: e.target.value }))
                resetValidation()
              }}
              placeholder="Ej: 142"
            />
            <p className="text-xs text-gray-400">
              ID numérico de la designación existente
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Día *</Label>
              <Select
                value={form.day_of_week}
                onValueChange={(v) => {
                  setForm((f) => ({ ...f, day_of_week: v }))
                  resetValidation()
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Seleccionar día" />
                </SelectTrigger>
                <SelectContent>
                  {WEEKDAYS.map((d) => (
                    <SelectItem key={d.value} value={String(d.value)}>
                      {d.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Sala (opcional)</Label>
              <Select
                value={form.room_id}
                onValueChange={(v) => {
                  setForm((f) => ({ ...f, room_id: v === '__none__' ? '' : v }))
                  resetValidation()
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Sin sala" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Sin sala</SelectItem>
                  {rooms
                    .filter((r) => r.is_active)
                    .map((r) => (
                      <SelectItem key={r.id} value={String(r.id)}>
                        {r.name} ({r.code})
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Hora Inicio *</Label>
              <Input
                type="time"
                value={form.start_time}
                onChange={(e) => {
                  setForm((f) => ({ ...f, start_time: e.target.value }))
                  resetValidation()
                }}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm">Hora Fin *</Label>
              <Input
                type="time"
                value={form.end_time}
                onChange={(e) => {
                  setForm((f) => ({ ...f, end_time: e.target.value }))
                  resetValidation()
                }}
              />
            </div>
          </div>

          {/* Validate button */}
          <Button
            type="button"
            variant="outline"
            onClick={handleValidate}
            disabled={validateSlot.isPending}
            className="w-full gap-2"
          >
            {validateSlot.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : validated ? (
              <CheckCircle size={14} className="text-green-600" />
            ) : (
              <Search size={14} />
            )}
            {validated ? 'Validado — Volver a validar' : 'Validar Conflictos'}
          </Button>

          {/* Conflicts display */}
          <ConflictList conflicts={conflicts} />
          {validated && conflicts.length === 0 && (
            <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 border border-green-200 px-3 py-2 rounded-lg">
              <CheckCircle size={14} />
              Sin conflictos detectados
            </div>
          )}

          {error && <ErrorBanner error={error} />}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={createSlot.isPending || !validated || hasHardConflicts}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {createSlot.isPending && <Loader2 size={16} className="animate-spin mr-1" />}
              Guardar Slot
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ─── Availability Dialog ──────────────────────────────────────────────────────

interface AvailabilityDialogProps {
  open: boolean
  onClose: () => void
  teacherCi: string
  teacherName: string
  periodId: number
  existing: TeacherAvailability | null | undefined
}

function AvailabilityDialog({
  open,
  onClose,
  teacherCi,
  teacherName,
  periodId,
  existing,
}: AvailabilityDialogProps) {
  const setAvailability = useSetAvailability()
  const [error, setError] = useState<string | null>(null)

  // Grid state: 6 days x time blocks (30min each from 06:00 to 22:00 = 32 blocks)
  const timeBlocks = useMemo(() => {
    const blocks: string[] = []
    for (let h = 6; h < 22; h++) {
      blocks.push(`${String(h).padStart(2, '0')}:00`)
      blocks.push(`${String(h).padStart(2, '0')}:30`)
    }
    return blocks
  }, [])

  // Initialize selected cells from existing availability
  const [selected, setSelected] = useState<Set<string>>(() => {
    const s = new Set<string>()
    if (existing?.slots) {
      for (const slot of existing.slots) {
        const startMin = timeToMinutes(slot.start_time)
        const endMin = timeToMinutes(slot.end_time)
        for (let m = startMin; m < endMin; m += 30) {
          s.add(`${slot.day_of_week}-${minutesToTime(m)}`)
        }
      }
    }
    return s
  })

  const [isDragging, setIsDragging] = useState(false)
  const [dragMode, setDragMode] = useState<'add' | 'remove'>('add')

  useEffect(() => {
    if (!open) return
    const next = new Set<string>()
    if (existing?.slots) {
      for (const slot of existing.slots) {
        const startMin = timeToMinutes(slot.start_time)
        const endMin = timeToMinutes(slot.end_time)
        for (let m = startMin; m < endMin; m += 30) {
          next.add(`${slot.day_of_week}-${minutesToTime(m)}`)
        }
      }
    }
    setSelected(next)
  }, [open, existing])


  const handleMouseDown = useCallback(
    (day: number, time: string) => {
      const key = `${day}-${time}`
      setIsDragging(true)
      const mode = selected.has(key) ? 'remove' : 'add'
      setDragMode(mode)
      setSelected((prev) => {
        const next = new Set(prev)
        if (mode === 'remove') next.delete(key)
        else next.add(key)
        return next
      })
    },
    [selected],
  )

  const handleMouseEnter = useCallback(
    (day: number, time: string) => {
      if (!isDragging) return
      const key = `${day}-${time}`
      setSelected((prev) => {
        const next = new Set(prev)
        if (dragMode === 'remove') next.delete(key)
        else next.add(key)
        return next
      })
    },
    [isDragging, dragMode],
  )

  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
  }, [])

  // Convert selected cells into contiguous time ranges per day
  const buildSlots = useCallback((): { day_of_week: number; start_time: string; end_time: string }[] => {
    const byDay: Record<number, number[]> = {}
    for (const key of selected) {
      const [dayStr, time] = key.split('-')
      const day = Number(dayStr)
      if (!byDay[day]) byDay[day] = []
      byDay[day].push(timeToMinutes(time))
    }

    const result: { day_of_week: number; start_time: string; end_time: string }[] = []
    for (const [dayStr, minutes] of Object.entries(byDay)) {
      const day = Number(dayStr)
      const sorted = minutes.sort((a, b) => a - b)
      let start = sorted[0]
      let end = sorted[0] + 30

      for (let i = 1; i < sorted.length; i++) {
        if (sorted[i] === end) {
          end = sorted[i] + 30
        } else {
          result.push({
            day_of_week: day,
            start_time: minutesToTime(start),
            end_time: minutesToTime(end),
          })
          start = sorted[i]
          end = sorted[i] + 30
        }
      }
      result.push({
        day_of_week: day,
        start_time: minutesToTime(start),
        end_time: minutesToTime(end),
      })
    }

    return result.sort((a, b) => a.day_of_week - b.day_of_week || a.start_time.localeCompare(b.start_time))
  }, [selected])

  const handleSave = async () => {
    setError(null)
    try {
      await setAvailability.mutateAsync({
        teacher_ci: teacherCi,
        period_id: periodId,
        slots: buildSlots(),
      })
      onClose()
    } catch (err) {
      setError(extractAxiosError(err, 'No se pudo guardar la disponibilidad.'))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl p-0 overflow-hidden max-h-[95vh] overflow-y-auto">
        <div className="gradient-navy px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <Calendar size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Disponibilidad Docente</h2>
              <p className="text-white/60 text-sm">{teacherName}</p>
            </div>
          </div>
        </div>
        <div className="px-6 py-5 space-y-4" onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp}>
          <p className="text-xs text-gray-500">
            Hacé clic y arrastrá para marcar/desmarcar bloques disponibles (30 min cada uno).
          </p>

          {/* Grid */}
          <div className="overflow-x-auto border border-gray-200 rounded-lg select-none">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-gray-50">
                  <th className="px-2 py-2 text-left text-gray-500 font-semibold w-16 sticky left-0 bg-gray-50 z-10">
                    Hora
                  </th>
                  {WEEKDAYS.map((d) => (
                    <th
                      key={d.value}
                      className="px-2 py-2 text-center font-semibold min-w-[80px]"
                      style={{ color: DAY_COLORS[d.value] }}
                    >
                      {d.label.substring(0, 3)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {timeBlocks.map((time) => (
                  <tr key={time} className="border-t border-gray-100">
                    <td className="px-2 py-0.5 font-mono text-gray-500 sticky left-0 bg-white z-10 text-[10px]">
                      {time}
                    </td>
                    {WEEKDAYS.map((d) => {
                      const key = `${d.value}-${time}`
                      const isSelected = selected.has(key)
                      return (
                        <td
                          key={key}
                          className="px-0.5 py-0.5"
                          onMouseDown={(e) => {
                            e.preventDefault()
                            handleMouseDown(d.value, time)
                          }}
                          onMouseEnter={() => handleMouseEnter(d.value, time)}
                        >
                          <div
                            className={`h-5 rounded-sm cursor-pointer transition-colors ${
                              isSelected
                                ? 'bg-green-400 hover:bg-green-500'
                                : 'bg-gray-100 hover:bg-gray-200'
                            }`}
                          />
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center gap-4 text-xs text-gray-500">
            <div className="flex items-center gap-1.5">
              <div className="w-4 h-3 rounded-sm bg-green-400" />
              Disponible
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-4 h-3 rounded-sm bg-gray-100 border border-gray-200" />
              No disponible
            </div>
            <span className="ml-auto">{selected.size} bloques seleccionados</span>
          </div>

          {error && <ErrorBanner error={error} />}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              onClick={handleSave}
              disabled={setAvailability.isPending}
              className="text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {setAvailability.isPending && <Loader2 size={16} className="animate-spin mr-1" />}
              Guardar Disponibilidad
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ─── Slot Card ────────────────────────────────────────────────────────────────

function SlotCard({
  slot,
  onDelete,
  isDeleting,
}: {
  slot: DesignationSlot
  onDelete: (id: number) => void
  isDeleting: boolean
}) {
  const color = DAY_COLORS[slot.day_of_week] ?? '#003366'

  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100 last:border-b-0 hover:bg-gray-50/50 transition-colors">
      <div
        className="w-2 h-full min-h-[40px] rounded-full flex-shrink-0"
        style={{ backgroundColor: color }}
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-800">{slot.day_name}</span>
          <span className="text-xs font-mono text-gray-600">
            {slot.start_time} – {slot.end_time}
          </span>
          <span className="text-xs text-gray-400">{slot.academic_hours}h acad.</span>
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          {slot.room_code ? (
            <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full font-medium">
              {slot.room_code}
            </span>
          ) : (
            <span className="text-xs text-gray-400 italic">Sin sala</span>
          )}
          <span className="text-xs text-gray-400">Desig. #{slot.designation_id}</span>
        </div>
      </div>
      <button
        onClick={() => onDelete(slot.id)}
        disabled={isDeleting}
        className="p-1.5 rounded-md hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors disabled:opacity-50"
        title="Eliminar slot"
      >
        {isDeleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
      </button>
    </div>
  )
}

// ─── Teacher View ─────────────────────────────────────────────────────────────

function TeacherView({
  periodId,
  rooms,
}: {
  periodId: number
  rooms: Room[]
}) {
  const { data: teachersData, isLoading: loadingTeachers } = useTeachers({ perPage: 500 })
  const [selectedTeacherCi, setSelectedTeacherCi] = useState('')
  const [teacherSearch, setTeacherSearch] = useState('')
  const [designationId, setDesignationId] = useState('')
  const [createSlotOpen, setCreateSlotOpen] = useState(false)
  const [availabilityOpen, setAvailabilityOpen] = useState(false)
  const [deletingSlotId, setDeletingSlotId] = useState<number | null>(null)

  const deleteSlot = useDeleteSlot()

  const teachers = teachersData?.items ?? []
  const filteredTeachers = useMemo(() => {
    if (!teacherSearch) return teachers.slice(0, 50)
    const q = teacherSearch.toLowerCase()
    return teachers.filter(
      (t) => t.full_name.toLowerCase().includes(q) || t.ci.includes(q),
    ).slice(0, 50)
  }, [teachers, teacherSearch])

  const selectedTeacher = teachers.find((t) => t.ci === selectedTeacherCi)

  // Slots for selected designation
  const numDesigId = designationId ? Number(designationId) : 0
  const { data: slots, isLoading: loadingSlots } = useDesignationSlots(numDesigId, numDesigId > 0)

  // Teacher availability
  const { data: availability } = useTeacherAvailability(selectedTeacherCi, periodId, !!selectedTeacherCi)

  const handleDeleteSlot = async (id: number) => {
    if (!window.confirm('Eliminar este slot?')) return
    setDeletingSlotId(id)
    try {
      await deleteSlot.mutateAsync(id)
    } finally {
      setDeletingSlotId(null)
    }
  }

  // Build availability map for grid overlay
  const availabilityMap = useMemo(() => {
    const map = new Set<string>()
    if (availability?.slots) {
      for (const slot of availability.slots) {
        const startMin = timeToMinutes(slot.start_time)
        const endMin = timeToMinutes(slot.end_time)
        for (let m = startMin; m < endMin; m += 30) {
          map.add(`${slot.day_of_week}-${minutesToTime(m)}`)
        }
      }
    }
    return map
  }, [availability])

  // Build slot map for grid
  const slotMap = useMemo(() => {
    const map = new Map<string, DesignationSlot>()
    if (slots) {
      for (const slot of slots) {
        const startMin = timeToMinutes(slot.start_time)
        // Only mark the first block for each slot to show label
        map.set(`${slot.day_of_week}-${minutesToTime(startMin)}`, slot)
      }
    }
    return map
  }, [slots])

  // Calculate slot span for grid display
  const slotSpans = useMemo(() => {
    const spans = new Set<string>()
    if (slots) {
      for (const slot of slots) {
        const startMin = timeToMinutes(slot.start_time)
        const endMin = timeToMinutes(slot.end_time)
        for (let m = startMin; m < endMin; m += 30) {
          spans.add(`${slot.day_of_week}-${minutesToTime(m)}`)
        }
      }
    }
    return spans
  }, [slots])

  // Time blocks for the mini-grid (only busy hours range)
  const gridTimeBlocks = useMemo(() => {
    const blocks: string[] = []
    for (let h = 6; h < 22; h++) {
      blocks.push(`${String(h).padStart(2, '0')}:00`)
      blocks.push(`${String(h).padStart(2, '0')}:30`)
    }
    return blocks
  }, [])

  return (
    <div className="space-y-4">
      {/* Teacher selector */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2 flex-1 min-w-[240px]">
              <Users size={16} className="text-gray-400 flex-shrink-0" />
              <div className="relative flex-1">
                <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <Input
                  value={teacherSearch}
                  onChange={(e) => setTeacherSearch(e.target.value)}
                  placeholder="Buscar docente por nombre o CI..."
                  className="pl-8"
                />
              </div>
            </div>
            {selectedTeacher && (
              <>
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    value={designationId}
                    onChange={(e) => setDesignationId(e.target.value)}
                    placeholder="ID Designación"
                    className="w-36"
                  />
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setAvailabilityOpen(true)}
                  className="gap-1 text-xs"
                >
                  <Calendar size={14} />
                  Disponibilidad
                </Button>
                <Button
                  size="sm"
                  onClick={() => setCreateSlotOpen(true)}
                  className="gap-1 text-white text-xs"
                  style={{ backgroundColor: '#003366' }}
                  disabled={!designationId}
                >
                  <Plus size={14} />
                  Agregar Slot
                </Button>
              </>
            )}
          </div>
        </div>

        {/* Teacher list (dropdown) */}
        {!selectedTeacherCi && (
          <div className="max-h-64 overflow-y-auto">
            {loadingTeachers ? (
              <LoadingPage />
            ) : filteredTeachers.length === 0 ? (
              <div className="py-8 text-center">
                <p className="text-sm text-gray-400">No se encontraron docentes</p>
              </div>
            ) : (
              filteredTeachers.map((t) => (
                <button
                  key={t.ci}
                  onClick={() => {
                    setSelectedTeacherCi(t.ci)
                    setTeacherSearch('')
                  }}
                  className="w-full px-5 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors text-left border-b border-gray-50 last:border-b-0"
                >
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                    style={{ backgroundColor: '#003366' }}
                  >
                    {t.full_name.charAt(0)}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate">{t.full_name}</p>
                    <p className="text-xs text-gray-400 font-mono">{t.ci}</p>
                  </div>
                  <ChevronRight size={14} className="text-gray-300 ml-auto" />
                </button>
              ))
            )}
          </div>
        )}

        {/* Selected teacher header */}
        {selectedTeacher && (
          <div className="px-5 py-3 bg-blue-50/50 border-b border-blue-100 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold"
                style={{ backgroundColor: '#003366' }}
              >
                {selectedTeacher.full_name.charAt(0)}
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-800">{selectedTeacher.full_name}</p>
                <p className="text-xs text-gray-500 font-mono">{selectedTeacher.ci}</p>
              </div>
            </div>
            <button
              onClick={() => {
                setSelectedTeacherCi('')
                setDesignationId('')
              }}
              className="p-1.5 rounded-md hover:bg-gray-200 text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X size={14} />
            </button>
          </div>
        )}
      </div>

      {/* Weekly mini-grid (shows availability + slots) */}
      {selectedTeacher && (
        <div className="card-3d-static overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
            <Clock size={16} className="text-gray-500" />
            <h3 className="text-sm font-semibold" style={{ color: '#003366' }}>
              Grilla Semanal
            </h3>
            <div className="flex items-center gap-3 ml-auto text-xs text-gray-500">
              <div className="flex items-center gap-1.5">
                <div className="w-4 h-3 rounded-sm bg-green-200 border border-green-300" />
                Disponible
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-4 h-3 rounded-sm bg-blue-500" />
                Clase asignada
              </div>
            </div>
          </div>
          <div className="overflow-x-auto p-3">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="bg-gray-50">
                  <th className="px-1 py-1.5 text-left text-gray-500 font-semibold w-12 sticky left-0 bg-gray-50 z-10">
                    Hora
                  </th>
                  {WEEKDAYS.map((d) => (
                    <th
                      key={d.value}
                      className="px-1 py-1.5 text-center font-semibold min-w-[60px]"
                      style={{ color: DAY_COLORS[d.value] }}
                    >
                      {d.label.substring(0, 3)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {gridTimeBlocks.map((time) => (
                  <tr key={time} className="border-t border-gray-50">
                    <td className="px-1 py-0 font-mono text-gray-400 sticky left-0 bg-white z-10">
                      {time.endsWith(':00') ? time : ''}
                    </td>
                    {WEEKDAYS.map((d) => {
                      const key = `${d.value}-${time}`
                      const isAvailable = availabilityMap.has(key)
                      const hasSlotHere = slotSpans.has(key)
                      const slotStart = slotMap.get(key)

                      let bg = 'bg-gray-50'
                      if (hasSlotHere) bg = 'bg-blue-500'
                      else if (isAvailable) bg = 'bg-green-200'

                      return (
                        <td key={key} className="px-0.5 py-0">
                          <div
                            className={`h-4 rounded-[2px] ${bg} relative`}
                            title={
                              slotStart
                                ? `Desig. #${slotStart.designation_id} ${slotStart.start_time}-${slotStart.end_time} ${slotStart.room_code || 'sin sala'}`
                                : isAvailable
                                  ? 'Disponible'
                                  : ''
                            }
                          >
                            {slotStart && (
                              <span className="absolute inset-0 flex items-center justify-center text-white text-[8px] font-bold truncate px-0.5">
                                #{slotStart.designation_id}
                              </span>
                            )}
                          </div>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Slots list for selected designation */}
      {selectedTeacher && numDesigId > 0 && (
        <div className="card-3d-static overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold" style={{ color: '#003366' }}>
                Slots — Designación #{designationId}
              </h3>
              {slots && (
                <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                  {slots.length}
                </span>
              )}
            </div>
          </div>
          {loadingSlots ? (
            <LoadingPage />
          ) : !slots?.length ? (
            <div className="py-8 text-center">
              <Clock size={32} className="mx-auto text-gray-300 mb-2" />
              <p className="text-sm text-gray-400">No hay slots para esta designación</p>
            </div>
          ) : (
            <div>
              {slots.map((slot) => (
                <SlotCard
                  key={slot.id}
                  slot={slot}
                  onDelete={handleDeleteSlot}
                  isDeleting={deletingSlotId === slot.id}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Dialogs */}
      {createSlotOpen && (
        <CreateSlotDialog
          open={createSlotOpen}
          onClose={() => setCreateSlotOpen(false)}
          rooms={rooms}
          designationId={numDesigId > 0 ? numDesigId : undefined}
        />
      )}
      {availabilityOpen && selectedTeacher && (
        <AvailabilityDialog
          open={availabilityOpen}
          onClose={() => setAvailabilityOpen(false)}
          teacherCi={selectedTeacherCi}
          teacherName={selectedTeacher.full_name}
          periodId={periodId}
          existing={availability}
        />
      )}
    </div>
  )
}

// ─── Room View ────────────────────────────────────────────────────────────────

function RoomView({ periodId, rooms }: { periodId: number; rooms: Room[] }) {
  const [selectedRoomId, setSelectedRoomId] = useState('')
  const [designationId, setDesignationId] = useState('')
  const [createSlotOpen, setCreateSlotOpen] = useState(false)

  const numDesigId = designationId ? Number(designationId) : 0
  const numRoomId = selectedRoomId ? Number(selectedRoomId) : 0
  const { data: roomSlots, isLoading } = useRoomSlots(numRoomId, periodId, numRoomId > 0)
  const deleteSlot = useDeleteSlot()
  const [deletingSlotId, setDeletingSlotId] = useState<number | null>(null)

  const selectedRoom = rooms.find((r) => r.id === Number(selectedRoomId))

  const handleDeleteSlot = async (id: number) => {
    if (!window.confirm('Eliminar este slot?')) return
    setDeletingSlotId(id)
    try {
      await deleteSlot.mutateAsync(id)
    } finally {
      setDeletingSlotId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2 min-w-[200px]">
              <Building2 size={16} className="text-gray-400" />
              <Select value={selectedRoomId} onValueChange={setSelectedRoomId}>
                <SelectTrigger className="w-[240px]">
                  <SelectValue placeholder="Seleccionar sala..." />
                </SelectTrigger>
                <SelectContent>
                  {rooms
                    .filter((r) => r.is_active)
                    .map((r) => (
                      <SelectItem key={r.id} value={String(r.id)}>
                        {r.name} ({r.code}) — Cap. {r.capacity}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
            {selectedRoom && (
              <>
                <Input
                  type="number"
                  value={designationId}
                  onChange={(e) => setDesignationId(e.target.value)}
                  placeholder="ID Designación"
                  className="w-36"
                />
                <Button
                  size="sm"
                  onClick={() => setCreateSlotOpen(true)}
                  className="gap-1 text-white text-xs"
                  style={{ backgroundColor: '#003366' }}
                  disabled={!designationId}
                >
                  <Plus size={14} />
                  Agregar Slot
                </Button>
              </>
            )}
          </div>
        </div>

        {selectedRoom && (
          <div className="px-5 py-3 bg-blue-50/50 border-b border-blue-100">
            <div className="flex items-center gap-4 text-sm">
              <span className="font-semibold" style={{ color: '#003366' }}>
                {selectedRoom.name}
              </span>
              <span className="text-xs text-gray-500">
                {selectedRoom.building} — Piso {selectedRoom.floor}
              </span>
              <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full">
                {selectedRoom.room_type_name}
              </span>
              <span className="text-xs text-gray-500">Cap. {selectedRoom.capacity}</span>
            </div>
          </div>
        )}

        {!selectedRoom && (
          <div className="py-12 text-center">
            <Building2 size={40} className="mx-auto text-gray-300 mb-3" />
            <p className="text-gray-400 font-medium">Seleccioná una sala para ver sus horarios</p>
          </div>
        )}

        {selectedRoom && (
          <div>
            {isLoading ? (
              <LoadingPage />
            ) : !roomSlots?.length ? (
              <div className="py-8 text-center">
                <Clock size={32} className="mx-auto text-gray-300 mb-2" />
                <p className="text-sm text-gray-400">
                  No hay slots asignados a esta sala en el período seleccionado
                </p>
              </div>
            ) : (
              roomSlots.map((slot) => (
                <SlotCard
                  key={slot.id}
                  slot={slot}
                  onDelete={handleDeleteSlot}
                  isDeleting={deletingSlotId === slot.id}
                />
              ))
            )}
          </div>
        )}
      </div>

      {createSlotOpen && (
        <CreateSlotDialog
          open={createSlotOpen}
          onClose={() => setCreateSlotOpen(false)}
          rooms={rooms}
          designationId={numDesigId > 0 ? numDesigId : undefined}
          defaultRoomId={numRoomId > 0 ? numRoomId : undefined}
        />
      )}
    </div>
  )
}

// ─── Weekly Overview ──────────────────────────────────────────────────────────

function WeeklyView({ periodId }: { periodId: number }) {
  const { data: availabilities, isLoading } = usePeriodAvailabilities(periodId)

  // Flatten all availability into a lookup table for display
  const allAvailSlots = useMemo(() => {
    if (!availabilities) return []
    type FlatAvail = AvailabilitySlot & { teacher_ci: string; teacher_name: string }
    const result: FlatAvail[] = []
    for (const ta of availabilities) {
      for (const slot of ta.slots) {
        result.push({ ...slot, teacher_ci: ta.teacher_ci, teacher_name: ta.teacher_name })
      }
    }
    return result
  }, [availabilities])

  // Group by day and sort by time
  const byDay = useMemo(() => {
    const map: Record<number, typeof allAvailSlots> = {}
    for (const s of allAvailSlots) {
      if (!map[s.day_of_week]) map[s.day_of_week] = []
      map[s.day_of_week].push(s)
    }
    for (const day of Object.keys(map)) {
      map[Number(day)].sort((a, b) => a.start_time.localeCompare(b.start_time))
    }
    return map
  }, [allAvailSlots])

  return (
    <div className="space-y-4">
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
          <Calendar size={16} className="text-gray-500" />
          <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
            Disponibilidad del Período — Vista Semanal
          </h3>
          {availabilities && (
            <span className="text-sm text-gray-500 bg-gray-100 px-2.5 py-1 rounded-full font-medium ml-auto">
              {availabilities.length} docentes
            </span>
          )}
        </div>

        {isLoading ? (
          <LoadingPage />
        ) : !availabilities?.length ? (
          <div className="py-12 text-center">
            <Calendar size={40} className="mx-auto text-gray-300 mb-3" />
            <p className="text-gray-400 font-medium">
              No hay disponibilidades registradas para este período
            </p>
          </div>
        ) : (
          <div className="p-5 overflow-x-auto">
            <div className="grid grid-cols-6 gap-3 min-w-[900px]">
              {WEEKDAYS.map((d) => {
                const daySlots = byDay[d.value] ?? []
                const color = DAY_COLORS[d.value]
                return (
                  <div key={d.value} className="space-y-2">
                    <div
                      className="text-sm font-semibold text-center py-2 rounded-lg"
                      style={{ backgroundColor: `${color}18`, color }}
                    >
                      {d.label}
                    </div>
                    {daySlots.length === 0 ? (
                      <p className="text-xs text-gray-400 text-center py-3">Sin registros</p>
                    ) : (
                      daySlots.map((s, i) => (
                        <div
                          key={`${s.teacher_ci}-${i}`}
                          className="text-xs bg-green-50 border border-green-200 rounded-lg px-2.5 py-2"
                        >
                          <p className="font-medium text-gray-800 truncate">{s.teacher_name}</p>
                          <p className="text-gray-500 font-mono mt-0.5">
                            {s.start_time} – {s.end_time}
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function SchedulingPage() {
  const { data: periods } = usePeriods()
  const { data: activePeriod } = useActivePeriod()
  const { data: rooms } = useRooms({ active_only: true })

  const [selectedPeriodId, setSelectedPeriodId] = useState<string>('')
  const [viewMode, setViewMode] = useState<ViewMode>('teacher')

  // Default to active period
  const effectivePeriodId = selectedPeriodId
    ? Number(selectedPeriodId)
    : activePeriod?.id ?? 0

  const viewModes: { key: ViewMode; label: string; icon: typeof Users }[] = [
    { key: 'teacher', label: 'Por Docente', icon: Users },
    { key: 'room', label: 'Por Sala', icon: Building2 },
    { key: 'weekly', label: 'Semanal', icon: Calendar },
  ]

  return (
    <div className="space-y-5 max-w-7xl">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ backgroundColor: '#003366' }}
          >
            <Clock size={20} className="text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold" style={{ color: '#003366' }}>
              Horarios
            </h1>
            <p className="text-sm text-gray-500">
              Gestión de slots de horario, disponibilidad docente y conflictos
            </p>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Period selector */}
        <div className="flex items-center gap-2">
          <Label className="text-sm text-gray-500 whitespace-nowrap">Período:</Label>
          <Select
            value={selectedPeriodId || (activePeriod ? String(activePeriod.id) : '')}
            onValueChange={setSelectedPeriodId}
          >
            <SelectTrigger className="w-[220px]">
              <SelectValue placeholder="Seleccionar período" />
            </SelectTrigger>
            <SelectContent>
              {periods?.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>
                  {p.name} {p.status === 'active' ? '(activo)' : ''}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* View mode toggle */}
        <div className="flex rounded-lg border border-gray-200 bg-white overflow-hidden shadow-sm ml-auto">
          {viewModes.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setViewMode(key)}
              className={`px-3 py-2 text-xs font-medium transition-colors flex items-center gap-1.5 ${
                viewMode === key
                  ? 'text-white'
                  : 'text-gray-600 hover:text-gray-800 hover:bg-gray-50'
              }`}
              style={viewMode === key ? { backgroundColor: '#003366' } : undefined}
            >
              <Icon size={13} />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {effectivePeriodId === 0 ? (
        <div className="card-3d-static py-12 text-center">
          <Calendar size={40} className="mx-auto text-gray-300 mb-3" />
          <p className="text-gray-400 font-medium">
            Seleccioná un período académico para empezar
          </p>
        </div>
      ) : (
        <>
          {viewMode === 'teacher' && (
            <TeacherView periodId={effectivePeriodId} rooms={rooms ?? []} />
          )}
          {viewMode === 'room' && (
            <RoomView periodId={effectivePeriodId} rooms={rooms ?? []} />
          )}
          {viewMode === 'weekly' && <WeeklyView periodId={effectivePeriodId} />}
        </>
      )}
    </div>
  )
}
