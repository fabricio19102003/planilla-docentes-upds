import { useMemo, useState } from 'react'
import { CalendarDays, Download } from 'lucide-react'

import { useDownloadScheduleExcel, useScheduleView } from '@/api/hooks/useAcademicSchedules'
import { useScheduleDrafts } from '@/api/hooks/useSchedulePlanner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { WeeklyScheduleGrid } from '@/components/academic-management/WeeklyScheduleGrid'
import { getTodayInBolivia } from '@/lib/boliviaDates'
import { groupBlocksBySchedule, subjectColor } from '@/lib/academicScheduleGrid'
import type { ScheduleFilters, ScheduleSource } from '@/lib/academicScheduleGrid'

const selectClass = 'h-10 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50'
const semesterLabel = (semester: number | null) => (semester === null ? 'Sin semestre' : `${semester}.º semestre`)

const errorText = (error: unknown) => {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : 'No se pudo cargar el horario. Intente nuevamente.'
}

export function SchedulesSection() {
  const [period, setPeriod] = useState('II/2026')
  const [source, setSource] = useState<ScheduleSource>('current')
  const [draftId, setDraftId] = useState<number | null>(null)
  const [date, setDate] = useState(getTodayInBolivia())
  const [semester, setSemester] = useState<number | null>(null)
  const [group, setGroup] = useState('')
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const drafts = useScheduleDrafts()
  const filters: ScheduleFilters = { period, source, draftId, date, semester, group }
  const view = useScheduleView(filters)
  const download = useDownloadScheduleExcel()

  const semesters = view.data?.semesters ?? []
  const groups = semesters.find((item) => item.semester === semester)?.groups ?? []
  const schedules = useMemo(() => groupBlocksBySchedule(view.data?.blocks ?? []), [view.data])
  const subjects = useMemo(() => [...new Set((view.data?.blocks ?? []).map((block) => block.subject_name))].sort(), [view.data])
  const periodDrafts = (drafts.data ?? []).filter((item) => item.academic_period === period && item.status !== 'archived')
  const needsDraft = source === 'draft' && !draftId

  const runDownload = async () => {
    setDownloadError(null)
    try {
      await download.mutateAsync(filters)
    } catch {
      setDownloadError('No se pudo generar el Excel. Revise los filtros e intente nuevamente.')
    }
  }

  return (
    <section aria-labelledby="schedules-heading" className="flex flex-col gap-5">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h2 id="schedules-heading" className="flex items-center gap-2 text-xl font-semibold text-foreground"><CalendarDays aria-hidden="true" className="size-5 text-info-foreground" />Horarios por semestre y grupo</h2>
          <p className="text-sm text-muted-foreground">
            {source === 'current'
              ? 'Horario vigente: el mismo que usa la planilla (teoría desde las designaciones y prácticas desde la última publicación).'
              : 'Borrador: bloques en planificación; no afectan pagos hasta publicarse.'}
          </p>
        </div>
        <Button onClick={() => void runDownload()} disabled={!view.data?.blocks.length || download.isPending}>
          <Download aria-hidden="true" />{download.isPending ? 'Generando…' : 'Descargar Excel'}
        </Button>
      </div>

      <div className="grid gap-3 rounded-xl border bg-card p-4 sm:grid-cols-2 lg:grid-cols-6">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="schedule-period">Período</Label>
          <Input id="schedule-period" value={period} onChange={(event) => { setPeriod(event.target.value.trim()); setSemester(null); setGroup('') }} placeholder="II/2026" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="schedule-source">Fuente</Label>
          <select id="schedule-source" className={selectClass} value={source} onChange={(event) => { setSource(event.target.value as ScheduleSource); setSemester(null); setGroup('') }}>
            <option value="current">Vigente</option>
            <option value="draft">Borrador</option>
          </select>
        </div>
        {source === 'draft' ? (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="schedule-draft">Borrador</Label>
            <select id="schedule-draft" className={selectClass} value={draftId ?? ''} disabled={drafts.isLoading} onChange={(event) => { setDraftId(event.target.value ? Number(event.target.value) : null); setSemester(null); setGroup('') }}>
              <option value="">Seleccione un borrador</option>
              {periodDrafts.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </div>
        ) : null}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="schedule-date">Fecha de referencia</Label>
          <Input id="schedule-date" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="schedule-semester">Semestre</Label>
          <select id="schedule-semester" className={selectClass} value={semester ?? ''} disabled={!semesters.length} onChange={(event) => { setSemester(event.target.value ? Number(event.target.value) : null); setGroup('') }}>
            <option value="">Todos los semestres</option>
            {semesters.filter((item) => item.semester !== null).map((item) => <option key={item.semester} value={item.semester ?? ''}>{semesterLabel(item.semester)} · {item.groups.length}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="schedule-group">Grupo</Label>
          <select id="schedule-group" className={selectClass} value={group} disabled={semester === null} onChange={(event) => setGroup(event.target.value)}>
            <option value="">Todos los grupos</option>
            {groups.map((code) => <option key={code} value={code}>{code}</option>)}
          </select>
        </div>
      </div>

      {downloadError && <p role="alert" className="rounded-md border border-destructive/32 bg-destructive/4 p-3 text-sm text-destructive-foreground">{downloadError}</p>}
      {needsDraft && <p role="status" className="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">Seleccione un borrador para ver sus bloques.</p>}
      {view.isFetching && !needsDraft && <p role="status" className="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">{view.isLoading ? 'Cargando horario…' : 'Actualizando horario…'}</p>}
      {view.isError && (
        <div role="alert" className="flex items-center justify-between gap-2 rounded-md border border-destructive/32 bg-destructive/4 p-3 text-sm text-destructive-foreground">
          <span>{errorText(view.error)}</span>
          <Button type="button" size="sm" variant="outline" onClick={() => void view.refetch()}>Reintentar</Button>
        </div>
      )}
      {view.data && !view.isError && !schedules.length && <p className="rounded-xl border bg-card px-4 py-10 text-center text-muted-foreground">No hay clases para este filtro.</p>}

      {subjects.length > 0 && (
        <div className="flex flex-wrap gap-2" aria-label="Materias del horario">
          {subjects.map((subject) => {
            const { background: fill, border: edge, text: ink } = subjectColor(subject)
            return <span key={subject} className="rounded-full border border-(--subject-border) bg-(--subject-bg) px-2.5 py-0.5 text-xs font-medium text-(--subject-text)" style={{ '--subject-bg': fill, '--subject-border': edge, '--subject-text': ink } as React.CSSProperties}>{subject}</span>
          })}
          <span className="rounded-full border border-dashed border-border px-2.5 py-0.5 text-xs italic text-muted-foreground">Borde punteado = práctica</span>
        </div>
      )}

      {schedules.map((schedule) => (
        <article key={`${schedule.semester}-${schedule.group}`} className="flex flex-col gap-2">
          <h3 className="text-base font-semibold text-foreground">
            {semesterLabel(schedule.semester)} · Grupo {schedule.group}
            <span className="ml-2 text-sm font-normal text-muted-foreground">{schedule.blocks.length} bloques</span>
          </h3>
          <WeeklyScheduleGrid blocks={schedule.blocks} label={`Horario de ${semesterLabel(schedule.semester)}, grupo ${schedule.group}`} />
        </article>
      ))}
    </section>
  )
}
