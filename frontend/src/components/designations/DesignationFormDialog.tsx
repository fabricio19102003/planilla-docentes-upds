import { useState } from 'react'
import { Plus, Trash2, TriangleAlert } from 'lucide-react'

import { useAcademicTeacherSearch } from '@/api/hooks/useAcademicManagement'
import { useCreateDesignation, useUpdateDesignation } from '@/api/hooks/useDesignationAdmin'
import type { DesignationAdminItem, DesignationAdminMutation } from '@/api/types'
import { TeacherCombobox } from '@/components/academic-management/TeacherCombobox'
import { DesignationProblems } from '@/components/designations/DesignationProblems'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog, DialogDescription, DialogFooter, DialogHeader, DialogPanel, DialogPopup, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { TEACHER_SEARCH_PAGE_SIZE } from '@/lib/academicManagementState'
import {
  DAY_OPTIONS,
  SEMESTER_OPTIONS,
  academicHours,
  detectDesignationType,
  emptySlot,
  errorDetails,
  formErrors,
  formToPayload,
  suggestedMonthlyHours,
  suggestedSemesterHours,
  weeklyHours,
  type DesignationForm,
  type ProblemDetails,
  type SlotForm,
} from '@/lib/designationAdminState'

const selectClass = 'h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50'
const GROUP_SUGGESTIONS = ['M-1', 'M-2', 'M-3', 'M-4', 'T-1', 'T-2', 'T-3', 'N-1', 'N-2', 'N-3', 'G.E.', 'EXTRA']

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <fieldset className="flex flex-col gap-3 rounded-lg border p-4">
      <legend className="px-1 text-sm font-semibold text-foreground">{title}</legend>
      {description && <p className="-mt-1 text-xs text-muted-foreground">{description}</p>}
      {children}
    </fieldset>
  )
}

function SlotRow({ index, slot, canRemove, onChange, onRemove }: {
  index: number
  slot: SlotForm
  canRemove: boolean
  onChange: (slot: SlotForm) => void
  onRemove: () => void
}) {
  const hours = academicHours(slot.hora_inicio, slot.hora_fin)
  const label = `Bloque ${index + 1}`
  return (
    <div className="grid grid-cols-2 items-end gap-2 sm:grid-cols-[1.3fr_1fr_1fr_auto_auto]">
      <div className="col-span-2 sm:col-span-1">
        <Label htmlFor={`slot-${index}-day`} className="text-xs">{label}: día</Label>
        <select id={`slot-${index}-day`} className={selectClass} value={slot.dia} onChange={(event) => onChange({ ...slot, dia: event.target.value })}>
          <option value="">Elegí un día</option>
          {DAY_OPTIONS.map((day) => <option key={day.value} value={day.value}>{day.label}</option>)}
        </select>
      </div>
      <div>
        <Label htmlFor={`slot-${index}-start`} className="text-xs">Desde</Label>
        <Input id={`slot-${index}-start`} type="time" value={slot.hora_inicio} onChange={(event) => onChange({ ...slot, hora_inicio: event.target.value })} />
      </div>
      <div>
        <Label htmlFor={`slot-${index}-end`} className="text-xs">Hasta</Label>
        <Input id={`slot-${index}-end`} type="time" value={slot.hora_fin} onChange={(event) => onChange({ ...slot, hora_fin: event.target.value })} />
      </div>
      <p className="pb-2 text-sm tabular-nums text-muted-foreground" aria-live="polite">= {hours} h</p>
      <Button type="button" size="icon" variant="ghost" aria-label={`Quitar ${label.toLowerCase()}`} disabled={!canRemove} onClick={onRemove}>
        <Trash2 aria-hidden="true" />
      </Button>
    </div>
  )
}

export interface DesignationFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Item being edited; null creates a new designation. */
  item: DesignationAdminItem | null
  initialForm: DesignationForm
  subjects: string[]
  onSaved: (result: DesignationAdminMutation, mode: 'create' | 'edit') => void
  onFinalizeInstead?: (item: DesignationAdminItem) => void
}

