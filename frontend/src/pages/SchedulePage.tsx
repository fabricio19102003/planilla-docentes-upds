import { useId, useState, useRef } from 'react'
import { useMySchedule, downloadSchedulePDF } from '@/api/hooks/useAuth'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { cn } from '@/lib/utils'
import {
  AlertCircle,
  BookOpen,
  CalendarX,
  Users,
  Clock,
  FileDown,
  Image as ImageIcon,
  Filter,
} from 'lucide-react'
import { toPng } from 'html-to-image'
import type { PortalDesignationSchedule } from '@/api/types'

// ─── Constants ────────────────────────────────────────────────────────────────

const WEEKDAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

// html-to-image rasterises the schedule from an isolated SVG, where the page's CSS variables do not
// resolve, so the PNG needs a literal opaque background. White keeps the token-colored cells readable.
const EXPORT_BACKGROUND = '#ffffff'

// Day dots and subject accents only use theme tokens, so they follow the theme and stay readable in the export.
const DAY_DOT: Record<string, string> = {
  Lunes: 'bg-primary',
  Martes: 'bg-info',
  Miércoles: 'bg-chart-2',
  Jueves: 'bg-success',
  Viernes: 'bg-chart-3',
  Sábado: 'bg-warning',
}

interface SubjectStyle {
  /** Solid dot. */
  dot: string
  /** Tinted pill: badge and legend. */
  chip: string
  /** Tinted header band. */
  band: string
  /** Weekly grid cell: tinted with a solid left accent. */
  cell: string
}

const SUBJECT_STYLES: SubjectStyle[] = [
  { dot: 'bg-primary', chip: 'border-primary/30 bg-primary/10 text-primary', band: 'bg-primary/8', cell: 'border-primary bg-primary/10' },
  { dot: 'bg-success', chip: 'border-success/30 bg-success/10 text-success-foreground', band: 'bg-success/8', cell: 'border-success bg-success/10' },
  { dot: 'bg-warning', chip: 'border-warning/30 bg-warning/10 text-warning-foreground', band: 'bg-warning/8', cell: 'border-warning bg-warning/10' },
  { dot: 'bg-destructive', chip: 'border-destructive/30 bg-destructive/10 text-destructive-foreground', band: 'bg-destructive/8', cell: 'border-destructive bg-destructive/10' },
  { dot: 'bg-info', chip: 'border-info/30 bg-info/10 text-info-foreground', band: 'bg-info/8', cell: 'border-info bg-info/10' },
  { dot: 'bg-chart-2', chip: 'border-chart-2/30 bg-chart-2/10 text-foreground', band: 'bg-chart-2/8', cell: 'border-chart-2 bg-chart-2/10' },
  { dot: 'bg-chart-3', chip: 'border-chart-3/30 bg-chart-3/10 text-chart-3', band: 'bg-chart-3/8', cell: 'border-chart-3 bg-chart-3/10' },
]

type ViewMode = 'dia' | 'materia' | 'grilla'
type TurnFilter = 'todos' | 'M' | 'T' | 'N'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function hashSubject(subject: string): number {
  let hash = 0
  for (let i = 0; i < subject.length; i++) {
    hash = (hash << 5) - hash + subject.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash)
}

function getSubjectStyle(subject: string): SubjectStyle {
  return SUBJECT_STYLES[hashSubject(subject) % SUBJECT_STYLES.length]
}

function normDay(dia: string): string {
  return dia
    .toLowerCase()
    .replace('é', 'e')
    .replace('á', 'a')
    .replace('ó', 'o')
    .replace('ú', 'u')
    .replace('í', 'i')
}

interface FlatSlot {
  key: string
  dia: string
  hora_inicio: string
  hora_fin: string
  horas_academicas: number
  subject: string
  group_code: string
  semester: string
  source_key: string
  source_kind: 'legacy' | 'published'
  activity_kind: 'theory' | 'practice'
}

