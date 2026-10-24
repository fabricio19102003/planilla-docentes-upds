import { useState, useEffect, useRef, type ReactNode } from 'react'
import {
  ShieldCheck,
  Calendar,
  ClipboardCheck,
  Fingerprint,
  Loader2,
  AlertTriangle,
  Check,
  X,
  Users,
  Download,
  FileText,
  XCircle,
  Clock,
} from 'lucide-react'
import { useAttendanceAudit } from '@/api/hooks/useAttendance'
import { useTeachers } from '@/api/hooks/useTeachers'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { TableCard } from '@/components/shared/TableCard'
import type { Tone } from '@/components/shared/tones'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Progress, ProgressIndicator, ProgressTrack } from '@/components/ui/progress'
import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'
import { api } from '@/api/client'

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

const MONTH_ITEMS = Object.entries(MONTH_NAMES).map(([value, label]) => ({ value, label }))

const AUDIT_STATUS: Record<string, { label: string; tone: Tone; rowTint: string }> = {
  ATTENDED: { label: 'Asistido', tone: 'success', rowTint: '' },
  LATE: { label: 'Tardanza', tone: 'warning', rowTint: 'bg-warning/4' },
  ABSENT: { label: 'Ausente', tone: 'destructive', rowTint: 'bg-destructive/4' },
}
const AUDIT_STATUS_FALLBACK = { label: 'Sin salida', tone: 'info' as Tone, rowTint: '' }

const AUDIT_DETAIL_HEADERS = [
  'Fecha',
  'Día',
  'Materia',
  'Grupo',
  'Horario Programado',
  'Entrada Real',
  'Salida Real',
  'Estado',
  'Retraso',
  'Hrs',
  'Biométrico',
  'Explicación',
]

function AuditSection({ icon, title, aside, children }: { icon: ReactNode; title: ReactNode; aside?: ReactNode; children: ReactNode }) {
  return (
    <Card>
      <CardHeader className="flex items-center gap-2 border-b pb-4">
        <span className="text-muted-foreground" aria-hidden="true">{icon}</span>
        <CardTitle className="text-sm">{title}</CardTitle>
        {aside && <span className="ml-auto text-xs text-muted-foreground tabular-nums">{aside}</span>}
      </CardHeader>
      {children}
    </Card>
  )
}

function AuditSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Cargando auditoría">
      <Skeleton className="h-32 rounded-2xl" />
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-24 rounded-2xl" />
        ))}
      </div>
      <Skeleton className="h-64 rounded-2xl" />
    </div>
  )
}

function formatLocalDate(dateStr: string): string {
  if (!dateStr) return '—'
  // Parse as local date to avoid UTC offset shifting the day
  const [year, month, day] = dateStr.split('-')
  return `${day}/${month}/${year}`
}

interface AuditScheduleSlot {
  dia: string
  hora_inicio: string
  hora_fin: string
}

interface AuditSchedule {
  source_kind: 'legacy' | 'published'
  source_key: string
  designation_id: number | null
  published_schedule_assignment_id: number | null
  subject: string
  group_code: string
  semester: string
  slots?: AuditScheduleSlot[]
}

interface AuditAttendanceRow {
  source_kind: 'legacy' | 'published'
  source_key: string
  designation_id: number | null
  published_schedule_assignment_id: number | null
  date: string
  day_name: string
  subject: string
  group_code: string
  scheduled_start: string
  scheduled_end: string
  actual_entry: string | null
  actual_exit: string | null
  status: string
  late_minutes: number
  academic_hours: number
  has_biometric_link: boolean
  explanation: string
}

interface AuditBiometricRow {
  date: string
  entry_time: string | null
  exit_time: string | null
  worked_minutes: number | null
}

