import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Pencil, Plus, Power, School } from 'lucide-react'

import {
  useAcademicCollection,
  useAcademicTeacherSearch,
  useDeactivateAcademicResource,
  useSaveAcademicResource,
  useTeacherAvailability,
} from '@/api/hooks/useAcademicManagement'
import type { AcademicResource } from '@/api/hooks/useAcademicManagement'
import type {
  AcademicCatalogBase,
  AcademicGroup,
  AcademicProgram,
  AcademicSubject,
  Classroom,
  SubjectOffering,
  TeacherAvailability,
} from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  availabilityPayload,
  normalizeClassroomResources,
  optionalPositiveInteger,
  TEACHER_SEARCH_PAGE_SIZE,
} from '@/lib/academicManagementState'

type FormState = Record<string, string>
type Option = { value: string; label: string }
type Field = {
  name: string
  label: string
  type?: 'text' | 'number' | 'select'
  required?: boolean | ((form: FormState) => boolean)
  min?: number
  options?: Option[]
  placeholder?: string
}

const errorMessage = (error: unknown) => {
  const detail = (error as { response?: { data?: { detail?: string | Array<{ msg: string }> } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(' ')
  return 'No se pudo completar la operación. Revise los datos e intente nuevamente.'
}

function StatusBadge({ active }: { active: boolean }) {
  return <Badge variant={active ? 'default' : 'secondary'}>{active ? 'Activo' : 'Inactivo'}</Badge>
}

function CatalogSection<T extends AcademicCatalogBase>({
  resource,
  title,
  description,
  query,
  fields,
  emptyForm,
  toForm,
  toPayload,
  summary,
}: {
  resource: Exclude<AcademicResource, 'availability'>
  title: string
  description: string
  query: {
    data: T[] | undefined
    isLoading: boolean
    isError: boolean
    error: unknown
    refetch: () => Promise<unknown>
  }
  fields: Field[]
  emptyForm: FormState
  toForm: (item: T) => FormState
  toPayload: (form: FormState) => Record<string, unknown>
  summary: (item: T) => string
}) {
  const items = query.data
  const save = useSaveAcademicResource(resource)
  const deactivate = useDeactivateAcademicResource(resource)
  const [editing, setEditing] = useState<T | null>(null)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<FormState>(emptyForm)
  const [error, setError] = useState<string | null>(null)
  const errorId = `${resource}-form-error`

  const beginCreate = () => {
    setEditing(null)
    setForm(emptyForm)
    setError(null)
    setOpen(true)
  }
  const beginEdit = (item: T) => {
    setEditing(item)
    setForm(toForm(item))
    setError(null)
    setOpen(true)
  }
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      await save.mutateAsync({ id: editing?.id, payload: toPayload(form) })
      setOpen(false)
    } catch (caught) {
      setError(errorMessage(caught))
    }
  }
  const handleDeactivate = async (item: T) => {
    setError(null)
    try {
      await deactivate.mutateAsync(item.id)
    } catch (caught) {
      setError(errorMessage(caught))
    }
  }

  return (
    <section aria-labelledby={`${resource}-heading`} className="flex flex-col gap-4">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h2 id={`${resource}-heading`} className="text-xl font-semibold text-slate-900">{title}</h2>
          <p className="text-sm text-slate-500">{description}</p>
        </div>
        <Button onClick={beginCreate}><Plus aria-hidden="true" />Agregar</Button>
      </div>
      {error && !open && <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {query.isLoading && <p role="status" className="rounded-md border bg-slate-50 p-3 text-sm text-slate-600">Cargando registros…</p>}
      {query.isError && (
        <div role="alert" className="flex flex-col items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <span>{errorMessage(query.error)}</span>
          <Button type="button" size="sm" variant="outline" onClick={() => void query.refetch()}>Reintentar</Button>
        </div>
      )}
      <div className="overflow-x-auto rounded-xl border bg-white">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="bg-slate-50 text-left text-slate-600">
            <tr><th className="px-4 py-3">Detalle</th><th className="px-4 py-3">Estado</th><th className="px-4 py-3 text-right">Acciones</th></tr>
          </thead>
          <tbody>
            {items?.map((item) => (
              <tr key={item.id} className="border-t">
                <td className="px-4 py-3 font-medium text-slate-800">{summary(item)}</td>
                <td className="px-4 py-3"><StatusBadge active={item.active} /></td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" size="sm" onClick={() => beginEdit(item)}><Pencil aria-hidden="true" />Editar</Button>
                    {item.active && <Button variant="outline" size="sm" onClick={() => void handleDeactivate(item)}><Power aria-hidden="true" />Desactivar</Button>}
                  </div>
                </td>
              </tr>
            ))}
            {!query.isLoading && !query.isError && !items?.length && <tr><td colSpan={3} className="px-4 py-10 text-center text-slate-500">No hay registros.</td></tr>}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{editing ? `Editar ${title.toLowerCase()}` : `Agregar ${title.toLowerCase()}`}</DialogTitle>
            <DialogDescription>Complete los campos obligatorios antes de guardar.</DialogDescription>
          </DialogHeader>
          <form onSubmit={submit} className="flex flex-col gap-4">
            {fields.map((field) => {
              const id = `${resource}-${field.name}`
              const required = typeof field.required === 'function' ? field.required(form) : field.required
              return (
                <div key={field.name} className="flex flex-col gap-1.5">
                  <Label htmlFor={id}>{field.label}{required ? ' *' : ''}</Label>
                  {field.type === 'select' ? (
                    <select
                      id={id}
                      value={form[field.name] ?? ''}
                      required={required}
                      aria-invalid={Boolean(error)}
                      aria-describedby={error ? errorId : undefined}
                      onChange={(event) => setForm((current) => ({ ...current, [field.name]: event.target.value }))}
                      className="h-10 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <option value="">Seleccione una opción</option>
                      {field.options?.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                  ) : (
                    <Input
                      id={id}
                      type={field.type ?? 'text'}
                      min={field.min}
                      required={required}
                      placeholder={field.placeholder}
                      value={form[field.name] ?? ''}
                      aria-invalid={Boolean(error)}
                      aria-describedby={error ? errorId : undefined}
                      onChange={(event) => setForm((current) => ({ ...current, [field.name]: event.target.value }))}
                    />
                  )}
                </div>
              )
            })}
            {error && <p id={errorId} role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
              <Button type="submit" disabled={save.isPending}>{save.isPending ? 'Guardando…' : 'Guardar'}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </section>
  )
}

const commonFields: Field[] = [
  { name: 'code', label: 'Código', required: true },
  { name: 'name', label: 'Nombre', required: true },
]

function AvailabilitySection() {
  const [teacherSearch, setTeacherSearch] = useState('')
  const [debouncedTeacherSearch, setDebouncedTeacherSearch] = useState('')
  const [teacherPage, setTeacherPage] = useState(1)
  const teachers = useAcademicTeacherSearch(debouncedTeacherSearch, teacherPage)
  const [teacherCi, setTeacherCi] = useState('')
  const [selectedTeacherLabel, setSelectedTeacherLabel] = useState('')
  const [academicPeriod, setAcademicPeriod] = useState('')
  const availability = useTeacherAvailability(teacherCi, academicPeriod)
  const save = useSaveAcademicResource('availability')
  const deactivate = useDeactivateAcademicResource('availability')
  const [editing, setEditing] = useState<TeacherAvailability | null>(null)
  const [form, setForm] = useState({ weekday: 'monday', start_time: '', end_time: '' })
  const [error, setError] = useState<string | null>(null)
  const canSubmit = Boolean(teacherCi && academicPeriod && form.start_time && form.end_time)
  const teacherPages = Math.max(1, Math.ceil((teachers.data?.total ?? 0) / TEACHER_SEARCH_PAGE_SIZE))

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedTeacherSearch(teacherSearch.trim())
      setTeacherPage(1)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [teacherSearch])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      await save.mutateAsync({ id: editing?.id, payload: availabilityPayload(teacherCi, academicPeriod, form) })
      setEditing(null)
      setForm({ weekday: 'monday', start_time: '', end_time: '' })
    } catch (caught) {
      setError(errorMessage(caught))
    }
  }
  const edit = (item: TeacherAvailability) => {
    setEditing(item)
    setForm({ weekday: item.weekday, start_time: item.start_time.slice(0, 5), end_time: item.end_time.slice(0, 5) })
    setError(null)
  }
  const weekdays: Option[] = [
    ['monday', 'Lunes'], ['tuesday', 'Martes'], ['wednesday', 'Miércoles'], ['thursday', 'Jueves'],
    ['friday', 'Viernes'], ['saturday', 'Sábado'], ['sunday', 'Domingo'],
  ].map(([value, label]) => ({ value, label }))

  return (
    <section aria-labelledby="availability-heading" className="grid gap-6 lg:grid-cols-[360px_1fr]">
      <form onSubmit={submit} className="flex flex-col gap-4 rounded-xl border bg-white p-5">
        <div><h2 id="availability-heading" className="text-xl font-semibold">Disponibilidad docente</h2><p className="text-sm text-slate-500">Bloques semanales por período académico.</p></div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="availability-period">Período académico *</Label>
          <Input id="availability-period" required value={academicPeriod} onChange={(event) => setAcademicPeriod(event.target.value)} placeholder="II/2026" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="availability-teacher-search">Buscar docente</Label>
          <Input id="availability-teacher-search" type="search" value={teacherSearch} onChange={(event) => setTeacherSearch(event.target.value)} placeholder="Nombre o C.I." aria-describedby="availability-teacher-search-help" />
          <p id="availability-teacher-search-help" className="text-xs text-slate-500">La búsqueda consulta resultados paginados y no descarga el padrón completo.</p>
          {teachers.isFetching && <p role="status" className="text-sm text-slate-600">Buscando docentes…</p>}
          {teachers.isError && <div role="alert" className="flex items-center justify-between gap-2 rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700"><span>No se pudieron cargar los docentes.</span><Button type="button" size="sm" variant="outline" onClick={() => void teachers.refetch()}>Reintentar</Button></div>}
          {!teachers.isFetching && !teachers.isError && teachers.data?.items.length === 0 && <p role="status" className="text-sm text-slate-600">No se encontraron docentes para esta búsqueda.</p>}
          <Label htmlFor="availability-teacher">Docente *</Label>
          <select
            id="availability-teacher"
            required
            value={teacherCi}
            disabled={teachers.isFetching || teachers.isError}
            onChange={(event) => {
              const teacher = teachers.data?.items.find((item) => item.ci === event.target.value)
              setTeacherCi(event.target.value)
              setSelectedTeacherLabel(teacher ? `${teacher.full_name} — ${teacher.ci}` : selectedTeacherLabel)
            }}
            className="h-10 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="">Seleccione un docente</option>
            {teacherCi && !teachers.data?.items.some((teacher) => teacher.ci === teacherCi) && <option value={teacherCi}>{selectedTeacherLabel || teacherCi}</option>}
            {teachers.data?.items.map((teacher) => <option key={teacher.ci} value={teacher.ci}>{teacher.full_name} — {teacher.ci}</option>)}
          </select>
          {!teachers.isError && (teachers.data?.total ?? 0) > TEACHER_SEARCH_PAGE_SIZE && (
            <div className="flex items-center justify-between gap-2" aria-label="Paginación de docentes">
              <Button type="button" size="sm" variant="outline" disabled={teacherPage <= 1 || teachers.isFetching} onClick={() => setTeacherPage((page) => page - 1)}>Anterior</Button>
              <span className="text-xs text-slate-500">Página {teacherPage} de {teacherPages}</span>
              <Button type="button" size="sm" variant="outline" disabled={teacherPage >= teacherPages || teachers.isFetching} onClick={() => setTeacherPage((page) => page + 1)}>Siguiente</Button>
            </div>
          )}
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="availability-weekday">Día *</Label>
          <select id="availability-weekday" required value={form.weekday} onChange={(event) => setForm((current) => ({ ...current, weekday: event.target.value }))} className="h-10 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            {weekdays.map((day) => <option key={day.value} value={day.value}>{day.label}</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5"><Label htmlFor="availability-start">Hora de inicio *</Label><Input id="availability-start" type="time" required value={form.start_time} aria-invalid={Boolean(error)} aria-describedby={error ? 'availability-error' : undefined} onChange={(event) => setForm((current) => ({ ...current, start_time: event.target.value }))} /></div>
          <div className="flex flex-col gap-1.5"><Label htmlFor="availability-end">Hora de fin *</Label><Input id="availability-end" type="time" required value={form.end_time} aria-invalid={Boolean(error)} aria-describedby={error ? 'availability-error' : undefined} onChange={(event) => setForm((current) => ({ ...current, end_time: event.target.value }))} /></div>
        </div>
        {error && <p id="availability-error" role="alert" aria-live="polite" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        <div className="flex gap-2"><Button type="submit" disabled={!canSubmit || save.isPending}>{editing ? 'Actualizar bloque' : 'Agregar bloque'}</Button>{editing && <Button type="button" variant="outline" onClick={() => setEditing(null)}>Cancelar edición</Button>}</div>
      </form>
      <div className="overflow-x-auto rounded-xl border bg-white">
        <table className="w-full min-w-[560px] text-sm">
          <thead className="bg-slate-50 text-left"><tr><th className="px-4 py-3">Día</th><th className="px-4 py-3">Horario</th><th className="px-4 py-3">Estado</th><th className="px-4 py-3 text-right">Acciones</th></tr></thead>
          <tbody>
            {availability.data?.map((item) => <tr key={item.id} className="border-t"><td className="px-4 py-3">{weekdays.find((day) => day.value === item.weekday)?.label}</td><td className="px-4 py-3">{item.start_time.slice(0, 5)}–{item.end_time.slice(0, 5)}</td><td className="px-4 py-3"><StatusBadge active={item.active} /></td><td className="px-4 py-3"><div className="flex justify-end gap-2"><Button size="sm" variant="outline" onClick={() => edit(item)}><Pencil aria-hidden="true" />Editar</Button>{item.active && <Button size="sm" variant="outline" onClick={() => void deactivate.mutateAsync(item.id).catch((caught) => setError(errorMessage(caught)))}><Power aria-hidden="true" />Desactivar</Button>}</div></td></tr>)}
            {!teacherCi || !academicPeriod ? <tr><td colSpan={4} className="px-4 py-10 text-center text-slate-500">Seleccione período y docente para consultar sus bloques.</td></tr> : null}
            {availability.isLoading && <tr><td colSpan={4} role="status" className="px-4 py-10 text-center text-slate-600">Cargando disponibilidad…</td></tr>}
            {availability.isError && <tr><td colSpan={4} className="px-4 py-6"><div role="alert" className="flex items-center justify-between gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-red-700"><span>No se pudo cargar la disponibilidad.</span><Button type="button" size="sm" variant="outline" onClick={() => void availability.refetch()}>Reintentar</Button></div></td></tr>}
            {teacherCi && academicPeriod && !availability.isLoading && !availability.isError && !availability.data?.length && <tr><td colSpan={4} className="px-4 py-10 text-center text-slate-500">El docente no tiene bloques registrados en este período.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export function AcademicManagementPage() {
  const programs = useAcademicCollection('programs')
  const subjects = useAcademicCollection('subjects')
  const offerings = useAcademicCollection('offerings')
  const groups = useAcademicCollection('groups')
  const classrooms = useAcademicCollection('classrooms')
  const programOptions = programs.data?.filter((item) => item.active).map((item) => ({ value: String(item.id), label: `${item.code} — ${item.name}` })) ?? []
  const subjectOptions = subjects.data?.filter((item) => item.active).map((item) => ({ value: String(item.id), label: `${item.code} — ${item.name}` })) ?? []

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-center gap-3"><div className="rounded-xl bg-blue-50 p-3 text-blue-800"><School aria-hidden="true" /></div><div><h1 className="text-2xl font-bold text-slate-900">Gestión académica</h1><p className="text-sm text-slate-500">Catálogos formales y disponibilidad docente para planificación.</p></div></header>
      <Tabs defaultValue="programs" className="flex flex-col gap-5">
        <TabsList className="h-auto flex-wrap justify-start">
          <TabsTrigger value="programs">Programas</TabsTrigger><TabsTrigger value="subjects">Asignaturas</TabsTrigger><TabsTrigger value="offerings">Ofertas</TabsTrigger><TabsTrigger value="groups">Grupos</TabsTrigger><TabsTrigger value="classrooms">Aulas</TabsTrigger><TabsTrigger value="availability">Disponibilidad docente</TabsTrigger>
        </TabsList>
        <TabsContent value="programs"><CatalogSection<AcademicProgram> resource="programs" title="Programas" description="Carreras o programas académicos reutilizables." query={programs} fields={commonFields} emptyForm={{ code: '', name: '' }} toForm={(item) => ({ code: item.code, name: item.name })} toPayload={(form) => form} summary={(item) => `${item.code} — ${item.name}`} /></TabsContent>
        <TabsContent value="subjects"><CatalogSection<AcademicSubject> resource="subjects" title="Asignaturas" description="Materias globales independientes de cada carrera." query={subjects} fields={[...commonFields, { name: 'description', label: 'Descripción' }]} emptyForm={{ code: '', name: '', description: '' }} toForm={(item) => ({ code: item.code, name: item.name, description: item.description ?? '' })} toPayload={(form) => ({ ...form, description: form.description || null })} summary={(item) => `${item.code} — ${item.name}`} /></TabsContent>
        <TabsContent value="offerings"><CatalogSection<SubjectOffering> resource="offerings" title="Ofertas académicas" description="Carga teórica y práctica por programa, período y semestre." query={offerings} fields={[{ name: 'subject_id', label: 'Asignatura', type: 'select', required: true, options: subjectOptions }, { name: 'program_id', label: 'Programa', type: 'select', required: true, options: programOptions }, { name: 'academic_period', label: 'Período académico', required: true, placeholder: 'II/2026' }, { name: 'semester', label: 'Semestre', type: 'number', min: 1, required: true }, { name: 'theory_hours', label: 'Horas de teoría', type: 'number', min: 0, required: true }, { name: 'practice_hours', label: 'Horas de práctica', type: 'number', min: 0, required: true }]} emptyForm={{ subject_id: '', program_id: '', academic_period: '', semester: '1', theory_hours: '0', practice_hours: '0' }} toForm={(item) => ({ subject_id: String(item.subject_id), program_id: String(item.program_id), academic_period: item.academic_period, semester: String(item.semester), theory_hours: String(item.theory_hours), practice_hours: String(item.practice_hours) })} toPayload={(form) => ({ ...form, subject_id: Number(form.subject_id), program_id: Number(form.program_id), semester: Number(form.semester), theory_hours: Number(form.theory_hours), practice_hours: Number(form.practice_hours) })} summary={(item) => `${item.subject.code} · ${item.program.code} · ${item.academic_period} · Sem. ${item.semester} · T${item.theory_hours}/P${item.practice_hours}`} /></TabsContent>
        <TabsContent value="groups"><CatalogSection<AcademicGroup> resource="groups" title="Grupos" description="Cohortes reutilizables dentro de un período." query={groups} fields={[{ name: 'program_id', label: 'Programa', type: 'select', required: true, options: programOptions }, { name: 'academic_period', label: 'Período académico', required: true }, { name: 'semester', label: 'Semestre', type: 'number', min: 1, required: true }, { name: 'shift', label: 'Turno', required: true }, { name: 'code', label: 'Código', required: true }, { name: 'expected_size', label: 'Cantidad esperada', type: 'number', min: 1 }]} emptyForm={{ program_id: '', academic_period: '', semester: '1', shift: '', code: '', expected_size: '' }} toForm={(item) => ({ program_id: String(item.program_id), academic_period: item.academic_period, semester: String(item.semester), shift: item.shift, code: item.code, expected_size: item.expected_size ? String(item.expected_size) : '' })} toPayload={(form) => ({ ...form, program_id: Number(form.program_id), semester: Number(form.semester), expected_size: optionalPositiveInteger(form.expected_size) })} summary={(item) => `${item.program.code} · ${item.code} · ${item.academic_period} · Sem. ${item.semester} · ${item.shift}`} /></TabsContent>
        <TabsContent value="classrooms"><CatalogSection<Classroom> resource="classrooms" title="Aulas" description="Ambientes, capacidad y equipamiento disponible." query={classrooms} fields={[...commonFields, { name: 'campus', label: 'Campus', required: true }, { name: 'capacity', label: 'Capacidad', type: 'number', min: 1, required: (form) => form.classroom_type === 'classroom' || form.classroom_type === 'laboratory' }, { name: 'classroom_type', label: 'Tipo', type: 'select', required: true, options: [{ value: 'classroom', label: 'Aula' }, { value: 'laboratory', label: 'Laboratorio' }, { value: 'virtual', label: 'Virtual' }, { value: 'other', label: 'Otro' }] }, { name: 'resources', label: 'Recursos (separados por comas)', placeholder: 'proyector, pizarra' }]} emptyForm={{ code: '', name: '', campus: '', capacity: '', classroom_type: 'classroom', resources: '' }} toForm={(item) => ({ code: item.code, name: item.name, campus: item.campus, capacity: item.capacity === null ? '' : String(item.capacity), classroom_type: item.classroom_type, resources: item.resources.join(', ') })} toPayload={(form) => ({ ...form, capacity: form.capacity ? Number(form.capacity) : null, resources: normalizeClassroomResources(form.resources) })} summary={(item) => `${item.code} — ${item.name} · ${item.campus} · Cap. ${item.capacity ?? 'No aplica'} · ${item.resources.join(', ') || 'Sin recursos'}`} /></TabsContent>
        <TabsContent value="availability"><AvailabilitySection /></TabsContent>
      </Tabs>
    </div>
  )
}
