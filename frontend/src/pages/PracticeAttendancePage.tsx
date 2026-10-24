import { useState, useMemo, Fragment } from 'react'
import {
  Loader2,
  Users,
  Calendar,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Trash2,
  FileText,
  FileSpreadsheet,
  ChevronLeft,
  ChevronRight,
  CalendarDays,
  CheckCheck,
  X,
} from 'lucide-react'
import {
  usePracticeAttendance,
  usePracticeAttendanceSummary,
  useGeneratePracticeAttendance,
  useUpdatePracticeAttendance,
  useDeletePracticeAttendance,
  downloadPracticeAttendancePdf,
  downloadPracticeAttendanceExcel,
} from '@/api/hooks/usePracticeAttendance'
import type { PracticeAttendanceEntry } from '@/api/hooks/usePracticeAttendance'
import { ConfirmAlertDialog } from '@/components/shared/ConfirmAlertDialog'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { TableCard } from '@/components/shared/TableCard'
import { TONE_CHIP, TONE_TEXT, type Tone } from '@/components/shared/tones'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

const MONTH_ITEMS = Object.entries(MONTH_NAMES).map(([value, label]) => ({ value, label }))

const ALL_TEACHERS = 'all'

const STATUS_CONFIG: Record<string, { label: string; tone: Tone; rowTint: string }> = {
  attended:  { label: 'ASISTIÓ',     tone: 'success',     rowTint: '' },
  absent:    { label: 'AUSENTE',     tone: 'destructive', rowTint: 'bg-destructive/4' },
  late:      { label: 'TARDANZA',    tone: 'warning',     rowTint: 'bg-warning/4' },
  justified: { label: 'JUSTIFICADO', tone: 'info',        rowTint: 'bg-info/4' },
}

function autoSetStatus(scheduledStart: string, actualStart: string): 'attended' | 'late' | null {
  if (!actualStart || !scheduledStart) return null

  const [sh, sm] = scheduledStart.split(':').map(Number)
  const [ah, am] = actualStart.split(':').map(Number)

  const scheduledMinutes = sh * 60 + sm
  const actualMinutes = ah * 60 + am
  const diff = actualMinutes - scheduledMinutes

  if (diff <= 15) return 'attended' // On time or up to 15 min late
  return 'late' // More than 15 min late
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '\u2014'
  const d = new Date(dateStr + 'T00:00:00')
  const days = ['Dom', 'Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab']
  return `${days[d.getDay()]} ${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`
}

function formatTime(timeStr: string | null): string {
  if (!timeStr) return '\u2014'
  return timeStr.slice(0, 5)
}

const DAY_NAMES_FULL = ['Domingo', 'Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado']

function formatFullDate(dateStr: string): string {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T00:00:00')
  const dayName = DAY_NAMES_FULL[d.getDay()]
  const day = d.getDate()
  const monthName = MONTH_NAMES[d.getMonth() + 1]
  const year = d.getFullYear()
  return `${dayName} ${day} de ${monthName} de ${year}`
}

function StatusSelect({ entry, disabled, onChange }: {
  entry: PracticeAttendanceEntry
  disabled: boolean
  onChange: (status: string) => void
}) {
  const cfg = STATUS_CONFIG[entry.status] ?? STATUS_CONFIG.absent
  return (
    <select
      aria-label={`Estado de ${entry.teacher_name ?? entry.teacher_ci}`}
      className={cn(
        'h-7 cursor-pointer rounded-full border border-transparent px-3 text-xs font-semibold outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default disabled:opacity-64',
        TONE_CHIP[cfg.tone],
      )}
      value={entry.status}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
    >
      {Object.entries(STATUS_CONFIG).map(([value, sc]) => (
        <option key={value} value={value}>{sc.label}</option>
      ))}
    </select>
  )
}

function TimeField({ label, value, onChange }: { label: string; value: string | null; onChange: (value: string) => void }) {
  return (
    <Input
      type="time"
      step="60"
      size="sm"
      aria-label={label}
      className="mx-auto w-28"
      inputClassName="text-center tabular-nums"
      value={value?.slice(0, 5) ?? ''}
      onChange={(e) => onChange(e.target.value)}
    />
  )
}