function buildFlatSlots(
  designations: PortalDesignationSchedule[],
  turnFilter: TurnFilter,
): FlatSlot[] {
  const slots: FlatSlot[] = []
  const keyOccurrences = new Map<string, number>()

  for (const d of designations) {
    if (turnFilter !== 'todos') {
      const prefix = d.group_code.charAt(0).toUpperCase()
      if (prefix !== turnFilter) continue
    }
    for (const s of d.schedule) {
      const baseKey = [
        normDay(s.dia),
        s.hora_inicio,
        s.hora_fin,
        d.subject,
        d.group_code,
        d.semester,
        d.source_key,
      ].join('|')
      const occurrence = keyOccurrences.get(baseKey) ?? 0
      keyOccurrences.set(baseKey, occurrence + 1)

      slots.push({
        key: `${baseKey}|${occurrence}`,
        dia: s.dia,
        hora_inicio: s.hora_inicio,
        hora_fin: s.hora_fin,
        horas_academicas: s.horas_academicas,
        subject: d.subject,
        group_code: d.group_code,
        semester: d.semester,
        source_key: d.source_key,
        source_kind: d.source_kind,
        activity_kind: d.activity_kind,
      })
    }
  }
  return slots
}

// ─── Stats bar ────────────────────────────────────────────────────────────────

function StatsBar({ allSlots }: { allSlots: FlatSlot[] }) {
  const uniqueSubjects = new Set(allSlots.map((s) => s.subject)).size
  const uniqueGroups = new Set(allSlots.map((s) => s.group_code)).size
  const visibleHours = allSlots.reduce((sum, slot) => sum + slot.horas_academicas, 0)

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <StatCard icon={Clock} title="Horas visibles/semana" value={visibleHours} tone="primary" />
      <StatCard icon={BookOpen} title="Materias visibles" value={uniqueSubjects} tone="info" />
      <StatCard icon={Users} title="Grupos visibles" value={uniqueGroups} tone="success" />
    </div>
  )
}

// ─── View: Por Día ────────────────────────────────────────────────────────────