export function DesignationFormDialog({ open, onOpenChange, item, initialForm, subjects, onSaved, onFinalizeInstead }: DesignationFormDialogProps) {
  const [form, setForm] = useState<DesignationForm>(initialForm)
  const [typeTouched, setTypeTouched] = useState(Boolean(item))
  const [problems, setProblems] = useState<ProblemDetails | null>(null)
  const [teacherSearch, setTeacherSearch] = useState('')
  const [teacherPage, setTeacherPage] = useState(1)
  const teachers = useAcademicTeacherSearch(teacherSearch, teacherPage)
  const create = useCreateDesignation()
  const update = useUpdateDesignation()
  const saving = create.isPending || update.isPending
  const editing = item !== null
  const editBlocked = editing && !item.actions.edit.allowed
  const datesLocked = editing && !item.actions.edit_dates.allowed
  const weekly = weeklyHours(form.slots)
  const monthlySuggestion = suggestedMonthlyHours(weekly)
  const semesterSuggestion = suggestedSemesterHours(Number(form.monthlyHours) || monthlySuggestion)

  const set = <K extends keyof DesignationForm>(key: K, value: DesignationForm[K]) => {
    setProblems(null)
    setForm((current) => ({ ...current, [key]: value }))
  }

  const setSubject = (subject: string) => {
    setProblems(null)
    setForm((current) => ({
      ...current,
      subject,
      designationType: typeTouched ? current.designationType : detectDesignationType(subject),
    }))
  }

  const setSlot = (index: number, slot: SlotForm) =>
    set('slots', form.slots.map((current, position) => (position === index ? slot : current)))

  const save = () => {
    const errors = formErrors(form)
    if (errors.length) {
      setProblems({ title: 'Faltan datos o hay datos para corregir.', items: errors })
      return
    }
    const body = formToPayload(form)
    const onError = (error: unknown) => setProblems(errorDetails(error, 'No se pudo guardar la designación.'))
    if (editing) {
      update.mutate({ id: item.id, body }, { onSuccess: (result) => onSaved(result!, 'edit'), onError })
    } else {
      create.mutate(body, { onSuccess: (result) => onSaved(result!, 'create'), onError })
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{editing ? 'Editar designación' : 'Nueva designación'}</DialogTitle>
          <DialogDescription>
            {editing
              ? `${item.subject} · ${item.group_code} · ${item.teacher_name}`
              : `Asigná una materia a un docente en el período ${form.academicPeriod}.`}
          </DialogDescription>
        </DialogHeader>
        <DialogPanel className="flex flex-col gap-4">
          {editBlocked && (
            <Alert variant="warning">
              <TriangleAlert aria-hidden="true" />
              <AlertTitle>Esta designación ya se pagó y no se puede editar</AlertTitle>
              <AlertDescription>
                <p>{item.actions.edit.reason}</p>
                <p>Si algo cambia desde ahora, finalizala en la fecha del cambio y creá una nueva designación desde el día siguiente.</p>
                {onFinalizeInstead && (
                  <Button type="button" size="sm" variant="outline" className="mt-2" onClick={() => onFinalizeInstead(item)}>
                    Finalizar esta designación
                  </Button>
                )}
              </AlertDescription>
            </Alert>
          )}

          <fieldset disabled={editBlocked || saving} className="flex flex-col gap-4">
            <Section title="1. Docente y materia">
              <div>
                <Label htmlFor="designation-teacher">Docente</Label>
                {editing ? (
                  <>
                    <p id="designation-teacher" className="text-sm font-medium">{item.teacher_name} <span className="text-muted-foreground">(CI {item.teacher_ci})</span></p>
                    <p className="text-xs text-muted-foreground">Para pasar la materia a otro docente usá Gestión académica → Cambiar docente.</p>
                  </>
                ) : (
                  <TeacherCombobox
                    id="designation-teacher"
                    teachers={teachers.data?.items ?? []}
                    value={form.teacherCi}
                    onChange={(ci) => set('teacherCi', ci)}
                    search={teacherSearch}
                    onSearchChange={(value) => { setTeacherSearch(value); setTeacherPage(1) }}
                    loading={teachers.isLoading}
                    page={teacherPage}
                    pageCount={Math.max(1, Math.ceil((teachers.data?.total ?? 0) / TEACHER_SEARCH_PAGE_SIZE))}
                    onPageChange={setTeacherPage}
                  />
                )}
              </div>
              <div>
                <Label htmlFor="designation-subject">Materia</Label>
                <Input id="designation-subject" list="designation-subjects" value={form.subject} onChange={(event) => setSubject(event.target.value)} placeholder="Ej: ANATOMÍA HUMANA I" />
                <datalist id="designation-subjects">{subjects.map((subject) => <option key={subject} value={subject} />)}</datalist>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <div>
                  <Label htmlFor="designation-semester">Semestre</Label>
                  <select id="designation-semester" className={selectClass} value={form.semester} onChange={(event) => set('semester', event.target.value)}>
                    <option value="">Elegí</option>
                    {[...new Set([...SEMESTER_OPTIONS, ...(form.semester ? [form.semester] : [])])].map((value) => (
                      <option key={value} value={value}>{value.charAt(0) + value.slice(1).toLowerCase()}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <Label htmlFor="designation-group">Grupo</Label>
                  <Input id="designation-group" list="designation-groups" value={form.groupCode} onChange={(event) => set('groupCode', event.target.value)} placeholder="Ej: M-1" />
                  <datalist id="designation-groups">{GROUP_SUGGESTIONS.map((group) => <option key={group} value={group} />)}</datalist>
                </div>
                <div>
                  <Label htmlFor="designation-type">Tipo</Label>
                  <select id="designation-type" className={selectClass} value={form.designationType} onChange={(event) => { setTypeTouched(true); set('designationType', event.target.value as DesignationForm['designationType']) }}>
                    <option value="regular">Teoría</option>
                    <option value="practice">Práctica</option>
                  </select>
                </div>
              </div>
            </Section>

            <Section title="2. Horario semanal" description="Cargá cada bloque de clase. Las horas académicas se calculan solas (bloques de 45 minutos).">
              {form.slots.map((slot, index) => (
                <SlotRow
                  key={index}
                  index={index}
                  slot={slot}
                  canRemove={form.slots.length > 1}
                  onChange={(next) => setSlot(index, next)}
                  onRemove={() => set('slots', form.slots.filter((_slot, position) => position !== index))}
                />
              ))}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Button type="button" size="sm" variant="outline" onClick={() => set('slots', [...form.slots, emptySlot()])}>
                  <Plus aria-hidden="true" />Agregar bloque
                </Button>
                <p className="text-sm font-medium">Total: {weekly} horas académicas por semana</p>
              </div>
            </Section>

            <Section title="3. Horas a pagar" description="La planilla paga las horas mensuales. Te sugerimos un valor; cambialo si la designación dice otra cosa.">
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor="designation-monthly">Horas mensuales</Label>
                  <Input id="designation-monthly" type="number" min={0} inputMode="numeric" value={form.monthlyHours} onChange={(event) => set('monthlyHours', event.target.value)} />
                  {weekly > 0 && String(monthlySuggestion) !== form.monthlyHours && (
                    <Button type="button" size="xs" variant="link" className="px-0" onClick={() => set('monthlyHours', String(monthlySuggestion))}>
                      Usar sugerido: {monthlySuggestion} (semanales × 4)
                    </Button>
                  )}
                </div>
                <div>
                  <Label htmlFor="designation-semester-hours">Horas del semestre (opcional)</Label>
                  <Input id="designation-semester-hours" type="number" min={0} inputMode="numeric" value={form.semesterHours} onChange={(event) => set('semesterHours', event.target.value)} />
                  {semesterSuggestion > 0 && String(semesterSuggestion) !== form.semesterHours && (
                    <Button type="button" size="xs" variant="link" className="px-0" onClick={() => set('semesterHours', String(semesterSuggestion))}>
                      Usar sugerido: {semesterSuggestion} (mensuales × 5)
                    </Button>
                  )}
                </div>
              </div>
            </Section>

            <Section title="4. Fechas del contrato" description="Desde qué día y hasta qué día dicta la materia. Si las dejás vacías se toma todo el período académico.">
              {datesLocked && !editBlocked && (
                <p className="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">{item.actions.edit_dates.reason}</p>
              )}
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor="designation-start">Fecha de inicio</Label>
                  <Input id="designation-start" type="date" disabled={datesLocked} value={form.contractStartDate} onChange={(event) => set('contractStartDate', event.target.value)} />
                </div>
                <div>
                  <Label htmlFor="designation-end">Fecha de fin</Label>
                  <Input id="designation-end" type="date" disabled={datesLocked} value={form.contractEndDate} onChange={(event) => set('contractEndDate', event.target.value)} />
                </div>
              </div>
            </Section>
          </fieldset>

          <DesignationProblems problems={problems} />
        </DialogPanel>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button type="button" onClick={save} disabled={editBlocked || saving}>
            {saving ? 'Guardando…' : editing ? 'Guardar cambios' : 'Crear designación'}
          </Button>
        </DialogFooter>
      </DialogPopup>
    </Dialog>
  )
}