function ObservationCell({ entry, editing, value, onValueChange, onStart, onSave, onCancel }: {
  entry: PracticeAttendanceEntry
  editing: boolean
  value: string
  onValueChange: (value: string) => void
  onStart: () => void
  onSave: () => void
  onCancel: () => void
}) {
  if (editing) {
    return (
      <div className="flex items-center gap-1">
        <Input
          type="text"
          size="sm"
          aria-label="Observación"
          className="w-36"
          value={value}
          onChange={(e) => onValueChange(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSave()}
          autoFocus
        />
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label="Guardar observación"
          className="text-success-foreground"
          onClick={onSave}
        >
          <CheckCircle />
        </Button>
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label="Cancelar edición de observación"
          className="text-muted-foreground"
          onClick={onCancel}
        >
          <XCircle />
        </Button>
      </div>
    )
  }
  return (
    <Button
      variant="ghost"
      size="xs"
      className="max-w-36 justify-start text-xs font-normal text-muted-foreground"
      title={entry.observation ?? 'Click para agregar'}
      onClick={onStart}
    >
      <span className="truncate">
        {entry.observation || <span className="italic text-muted-foreground/60">sin obs.</span>}
      </span>
    </Button>
  )
}

function PracticeAttendanceSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Cargando asistencia de prácticas">
      <div className="space-y-2">
        <Skeleton className="h-8 w-80" />
        <Skeleton className="h-4 w-96 max-w-full" />
      </div>
      <Skeleton className="h-28 rounded-2xl" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-24 rounded-2xl" />
        ))}
      </div>
      <Skeleton className="h-64 rounded-2xl" />
    </div>
  )
}