function ViewPorDia({ allSlots }: { allSlots: FlatSlot[] }) {
  const headingIdPrefix = useId()

  if (allSlots.length === 0) {
    return (
      <Card>
        <EmptyState icon={CalendarX} title="No hay clases con los filtros seleccionados" />
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {WEEKDAYS.map((day) => {
        const dayNorm = normDay(day)
        const daySlots = allSlots
          .filter((s) => normDay(s.dia) === dayNorm)
          .sort((a, b) => a.hora_inicio.localeCompare(b.hora_inicio))

        if (daySlots.length === 0) return null

        return (
          <Card
            key={day}
            render={<section aria-labelledby={`${headingIdPrefix}-${dayNorm}`} />}
            className="overflow-hidden"
          >
            <div className="flex items-center gap-2 border-b bg-muted/40 px-4 py-2.5">
              <div className={cn('size-2 shrink-0 rounded-full', DAY_DOT[day] ?? 'bg-primary')} />
              <h3 id={`${headingIdPrefix}-${dayNorm}`} className="text-sm font-semibold capitalize text-foreground">{day}</h3>
              <span className="ml-auto text-xs text-muted-foreground">{daySlots.length} clase(s)</span>
            </div>
            <div className="divide-y">
              {daySlots.map((slot) => (
                <div key={slot.key} className="flex flex-col items-start gap-2 px-3 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-3 sm:px-4">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="min-w-[72px] shrink-0 text-center">
                      <p className="text-sm font-semibold tabular-nums text-foreground">
                        {slot.hora_inicio}
                      </p>
                      <p className="text-xs tabular-nums text-muted-foreground">{slot.hora_fin}</p>
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">{slot.subject}</p>
                      <div className="mt-0.5 flex flex-wrap items-center gap-2">
                        <Badge variant="outline" className="font-mono">
                          {slot.group_code}
                        </Badge>
                        <span className="text-xs text-muted-foreground">{slot.semester}</span>
                        <span className="text-xs text-muted-foreground">
                          {slot.activity_kind === 'practice' ? 'Práctica' : 'Teoría'} · {slot.source_kind === 'published' ? 'Publicado' : 'Legado'}
                        </span>
                      </div>
                    </div>
                  </div>
                  <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{slot.horas_academicas}h</span>
                </div>
              ))}
            </div>
          </Card>
        )
      })}
    </div>
  )
}

// ─── View: Por Materia ────────────────────────────────────────────────────────

function ViewPorMateria({ designations, turnFilter }: { designations: PortalDesignationSchedule[]; turnFilter: TurnFilter }) {
  const filtered = designations.filter((d) => {
    if (turnFilter === 'todos') return true
    return d.group_code.charAt(0).toUpperCase() === turnFilter
  })

  if (filtered.length === 0) {
    return (
      <Card>
        <EmptyState icon={CalendarX} title="No hay materias con los filtros seleccionados" />
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {filtered.map((d) => {
        const style = getSubjectStyle(`${d.subject}|${d.activity_kind}`)
        const sorted = [...d.schedule].sort((a, b) => a.hora_inicio.localeCompare(b.hora_inicio))

        return (
          <Card key={d.source_key} className="overflow-hidden">
            <div className={cn('flex items-center gap-3 px-4 py-3', style.band)}>
              <div className={cn('size-3 shrink-0 rounded-full', style.dot)} />
              <div className="min-w-0 flex-1">
                <h3 className="truncate text-sm font-semibold text-foreground">{d.subject}</h3>
                <div className="mt-0.5 flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className={cn('font-mono', style.chip)}>
                    {d.group_code}
                  </Badge>
                  <span className="text-xs text-muted-foreground">{d.semester}</span>
                  <span className="text-xs text-muted-foreground">
                    {d.activity_kind === 'practice' ? 'Práctica' : 'Teoría'} · {d.source_kind === 'published' ? 'Publicado' : 'Legado'}
                  </span>
                  {d.weekly_hours != null && (
                    <span className="ml-auto text-xs tabular-nums text-muted-foreground">{d.weekly_hours}h/sem</span>
                  )}
                </div>
              </div>
            </div>
            {sorted.length > 0 ? (
              <div className="divide-y">
                {sorted.map((slot) => (
                  <div key={`${d.source_key}|${normDay(slot.dia)}|${slot.hora_inicio}|${slot.hora_fin}`} className="flex flex-wrap items-center gap-2 px-3 py-2.5 sm:gap-3 sm:px-4">
                    <div
                      className={cn(
                        'size-1.5 shrink-0 rounded-full',
                        DAY_DOT[WEEKDAYS.find((w) => normDay(w) === normDay(slot.dia)) ?? 'Lunes'] ?? style.dot,
                      )}
                    />
                    <span className="min-w-[76px] text-xs font-medium capitalize text-muted-foreground">
                      {slot.dia}
                    </span>
                    <span className="font-mono text-xs tabular-nums text-foreground">
                      {slot.hora_inicio} – {slot.hora_fin}
                    </span>
                    <span className="ml-auto text-xs tabular-nums text-muted-foreground">{slot.horas_academicas}h</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="px-4 py-3 text-xs italic text-muted-foreground">Sin horario registrado</p>
            )}
          </Card>
        )
      })}
    </div>
  )
}

// ─── View: Grilla Semanal ─────────────────────────────────────────────────────

function ViewGrillaSemanal({ allSlots }: { allSlots: FlatSlot[] }) {
  const uniqueTimes = Array.from(new Set(allSlots.map((s) => s.hora_inicio))).sort()
  const slotsByCell = new Map<string, FlatSlot[]>()

  for (const slot of allSlots) {
    const cellKey = `${normDay(slot.dia)}|${slot.hora_inicio}`
    const cellSlots = slotsByCell.get(cellKey)
    if (cellSlots) {
      cellSlots.push(slot)
    } else {
      slotsByCell.set(cellKey, [slot])
    }
  }

  if (uniqueTimes.length === 0) {
    return (
      <Card>
        <EmptyState icon={CalendarX} title="No hay clases con los filtros seleccionados" />
      </Card>
    )
  }

  return (
    <Card className="max-w-full overflow-hidden">
      <div className="max-w-full overflow-x-auto" role="region" aria-label="Grilla semanal desplazable">
        <table className="min-w-[900px] w-full text-sm">
          <caption className="sr-only">Horario semanal agrupado por día y hora de inicio</caption>
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="w-24 px-3 py-3 text-left text-xs font-medium text-muted-foreground">
                Hora
              </th>
              {WEEKDAYS.map((day) => (
                <th key={day} className="px-3 py-3 text-center text-xs font-medium capitalize text-muted-foreground">
                  {day}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {uniqueTimes.map((time) => (
              <tr key={time} className="border-b last:border-0 even:bg-muted/20">
                <td className="px-3 py-2 text-center">
                  <p className="font-mono text-xs font-semibold tabular-nums text-foreground">{time}</p>
                  <p className="text-[10px] text-muted-foreground">inicio</p>
                </td>
                {WEEKDAYS.map((day) => {
                  const cellSlots = slotsByCell.get(`${normDay(day)}|${time}`) ?? []

                  return (
                    <td key={day} className="px-1 py-1 text-center align-top">
                      <div className="space-y-1">
                        {cellSlots.map((slot) => {
                          const style = getSubjectStyle(`${slot.subject}|${slot.activity_kind}`)

                          return (
                            <div
                              key={slot.key}
                              className={cn('mx-auto max-w-[140px] rounded-lg border-l-4 p-2 text-left', style.cell)}
                            >
                              <p className="text-xs font-semibold leading-tight text-foreground">{slot.subject}</p>
                              <p className="mt-1 text-[11px] text-foreground/80">Grupo {slot.group_code}</p>
                              <p className="text-[11px] text-muted-foreground">{slot.semester}</p>
                              <p className="text-[10px] text-muted-foreground">
                                {slot.activity_kind === 'practice' ? 'Práctica' : 'Teoría'} · {slot.source_kind === 'published' ? 'Publicado' : 'Legado'}
                              </p>
                              <p className="mt-1 font-mono text-[10px] tabular-nums text-muted-foreground">
                                {slot.hora_inicio}-{slot.hora_fin} · {slot.horas_academicas}h
                              </p>
                            </div>
                          )
                        })}
                      </div>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

// ─── Legend ───────────────────────────────────────────────────────────────────

function SubjectLegend({ designations }: { designations: PortalDesignationSchedule[] }) {
  if (designations.length === 0) return null

  return (
    <Card className="p-4">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Referencias
      </p>
      <div className="flex flex-wrap gap-2">
        {designations.map((d) => {
          const style = getSubjectStyle(`${d.subject}|${d.activity_kind}`)
          return (
            <div
              key={d.source_key}
              className={cn('flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium', style.chip)}
            >
              <div className={cn('size-2 shrink-0 rounded-full', style.dot)} />
              {d.subject} ({d.group_code}) · {d.activity_kind === 'practice' ? 'Práctica' : 'Teoría'}
            </div>
          )
        })}
      </div>
    </Card>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

function ScheduleSkeleton() {
  return (
    <div role="status" aria-busy="true" className="space-y-4">
      <span className="sr-only">Cargando horario</span>
      <Skeleton className="h-9 w-72 max-w-full rounded-lg" />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-20 rounded-2xl" />
        ))}
      </div>
      <Skeleton className="h-64 w-full rounded-2xl" />
    </div>
  )
}

export function SchedulePage() {
  const { data: schedule, isLoading, error, refetch, isFetching } = useMySchedule()
  const [viewMode, setViewMode] = useState<ViewMode>('dia')
  const [turnFilter, setTurnFilter] = useState<TurnFilter>('todos')
  const [isExportingPDF, setIsExportingPDF] = useState(false)
  const [isExportingImg, setIsExportingImg] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)

  const handleExportPDF = async () => {
    setIsExportingPDF(true)
    try {
      await downloadSchedulePDF(schedule?.teacher_name)
    } catch (e) {
      console.error('Error exporting PDF:', e)
    } finally {
      setIsExportingPDF(false)
    }
  }

  const handleExportImage = async () => {
    if (!contentRef.current) return
    setIsExportingImg(true)
    try {
      const dataUrl = await toPng(contentRef.current, {
        pixelRatio: 2,
        backgroundColor: EXPORT_BACKGROUND,
      })
      const link = document.createElement('a')
      link.download = `horario_${schedule?.teacher_name?.replace(/\s+/g, '_') ?? 'docente'}.png`
      link.href = dataUrl
      link.click()
    } catch (e) {
      console.error('Error exporting image:', e)
    } finally {
      setIsExportingImg(false)
    }
  }

  if (isLoading) {
    return (
      <div className="max-w-5xl">
        <PageHeader title="Mi Horario Semanal" description="Tus clases por día, por materia y en grilla." />
        <ScheduleSkeleton />
      </div>
    )
  }

  if (error || !schedule) {
    return (
      <div className="max-w-5xl">
        <PageHeader title="Mi Horario Semanal" description="Tus clases por día, por materia y en grilla." />
        <Alert variant="error">
          <AlertCircle aria-hidden="true" />
          <AlertTitle>No se pudo cargar el horario</AlertTitle>
          <AlertDescription>Revisá tu conexión e intentá de nuevo.</AlertDescription>
          <AlertAction>
            <Button type="button" variant="outline" size="sm" onClick={() => void refetch()} disabled={isFetching}>
              {isFetching ? 'Reintentando...' : 'Reintentar'}
            </Button>
          </AlertAction>
        </Alert>
      </div>
    )
  }

  const visibleDesignations = schedule.designations.filter((designation) => {
    if (turnFilter === 'todos') return true
    return designation.group_code.charAt(0).toUpperCase() === turnFilter
  })
  const allSlots = buildFlatSlots(visibleDesignations, 'todos')

  const viewModes: { key: ViewMode; label: string }[] = [
    { key: 'dia', label: 'Por Día' },
    { key: 'materia', label: 'Por Materia' },
    { key: 'grilla', label: 'Grilla Semanal' },
  ]

  const turnOptions: { value: TurnFilter; label: string }[] = [
    { value: 'todos', label: 'Todos los turnos' },
    { value: 'M', label: 'Mañana (M)' },
    { value: 'T', label: 'Tarde (T)' },
    { value: 'N', label: 'Noche (N)' },
  ]

  return (
    <div className="max-w-5xl space-y-4 sm:space-y-5">
      <PageHeader
        title="Mi Horario Semanal"
        description={schedule.teacher_name}
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportImage}
              disabled={isExportingImg}
              className="h-9 flex-1 gap-1.5 text-xs sm:h-8 sm:flex-none"
            >
              <ImageIcon size={13} aria-hidden="true" />
              {isExportingImg ? 'Exportando...' : 'Exportar Imagen'}
            </Button>
            <Button
              size="sm"
              onClick={handleExportPDF}
              disabled={isExportingPDF}
              className="h-9 flex-1 gap-1.5 text-xs sm:h-8 sm:flex-none"
            >
              <FileDown size={13} aria-hidden="true" />
              {isExportingPDF ? 'Generando...' : 'Exportar PDF'}
            </Button>
          </>
        }
      />

      {/* Filters bar */}
      <div className="flex flex-wrap items-center gap-3">
        {/* View mode tabs */}
        <div className="flex max-w-full overflow-x-auto rounded-lg border bg-card shadow-xs/5">
          {viewModes.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => setViewMode(key)}
              aria-pressed={viewMode === key}
              className={cn(
                'whitespace-nowrap px-3 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring',
                viewMode === key
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground',
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Turn filter */}
        <div className="flex items-center gap-1.5">
          <Filter size={13} className="text-muted-foreground" aria-hidden="true" />
          <Select
            value={turnFilter}
            items={turnOptions}
            onValueChange={(value) => setTurnFilter((value ?? 'todos') as TurnFilter)}
          >
            <SelectTrigger aria-label="Filtrar horario por turno" size="sm" className="min-w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectPopup>
              {turnOptions.map(({ value, label }) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectPopup>
          </Select>
        </div>
      </div>

      {/* Stats */}
      <StatsBar allSlots={allSlots} />

      {/* Content (captured for image export) */}
      <div ref={contentRef} id="schedule-content" className="space-y-4">
        {/* Header for export */}
        <div className="hidden print:block">
          <p className="text-lg font-semibold text-foreground">{schedule.teacher_name} — Horario Semanal</p>
        </div>

        {viewMode === 'dia' && <ViewPorDia allSlots={allSlots} />}
        {viewMode === 'materia' && (
          <ViewPorMateria designations={visibleDesignations} turnFilter="todos" />
        )}
        {viewMode === 'grilla' && <ViewGrillaSemanal allSlots={allSlots} />}

        {/* Legend always visible */}
        <SubjectLegend designations={visibleDesignations} />
      </div>
    </div>
  )
}