export function AttendanceAuditPage() {
  const now = new Date()
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year, setYear] = useState(now.getFullYear())
  const [teacherSearch, setTeacherSearch] = useState('')
  const [selectedCi, setSelectedCi] = useState('')
  const [showDropdown, setShowDropdown] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Batch audit state
  const [batchMode, setBatchMode] = useState<'all' | 'select'>('all')
  const [batchSelected, setBatchSelected] = useState<Set<string>>(new Set())
  const [batchSearch, setBatchSearch] = useState('')
  const [batchGenerating, setBatchGenerating] = useState(false)

  const { data: teachersData } = useTeachers({ page: 1, perPage: 500 })
  const teachers = teachersData?.items ?? []

  const filteredTeachers = teacherSearch
    ? teachers.filter(
        (t) =>
          t.full_name.toLowerCase().includes(teacherSearch.toLowerCase()) ||
          t.ci.includes(teacherSearch),
      )
    : []

  const { data, isLoading, isError, refetch, isFetching } = useAttendanceAudit(
    selectedCi,
    month,
    year,
    !!selectedCi,
  )

  const handleDownloadPDF = async () => {
    if (!selectedCi) return
    setDownloading(true)
    try {
      const response = await api.get(
        `/attendance/audit/${selectedCi}/pdf?month=${month}&year=${year}`,
        { responseType: 'blob' },
      )
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      const safeName = (data?.teacher_name ?? 'docente').replace(/\s+/g, '_')
      link.download = `Auditoria_Asistencia_${safeName}_${month}_${year}.pdf`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (e) {
      console.error('Error downloading audit PDF:', e)
    } finally {
      setDownloading(false)
    }
  }

  const handleBatchPDF = async () => {
    setBatchGenerating(true)
    try {
      const payload = {
        month,
        year,
        teacher_cis: batchMode === 'select' ? [...batchSelected] : null,
      }
      const response = await api.post('/attendance/audit/batch-pdf', payload, {
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      const mn = MONTH_NAMES[month] ?? month
      link.download =
        batchMode === 'all'
          ? `Auditoria_Asistencia_General_${mn}_${year}.pdf`
          : `Auditoria_Asistencia_${batchSelected.size}_docentes_${mn}_${year}.pdf`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (e) {
      console.error('Error generating batch audit:', e)
    } finally {
      setBatchGenerating(false)
    }
  }

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const batchTeachers = teachers.filter(
    (t) =>
      !t.ci.startsWith('TEMP-') &&
      (!batchSearch ||
        t.full_name.toLowerCase().includes(batchSearch.toLowerCase()) ||
        t.ci.includes(batchSearch)),
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Auditoría de Asistencia"
        description="Trazabilidad completa: horario asignado · datos biométricos · resultado del procesamiento"
      />

      {/* Filter controls */}
      <Card>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* Teacher searchable */}
            <div className="relative lg:col-span-2" ref={dropdownRef}>
              <Field>
                <FieldLabel>
                  <Users className="size-3.5" aria-hidden="true" />
                  Docente
                </FieldLabel>
                <div className="relative w-full">
                  <Input
                    type="text"
                    value={teacherSearch}
                    onChange={(e) => {
                      setTeacherSearch(e.target.value)
                      setShowDropdown(true)
                      if (!e.target.value) setSelectedCi('')
                    }}
                    onFocus={() => setShowDropdown(true)}
                    placeholder="Buscar por nombre o CI..."
                    inputClassName={selectedCi ? 'pr-9' : undefined}
                  />
                  {selectedCi && (
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      aria-label="Limpiar docente"
                      className="absolute top-1/2 right-1.5 -translate-y-1/2 text-muted-foreground"
                      onClick={() => {
                        setTeacherSearch('')
                        setSelectedCi('')
                      }}
                    >
                      <X />
                    </Button>
                  )}
                </div>
              </Field>
              {showDropdown && teacherSearch && filteredTeachers.length > 0 && (
                <div className="absolute z-50 mt-1 max-h-48 w-full overflow-y-auto rounded-lg border bg-popover p-1 text-popover-foreground shadow-lg">
                  {filteredTeachers.slice(0, 20).map((t) => (
                    <button
                      key={t.ci}
                      type="button"
                      onClick={() => {
                        setSelectedCi(t.ci)
                        setTeacherSearch(t.full_name)
                        setShowDropdown(false)
                      }}
                      className="flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left text-sm outline-none hover:bg-accent focus-visible:bg-accent"
                    >
                      <span className="font-medium text-foreground">{t.full_name}</span>
                      <span className="text-xs text-muted-foreground tabular-nums">{t.ci}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Month */}
            <Field>
              <FieldLabel>
                <Calendar className="size-3.5" aria-hidden="true" />
                Mes
              </FieldLabel>
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

            {/* Year */}
            <Field>
              <FieldLabel>
                <Calendar className="size-3.5" aria-hidden="true" />
                Año
              </FieldLabel>
              <Input
                type="number"
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                min={2020}
                max={2030}
                inputClassName="tabular-nums"
              />
            </Field>
          </div>
        </CardContent>
      </Card>

      {/* Batch Audit Export */}
      <Card>
        <CardHeader className="border-b pb-4">
          <CardTitle className="text-base">Reporte de Auditoría Masivo</CardTitle>
          <p className="text-sm text-muted-foreground">
            Generá un reporte PDF con la auditoría de múltiples docentes
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Toggle: All vs Select */}
          <div className="flex w-full flex-col gap-0.5 rounded-lg bg-muted p-0.5 sm:w-fit sm:flex-row">
            <Button
              variant={batchMode === 'all' ? 'outline' : 'ghost'}
              size="sm"
              className="flex-1 sm:flex-none"
              aria-pressed={batchMode === 'all'}
              onClick={() => setBatchMode('all')}
            >
              Todos los docentes
            </Button>
            <Button
              variant={batchMode === 'select' ? 'outline' : 'ghost'}
              size="sm"
              className="flex-1 sm:flex-none"
              aria-pressed={batchMode === 'select'}
              onClick={() => setBatchMode('select')}
            >
              Seleccionar docentes
            </Button>
          </div>

          {/* Teacher multi-select (only when batchMode === 'select') */}
          {batchMode === 'select' && (
            <div className="space-y-2">
              <Input
                type="text"
                placeholder="Buscar docente..."
                value={batchSearch}
                onChange={(e) => setBatchSearch(e.target.value)}
              />
              <div className="max-h-48 divide-y overflow-y-auto rounded-lg border">
                {batchTeachers.map((t) => (
                  <label
                    key={t.ci}
                    className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm hover:bg-accent"
                  >
                    <Checkbox
                      checked={batchSelected.has(t.ci)}
                      onCheckedChange={(checked) => {
                        const next = new Set(batchSelected)
                        if (checked) {
                          next.add(t.ci)
                        } else {
                          next.delete(t.ci)
                        }
                        setBatchSelected(next)
                      }}
                    />
                    <span className="font-medium text-foreground">{t.full_name}</span>
                    <span className="ml-auto text-xs text-muted-foreground tabular-nums">{t.ci}</span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-muted-foreground tabular-nums">{batchSelected.size} docente(s) seleccionado(s)</p>
            </div>
          )}

          {/* Generate button */}
          <Button
            disabled={batchGenerating || (batchMode === 'select' && batchSelected.size === 0)}
            onClick={handleBatchPDF}
          >
            {batchGenerating ? (
              <>
                <Loader2 className="animate-spin" /> Generando...
              </>
            ) : (
              <>
                <FileText /> Generar Reporte de Auditoría
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Empty state */}
      {!selectedCi && (
        <Card>
          <EmptyState
            icon={ShieldCheck}
            title="Seleccioná un docente para ver la auditoría"
            description="Vas a ver el horario asignado, los registros biométricos y el detalle del procesamiento"
          />
        </Card>
      )}

      {/* Loading */}
      {selectedCi && isLoading && <AuditSkeleton />}

      {/* Error */}
      {selectedCi && isError && (
        <Alert variant="error">
          <AlertTriangle />
          <AlertTitle>No se pudo cargar la auditoría.</AlertTitle>
          <AlertDescription>
            Verificá que el docente tenga datos procesados para el período seleccionado.
          </AlertDescription>
          <AlertAction>
            <Button variant="outline" size="sm" onClick={() => refetch()} loading={isFetching}>
              Reintentar
            </Button>
          </AlertAction>
        </Alert>
      )}

      {/* AUDIT DATA */}
      {data && !isLoading && (
        <>
          {/* Section A: Teacher Info + Summary */}
          <Card>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary/10 text-lg font-semibold text-primary">
                  {data.teacher_name?.[0] ?? '?'}
                </div>
                <div className="min-w-48 flex-1">
                  <h3 className="text-lg font-semibold text-foreground">
                    {data.teacher_name}
                  </h3>
                  <p className="text-sm text-muted-foreground tabular-nums">
                    CI: {data.teacher_ci} · {MONTH_NAMES[data.month as number]} {data.year}
                  </p>
                </div>
                <StatusBadge tone={data.has_biometric ? 'success' : 'warning'}>
                  {data.has_biometric
                    ? `${data.biometric_records_count} registros biométricos`
                    : 'Sin biométrico'}
                </StatusBadge>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDownloadPDF}
                  disabled={downloading}
                >
                  {downloading ? <Loader2 className="animate-spin" /> : <Download />}
                  Descargar PDF
                </Button>
              </div>

              {data.summary.total_slots > 0 && (
                <Progress value={data.summary.attendance_rate} aria-label="Tasa de asistencia">
                  <div className="flex items-center gap-3">
                    <ProgressTrack className="flex-1">
                      <ProgressIndicator />
                    </ProgressTrack>
                    <span className="text-xs font-semibold text-foreground tabular-nums">
                      {data.summary.attendance_rate}% asistencia
                    </span>
                  </div>
                </Progress>
              )}
            </CardContent>
          </Card>

          {/* Summary cards */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard icon={Check} title="Asistidos" value={data.summary.attended} tone="success" />
            <StatCard icon={Clock} title="Tardanzas" value={data.summary.late} tone="warning" />
            <StatCard icon={XCircle} title="Ausencias" value={data.summary.absent} tone="destructive" />
            <StatCard icon={AlertTriangle} title="Sin salida" value={data.summary.no_exit} tone="info" />
          </div>

          {/* Section B: Horario Asignado */}
          {data.schedule.length > 0 && (
            <AuditSection icon={<Calendar size={16} />} title="Horario Asignado">
              <CardContent className="divide-y py-0">
                {data.schedule.map((s: AuditSchedule) => (
                  <div key={s.source_key} className="flex flex-wrap items-center gap-2 py-3 text-sm first:pt-4 last:pb-4">
                    <span className="font-medium text-foreground">{s.subject}</span>
                    <Badge variant="outline">{s.group_code}</Badge>
                    <Badge variant="info">{s.semester}</Badge>
                    <div className="ml-auto flex flex-wrap gap-1">
                      {(s.slots ?? []).map((slot: AuditScheduleSlot, i: number) => (
                        <Badge key={i} variant="outline" className="tabular-nums">
                          {slot.dia} {slot.hora_inicio}–{slot.hora_fin}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ))}
              </CardContent>
            </AuditSection>
          )}

          {/* Section C: Detalle de Asistencia — AUDIT TABLE */}
          {data.attendance_detail.length === 0 ? (
            <AuditSection icon={<ClipboardCheck size={16} />} title="Detalle de Asistencia — Auditoría" aside="0 registros">
              <EmptyState
                icon={ClipboardCheck}
                title="Sin registros de asistencia procesados para este período"
              />
            </AuditSection>
          ) : (
            <TableCard
              title={
                <span className="flex items-center gap-2 text-sm">
                  <ClipboardCheck size={16} className="text-muted-foreground" aria-hidden="true" />
                  Detalle de Asistencia — Auditoría
                </span>
              }
              toolbar={
                <span className="text-xs font-normal text-muted-foreground tabular-nums">
                  {data.attendance_detail.length} registros
                </span>
              }
            >
              <TableHeader>
                <TableRow>
                  {AUDIT_DETAIL_HEADERS.map((h) => (
                    <TableHead key={h} className={cn(h === 'Retraso' || h === 'Hrs' ? 'text-right' : undefined)}>
                      {h}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.attendance_detail.map((row: AuditAttendanceRow) => {
                  const status = AUDIT_STATUS[row.status] ?? AUDIT_STATUS_FALLBACK
                  return (
                    <TableRow key={`${row.source_key}:${row.date}:${row.scheduled_start}`} className={status.rowTint}>
                      <TableCell className="font-medium tabular-nums">{formatLocalDate(row.date)}</TableCell>
                      <TableCell className="capitalize text-muted-foreground">{row.day_name}</TableCell>
                      <TableCell className="max-w-[140px] truncate" title={row.subject}>
                        {row.subject}
                      </TableCell>
                      <TableCell className="text-muted-foreground">{row.group_code}</TableCell>
                      <TableCell className="tabular-nums">
                        {row.scheduled_start} - {row.scheduled_end}
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {row.actual_entry ? (
                          <span className={row.status === 'LATE' ? 'font-semibold text-warning-foreground' : 'text-success-foreground'}>
                            {row.actual_entry}
                          </span>
                        ) : (
                          <span className="text-destructive-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {row.actual_exit ? (
                          <span className="text-muted-foreground">{row.actual_exit}</span>
                        ) : (
                          <span className="text-muted-foreground/60">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <StatusBadge tone={status.tone}>{status.label}</StatusBadge>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {row.late_minutes > 0 ? (
                          <span className="font-semibold text-warning-foreground">{row.late_minutes} min</span>
                        ) : (
                          '—'
                        )}
                      </TableCell>
                      <TableCell className="text-right font-semibold tabular-nums">{row.academic_hours}h</TableCell>
                      <TableCell>
                        {row.has_biometric_link ? (
                          <span className="text-xs text-success-foreground">✓ Vinculado</span>
                        ) : (
                          <span className="text-xs text-destructive-foreground">✗ Sin registro</span>
                        )}
                      </TableCell>
                      <TableCell className="min-w-64 max-w-80 whitespace-normal text-xs leading-snug text-muted-foreground">
                        {row.explanation}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </TableCard>
          )}

          {/* Section D: Raw Biometric Records */}
          {data.biometric_raw.length > 0 ? (
            <TableCard
              title={
                <span className="flex items-center gap-2 text-sm">
                  <Fingerprint size={16} className="text-muted-foreground" aria-hidden="true" />
                  Registros Biométricos Originales ({data.biometric_raw.length})
                </span>
              }
            >
              <TableHeader>
                <TableRow>
                  <TableHead>Fecha</TableHead>
                  <TableHead>Entrada</TableHead>
                  <TableHead>Salida</TableHead>
                  <TableHead className="text-right">Minutos Trabajados</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.biometric_raw.map((bio: AuditBiometricRow, i: number) => (
                  <TableRow key={i}>
                    <TableCell className="tabular-nums">{formatLocalDate(bio.date)}</TableCell>
                    <TableCell className="tabular-nums">{bio.entry_time ?? '—'}</TableCell>
                    <TableCell className="tabular-nums">{bio.exit_time ?? '—'}</TableCell>
                    <TableCell className="text-right tabular-nums text-muted-foreground">
                      {bio.worked_minutes != null ? `${bio.worked_minutes} min` : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </TableCard>
          ) : (
            <AuditSection icon={<Fingerprint size={16} />} title={`Registros Biométricos Originales (${data.biometric_raw.length})`}>
              <EmptyState icon={Fingerprint} title="Sin registros biométricos para este período" />
            </AuditSection>
          )}
        </>
      )}
    </div>
  )
}