export function PracticeAttendancePage() {
  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1

  const [month, setMonth] = useState<number>(currentMonth)
  const [year, setYear] = useState<number>(currentYear)
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [teacherFilter, setTeacherFilter] = useState<string>('')
  const [selectedDate, setSelectedDate] = useState<string>('')
  const [editingObs, setEditingObs] = useState<number | null>(null)
  const [obsValue, setObsValue] = useState('')
  const [pdfLoading, setPdfLoading] = useState(false)
  const [excelLoading, setExcelLoading] = useState(false)
  const [bulkLoading, setBulkLoading] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<PracticeAttendanceEntry | null>(null)
  const [bulkTarget, setBulkTarget] = useState<'attended' | 'absent' | null>(null)

  const { data: entries, isLoading } = usePracticeAttendance(
    month, year,
    teacherFilter || undefined,
    startDate || undefined,
    endDate || undefined,
  )
  const { data: summaries } = usePracticeAttendanceSummary(
    month, year,
    teacherFilter || undefined,
    startDate || undefined,
    endDate || undefined,
  )
  const { data: teacherSummaries } = usePracticeAttendanceSummary(
    month, year,
    undefined,
    startDate || undefined,
    endDate || undefined,
  )
  const generateMutation = useGeneratePracticeAttendance()
  const updateMutation = useUpdatePracticeAttendance()
  const deleteMutation = useDeletePracticeAttendance()

  // Unique teachers for filter dropdown
  const teachers = useMemo(() => {
    if (teacherSummaries?.length) {
      return teacherSummaries
        .map((s) => ({ ci: s.teacher_ci, name: s.teacher_name ?? s.teacher_ci }))
        .sort((a, b) => a.name.localeCompare(b.name))
    }
    if (!entries) return []
    const map = new Map<string, string>()
    for (const e of entries) {
      if (e.teacher_ci && !map.has(e.teacher_ci)) {
        map.set(e.teacher_ci, e.teacher_name ?? e.teacher_ci)
      }
    }
    return Array.from(map.entries())
      .map(([ci, name]) => ({ ci, name }))
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [entries, teacherSummaries])

  const exportDateRange = useMemo(() => ({
    start_date: selectedDate || startDate || undefined,
    end_date: selectedDate || endDate || undefined,
  }), [selectedDate, startDate, endDate])

  // Filter entries by selected date
  const filteredEntries = useMemo(() => {
    if (!entries) return []
    if (!selectedDate) return entries
    return entries.filter((e) => e.date === selectedDate)
  }, [entries, selectedDate])

  // Daily view: flat list sorted by scheduled_start
  const dailyEntries = useMemo(() => {
    if (!selectedDate || !filteredEntries.length) return []
    return [...filteredEntries].sort((a, b) =>
      (a.scheduled_start ?? '').localeCompare(b.scheduled_start ?? ''),
    )
  }, [selectedDate, filteredEntries])

  // Group entries by teacher (uses filteredEntries so date filter applies)
  const grouped = useMemo(() => {
    if (!filteredEntries.length) return []
    const map = new Map<string, { name: string; entries: PracticeAttendanceEntry[] }>()
    for (const e of filteredEntries) {
      const key = e.teacher_ci
      if (!map.has(key)) {
        map.set(key, { name: e.teacher_name ?? key, entries: [] })
      }
      map.get(key)!.entries.push(e)
    }
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name))
  }, [filteredEntries])

  // Summary totals
  const totals = useMemo(() => {
    if (!summaries) return { scheduled: 0, attended: 0, absent: 0, rate: 0 }
    const scheduled = summaries.reduce((s, t) => s + t.total_scheduled, 0)
    const attended = summaries.reduce((s, t) => s + t.total_attended + t.total_late + t.total_justified, 0)
    const absent = summaries.reduce((s, t) => s + t.total_absent, 0)
    const rate = scheduled > 0 ? Math.round(attended / scheduled * 1000) / 10 : 0
    return { scheduled, attended, absent, rate }
  }, [summaries])

  function handleStatusChange(entry: PracticeAttendanceEntry, newStatus: string) {
    updateMutation.mutate({ id: entry.id, status: newStatus })
  }

  function handleObsSave(entryId: number) {
    updateMutation.mutate({ id: entryId, observation: obsValue.trim() === '' ? null : obsValue })
    setEditingObs(null)
    setObsValue('')
  }

  function handleGenerate() {
    generateMutation.mutate({
      month,
      year,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
    })
  }

  async function handleBulkStatus(newStatus: 'attended' | 'absent') {
    if (!dailyEntries.length) return
    setBulkLoading(true)
    try {
      for (const entry of dailyEntries) {
        if (entry.status !== newStatus) {
          await updateMutation.mutateAsync({ id: entry.id, status: newStatus })
        }
      }
    } finally {
      setBulkLoading(false)
    }
  }

  function handleStartChange(entry: PracticeAttendanceEntry, value: string) {
    const newStart = value || null
    updateMutation.mutate({ id: entry.id, actual_start: newStart })
    if (newStart && entry.scheduled_start) {
      const newStatus = autoSetStatus(entry.scheduled_start, newStart)
      if (newStatus && newStatus !== entry.status) {
        updateMutation.mutate({ id: entry.id, status: newStatus })
      }
    }
  }

  function handleEndChange(entry: PracticeAttendanceEntry, value: string) {
    updateMutation.mutate({ id: entry.id, actual_end: value || null })
  }

  function startEditingObs(entry: PracticeAttendanceEntry) {
    setEditingObs(entry.id)
    setObsValue(entry.observation ?? '')
  }

  function cancelEditingObs() {
    setEditingObs(null)
    setObsValue('')
  }

  async function handleExportPdf() {
    setPdfLoading(true)
    try {
      await downloadPracticeAttendancePdf({
        month, year,
        ...exportDateRange,
        teacher_ci: teacherFilter || undefined,
      })
    } finally { setPdfLoading(false) }
  }

  async function handleExportExcel() {
    setExcelLoading(true)
    try {
      await downloadPracticeAttendanceExcel({
        month, year,
        ...exportDateRange,
        teacher_ci: teacherFilter || undefined,
      })
    } finally { setExcelLoading(false) }
  }

  function navigateDate(direction: -1 | 1) {
    if (!selectedDate) return
    const d = new Date(selectedDate + 'T00:00:00')
    d.setDate(d.getDate() + direction)
    setSelectedDate(d.toISOString().split('T')[0])
  }

  if (isLoading) return <PracticeAttendanceSkeleton />

  const teacherItems = [
    { value: ALL_TEACHERS, label: 'Todos' },
    ...teachers.map((t) => ({ value: t.ci, label: t.name })),
  ]
  const yearItems = [currentYear - 1, currentYear, currentYear + 1].map((y) => ({ value: String(y), label: String(y) }))
  const bulkChanges = bulkTarget ? dailyEntries.filter((e) => e.status !== bulkTarget).length : 0

  return (
    <div className="space-y-6">
      <PageHeader
        title="Asistencia Practicas Internas"
        description="Registro manual de asistencia de docentes asistenciales"
        actions={
          <>
            <Button onClick={handleGenerate} loading={generateMutation.isPending}>
              <Calendar />
              Generar Asistencia
            </Button>
            <Button variant="outline" onClick={handleExportPdf} disabled={pdfLoading}>
              {pdfLoading ? <Loader2 className="animate-spin" /> : <FileText />}
              Exportar PDF
            </Button>
            <Button variant="outline" onClick={handleExportExcel} disabled={excelLoading}>
              {excelLoading ? <Loader2 className="animate-spin" /> : <FileSpreadsheet />}
              Exportar Excel
            </Button>
          </>
        }
      />

      {/* Controls */}
      <Card>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-6">
            <Field>
              <FieldLabel>Mes</FieldLabel>
              <Select value={String(month)} items={MONTH_ITEMS} onValueChange={(v) => setMonth(Number(v))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectPopup>
                  {MONTH_ITEMS.map((item) => (
                    <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
                  ))}
                </SelectPopup>
              </Select>
            </Field>

            <Field>
              <FieldLabel>Anio</FieldLabel>
              <Select value={String(year)} items={yearItems} onValueChange={(v) => setYear(Number(v))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectPopup>
                  {yearItems.map((item) => (
                    <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
                  ))}
                </SelectPopup>
              </Select>
            </Field>

            <Field>
              <FieldLabel>Desde</FieldLabel>
              <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </Field>

            <Field>
              <FieldLabel>Hasta</FieldLabel>
              <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </Field>

            <Field>
              <FieldLabel>Docente</FieldLabel>
              <Select
                value={teacherFilter || ALL_TEACHERS}
                items={teacherItems}
                onValueChange={(v) => setTeacherFilter(!v || v === ALL_TEACHERS ? '' : v)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectPopup className="max-h-64">
                  {teacherItems.map((item) => (
                    <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
                  ))}
                </SelectPopup>
              </Select>
            </Field>

            <Field className="relative">
              <FieldLabel>
                <CalendarDays className="size-3.5" aria-hidden="true" />
                Fecha Especifica
              </FieldLabel>
              <Input type="date" value={selectedDate} onChange={(e) => setSelectedDate(e.target.value)} />
              {selectedDate && (
                <Button
                  variant="ghost"
                  size="icon-xs"
                  aria-label="Limpiar fecha"
                  title="Limpiar fecha"
                  className="absolute -top-1.5 right-0"
                  onClick={() => setSelectedDate('')}
                >
                  <X />
                </Button>
              )}
            </Field>
          </div>

          {generateMutation.isSuccess && (
            <Alert variant="success">
              <CheckCircle />
              <AlertDescription>
                Se crearon {generateMutation.data.created} entradas de asistencia para {MONTH_NAMES[month]} {year}.
              </AlertDescription>
            </Alert>
          )}
          {generateMutation.isError && (
            <Alert variant="error" aria-live="assertive">
              <AlertTriangle />
              <AlertDescription>
                Error: {(generateMutation.error as Error)?.message ?? 'No se pudo generar la asistencia'}
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Summary cards */}
      {summaries && summaries.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 [&_p]:whitespace-normal">
          <StatCard icon={Users} title="Docentes" value={summaries.length} tone="primary" />
          <StatCard icon={Calendar} title="Clases Programadas" value={totals.scheduled} tone="info" />
          <StatCard icon={CheckCircle} title="Asistidas" value={totals.attended} subtitle={`${totals.rate}%`} tone="success" />
          <StatCard icon={XCircle} title="Ausentes" value={totals.absent} tone="destructive" />
        </div>
      )}

      {/* Per-teacher summary table */}
      {summaries && summaries.length > 0 && (
        <TableCard title="Resumen por Docente">
          <TableHeader>
            <TableRow>
              <TableHead>Docente</TableHead>
              <TableHead className="text-right">Programadas</TableHead>
              <TableHead className="text-right">Asistidas</TableHead>
              <TableHead className="text-right">Ausentes</TableHead>
              <TableHead className="text-right">Tardanzas</TableHead>
              <TableHead className="text-right">Justificadas</TableHead>
              <TableHead className="text-right">Hrs Prog.</TableHead>
              <TableHead className="text-right">Hrs Asist.</TableHead>
              <TableHead className="text-right">Tasa</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {summaries.map((s) => (
              <TableRow key={s.teacher_ci}>
                <TableCell className="font-medium">{s.teacher_name}</TableCell>
                <TableCell className="text-right tabular-nums">{s.total_scheduled}</TableCell>
                <TableCell className={cn('text-right font-medium tabular-nums', TONE_TEXT.success)}>{s.total_attended}</TableCell>
                <TableCell className={cn('text-right font-medium tabular-nums', TONE_TEXT.destructive)}>{s.total_absent}</TableCell>
                <TableCell className={cn('text-right tabular-nums', TONE_TEXT.warning)}>{s.total_late}</TableCell>
                <TableCell className={cn('text-right tabular-nums', TONE_TEXT.info)}>{s.total_justified}</TableCell>
                <TableCell className="text-right tabular-nums">{s.total_hours_scheduled}h</TableCell>
                <TableCell className="text-right tabular-nums">{s.total_hours_attended}h</TableCell>
                <TableCell className="text-right">
                  <StatusBadge
                    className="tabular-nums"
                    tone={s.attendance_rate >= 80 ? 'success' : s.attendance_rate >= 50 ? 'warning' : 'destructive'}
                  >
                    {s.attendance_rate}%
                  </StatusBadge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </TableCard>
      )}

      {/* ===== DAILY VIEW (when a specific date is selected) ===== */}
      {selectedDate && (
        <>
          {/* Daily view header with navigation */}
          <Card>
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="outline" size="sm" onClick={() => navigateDate(-1)}>
                  <ChevronLeft />
                  Dia anterior
                </Button>
                <div>
                  <h3 className="flex items-center gap-2 text-base font-semibold text-foreground">
                    <CalendarDays className="size-[18px] text-primary" aria-hidden="true" />
                    Asistencia del {formatFullDate(selectedDate)}
                  </h3>
                  <p className="text-sm text-muted-foreground tabular-nums">
                    {dailyEntries.length} clase{dailyEntries.length !== 1 ? 's' : ''} programada{dailyEntries.length !== 1 ? 's' : ''}
                  </p>
                </div>
                <Button variant="outline" size="sm" onClick={() => navigateDate(1)}>
                  Dia siguiente
                  <ChevronRight />
                </Button>
              </div>

              {/* Bulk action buttons */}
              {dailyEntries.length > 0 && (
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setBulkTarget('attended')}
                    disabled={bulkLoading || updateMutation.isPending}
                  >
                    {bulkLoading ? <Loader2 className="animate-spin" /> : <CheckCheck />}
                    Todos Asistieron
                  </Button>
                  <Button
                    variant="destructive-outline"
                    size="sm"
                    onClick={() => setBulkTarget('absent')}
                    disabled={bulkLoading || updateMutation.isPending}
                  >
                    {bulkLoading ? <Loader2 className="animate-spin" /> : <X />}
                    Todos Ausentes
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Daily flat table */}
          {dailyEntries.length === 0 ? (
            <Card>
              <EmptyState
                icon={Calendar}
                title="No hay clases programadas para esta fecha"
                description="Selecciona otra fecha o usa los botones de navegacion"
              />
            </Card>
          ) : (
            <TableCard>
              <TableHeader>
                <TableRow>
                  <TableHead>Docente</TableHead>
                  <TableHead>Materia</TableHead>
                  <TableHead>Grupo</TableHead>
                  <TableHead className="text-center">Origen</TableHead>
                  <TableHead className="text-center">Horario</TableHead>
                  <TableHead className="text-center">Estado</TableHead>
                  <TableHead className="text-center">Hora Llegada</TableHead>
                  <TableHead className="text-center">Hora Salida</TableHead>
                  <TableHead>Obs</TableHead>
                  <TableHead className="w-px"><span className="sr-only">Acciones</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dailyEntries.map((entry) => {
                  const cfg = STATUS_CONFIG[entry.status] ?? STATUS_CONFIG.absent
                  return (
                    <TableRow key={entry.id} className={cfg.rowTint}>
                      <TableCell className="font-medium">
                        {entry.teacher_name ?? entry.teacher_ci}
                      </TableCell>
                      <TableCell className="max-w-[200px] truncate" title={entry.subject ?? ''}>
                        {entry.subject}
                      </TableCell>
                      <TableCell className="text-muted-foreground">{entry.group_code}</TableCell>
                      <TableCell className="text-center">
                        <StatusBadge tone={entry.source_kind === 'published' ? 'primary' : 'neutral'}>
                          {entry.source_kind === 'published' ? 'Publicado' : 'Heredado'}
                        </StatusBadge>
                      </TableCell>
                      <TableCell className="text-center tabular-nums text-muted-foreground">
                        {formatTime(entry.scheduled_start)} - {formatTime(entry.scheduled_end)}
                      </TableCell>
                      <TableCell className="text-center">
                        <StatusSelect
                          entry={entry}
                          disabled={updateMutation.isPending}
                          onChange={(status) => handleStatusChange(entry, status)}
                        />
                      </TableCell>
                      <TableCell className="text-center">
                        <TimeField
                          label={`Hora de llegada de ${entry.teacher_name ?? entry.teacher_ci}`}
                          value={entry.actual_start}
                          onChange={(value) => handleStartChange(entry, value)}
                        />
                      </TableCell>
                      <TableCell className="text-center">
                        <TimeField
                          label={`Hora de salida de ${entry.teacher_name ?? entry.teacher_ci}`}
                          value={entry.actual_end}
                          onChange={(value) => handleEndChange(entry, value)}
                        />
                      </TableCell>
                      <TableCell>
                        <ObservationCell
                          entry={entry}
                          editing={editingObs === entry.id}
                          value={obsValue}
                          onValueChange={setObsValue}
                          onStart={() => startEditingObs(entry)}
                          onSave={() => handleObsSave(entry.id)}
                          onCancel={cancelEditingObs}
                        />
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          aria-label={`Eliminar asistencia de ${entry.teacher_name ?? entry.teacher_ci}`}
                          title="Eliminar"
                          className="text-muted-foreground hover:text-destructive-foreground"
                          onClick={() => setDeleteTarget(entry)}
                        >
                          <Trash2 />
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </TableCard>
          )}
        </>
      )}

      {/* ===== GROUPED VIEW (when no specific date is selected) ===== */}
      {!selectedDate && (
        <>
          {grouped.length === 0 && !isLoading && (
            <Card>
              <EmptyState
                icon={AlertTriangle}
                title="No hay registros de asistencia para este periodo"
                description='Usa el boton "Generar Asistencia" para crear los registros desde el horario'
              />
            </Card>
          )}

          {grouped.map((group) => (
            <TableCard
              key={group.name}
              title={group.name}
              description={`${group.entries.length} registros`}
            >
              <TableHeader>
                <TableRow>
                  <TableHead>Fecha</TableHead>
                  <TableHead>Materia</TableHead>
                  <TableHead>Grupo</TableHead>
                  <TableHead className="text-center">Origen</TableHead>
                  <TableHead className="text-center">Horario Prog.</TableHead>
                  <TableHead className="text-center">Estado</TableHead>
                  <TableHead className="text-center">Hora Real Inicio</TableHead>
                  <TableHead className="text-center">Hora Real Fin</TableHead>
                  <TableHead className="text-right">Hrs</TableHead>
                  <TableHead>Observacion</TableHead>
                  <TableHead className="w-px"><span className="sr-only">Acciones</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {group.entries.map((entry, idx, arr) => {
                  const cfg = STATUS_CONFIG[entry.status] ?? STATUS_CONFIG.absent
                  const showDateHeader = idx === 0 || arr[idx - 1].date !== entry.date
                  return (
                    <Fragment key={entry.id}>
                      {showDateHeader && (
                        <TableRow className="bg-muted/50 hover:bg-muted/50">
                          <TableCell colSpan={11} className="py-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            {formatDate(entry.date)}
                          </TableCell>
                        </TableRow>
                      )}
                      <TableRow className={cfg.rowTint}>
                        <TableCell className="tabular-nums">{formatDate(entry.date)}</TableCell>
                        <TableCell className="max-w-[200px] truncate" title={entry.subject ?? ''}>
                          {entry.subject}
                        </TableCell>
                        <TableCell className="text-muted-foreground">{entry.group_code}</TableCell>
                        <TableCell className="text-center">
                          <StatusBadge tone={entry.source_kind === 'published' ? 'primary' : 'neutral'}>
                            {entry.source_kind === 'published' ? 'Publicado' : 'Heredado'}
                          </StatusBadge>
                        </TableCell>
                        <TableCell className="text-center tabular-nums text-muted-foreground">
                          {formatTime(entry.scheduled_start)} - {formatTime(entry.scheduled_end)}
                        </TableCell>
                        <TableCell className="text-center">
                          <StatusSelect
                            entry={entry}
                            disabled={updateMutation.isPending}
                            onChange={(status) => handleStatusChange(entry, status)}
                          />
                        </TableCell>
                        <TableCell className="text-center">
                          <TimeField
                            label={`Hora real de inicio, ${formatDate(entry.date)} ${formatTime(entry.scheduled_start)}`}
                            value={entry.actual_start}
                            onChange={(value) => handleStartChange(entry, value)}
                          />
                        </TableCell>
                        <TableCell className="text-center">
                          <TimeField
                            label={`Hora real de fin, ${formatDate(entry.date)} ${formatTime(entry.scheduled_start)}`}
                            value={entry.actual_end}
                            onChange={(value) => handleEndChange(entry, value)}
                          />
                        </TableCell>
                        <TableCell className="text-right tabular-nums text-muted-foreground">{entry.academic_hours}h</TableCell>
                        <TableCell>
                          <ObservationCell
                            entry={entry}
                            editing={editingObs === entry.id}
                            value={obsValue}
                            onValueChange={setObsValue}
                            onStart={() => startEditingObs(entry)}
                            onSave={() => handleObsSave(entry.id)}
                            onCancel={cancelEditingObs}
                          />
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="icon-xs"
                            aria-label={`Eliminar asistencia de ${entry.teacher_name ?? entry.teacher_ci}, ${formatDate(entry.date)} ${formatTime(entry.scheduled_start)}`}
                            title="Eliminar"
                            className="text-muted-foreground hover:text-destructive-foreground"
                            onClick={() => setDeleteTarget(entry)}
                          >
                            <Trash2 />
                          </Button>
                        </TableCell>
                      </TableRow>
                    </Fragment>
                  )
                })}
              </TableBody>
            </TableCard>
          ))}
        </>
      )}

      {/* Pending state for inline saves */}
      {(updateMutation.isPending || deleteMutation.isPending || bulkLoading) && (
        <div
          role="status"
          className="fixed right-4 bottom-4 z-50 flex items-center gap-2 rounded-xl border bg-popover px-4 py-2 text-sm text-popover-foreground shadow-lg"
        >
          <Spinner className="size-4" />
          Guardando...
        </div>
      )}

      <ConfirmAlertDialog
        summary={
          deleteTarget
            ? {
                title: 'Eliminar registro de asistencia',
                confirmLabel: 'Eliminar',
                tone: 'destructive',
                rows: [
                  { label: 'Docente', value: deleteTarget.teacher_name ?? deleteTarget.teacher_ci },
                  { label: 'Fecha', value: formatDate(deleteTarget.date) },
                  { label: 'Materia', value: deleteTarget.subject ?? '—' },
                  { label: 'Horario', value: `${formatTime(deleteTarget.scheduled_start)} - ${formatTime(deleteTarget.scheduled_end)}` },
                ],
                consequence: 'El registro se elimina de forma permanente y deja de contar en la planilla de prácticas.',
              }
            : null
        }
        pending={deleteMutation.isPending}
        onConfirm={() => {
          if (!deleteTarget) return
          deleteMutation.mutate(deleteTarget.id, { onSettled: () => setDeleteTarget(null) })
        }}
        onCancel={() => setDeleteTarget(null)}
      />

      <ConfirmAlertDialog
        summary={
          bulkTarget
            ? {
                title: bulkTarget === 'attended' ? 'Marcar todos como asistieron' : 'Marcar todos como ausentes',
                confirmLabel: bulkTarget === 'attended' ? 'Todos Asistieron' : 'Todos Ausentes',
                tone: bulkTarget === 'absent' ? 'destructive' : 'default',
                rows: [
                  { label: 'Fecha', value: formatFullDate(selectedDate) },
                  { label: 'Clases del día', value: String(dailyEntries.length) },
                  { label: 'Registros que cambian', value: String(bulkChanges) },
                ],
                consequence: 'Se reemplaza el estado guardado de cada clase del día. Los registros se actualizan uno por uno.',
              }
            : null
        }
        pending={bulkLoading}
        onConfirm={async () => {
          if (!bulkTarget) return
          try {
            await handleBulkStatus(bulkTarget)
          } finally {
            setBulkTarget(null)
          }
        }}
        onCancel={() => setBulkTarget(null)}
      />
    </div>
  )
}
