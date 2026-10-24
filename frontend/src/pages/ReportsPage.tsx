/* eslint-disable @typescript-eslint/no-explicit-any -- Report preview payloads are heterogeneous by report type; preserving current runtime shapes is safer than a broad typing refactor here. */
import { useState, useEffect } from 'react'
import {
  FileText,
  Download,
  Eye,
  BarChart3,
  Users,
  DollarSign,
  ClipboardCheck,
  CheckCircle,
  History,
  X,
  AlertTriangle,
  AlertCircle,
  ArrowLeftRight,
  CalendarDays,
  Clock,
  Percent,
  Hash,
  UserCheck,
  UserX,
  Timer,
  Receipt,
  Scale,
  Calculator,
  BookOpen,
  ListChecks,
  FileSearch,
  type LucideIcon,
} from 'lucide-react'
import {
  useReportPreview,
  useGenerateReport,
  useReportHistory,
  downloadReport,
  type ReportFilters,
  type ReportInfo,
} from '@/api/hooks/useReports'
import { useTeachers } from '@/api/hooks/useTeachers'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardDescription, CardPanel } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { TableCard } from '@/components/shared/TableCard'
import { TONE_CHIP, TONE_TEXT, type Tone } from '@/components/shared/tones'
import { cn } from '@/lib/utils'

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

const MONTH_ITEMS = Object.entries(MONTH_NAMES).map(([value, label]) => ({ value, label }))

const REPORT_TYPES: Record<string, { label: string; icon: LucideIcon; tone: Tone; hint: string }> = {
  financial: { label: 'Financiero', icon: DollarSign, tone: 'primary', hint: 'Pagos por docente/designación' },
  attendance: { label: 'Asistencia', icon: ClipboardCheck, tone: 'info', hint: 'Registros de asistencia detallados' },
  comparative: { label: 'Comparativo', icon: BarChart3, tone: 'neutral', hint: 'Evolución mensual del año' },
  roster: { label: 'Plantel Docente', icon: Users, tone: 'success', hint: 'Lista completa del plantel docente' },
  incidence: { label: 'Incidencias', icon: AlertTriangle, tone: 'destructive', hint: 'Ausencias, tardanzas y sin biométrico' },
  reconciliation: { label: 'Conciliación', icon: ArrowLeftRight, tone: 'warning', hint: 'Designación vs asistencia real' },
}

type ReportType = 'financial' | 'attendance' | 'comparative' | 'roster' | 'incidence' | 'reconciliation'
const REPORT_TYPE_ENTRIES = Object.entries(REPORT_TYPES) as [ReportType, (typeof REPORT_TYPES)[string]][]

/** Scrolls the preview tables vertically while the header stays visible; horizontal scroll comes from Table. */
const PREVIEW_SCROLL = 'max-h-96 [&_[data-slot=table-container]]:min-h-0 [&_[data-slot=table-container]]:overflow-y-auto'
const STICKY_HEAD = 'sticky top-0 z-10 bg-card'
const NUM = 'text-right tabular-nums'

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function formatMoney(value: number): string {
  return value.toLocaleString('es-BO', { minimumFractionDigits: 2 })
}

function ReportTypeBadge({ type }: { type: string }) {
  const cfg = REPORT_TYPES[type]
  if (!cfg) return <StatusBadge>{type}</StatusBadge>
  return <StatusBadge tone={cfg.tone}>{cfg.label}</StatusBadge>
}

interface HeadColumn {
  label: string
  numeric?: boolean
}

function PreviewHead({ columns }: { columns: HeadColumn[] }) {
  return (
    <TableHeader>
      <TableRow className="hover:bg-transparent">
        {columns.map(({ label, numeric }) => (
          <TableHead key={label} className={cn(STICKY_HEAD, numeric && NUM)}>
            {label}
          </TableHead>
        ))}
      </TableRow>
    </TableHeader>
  )
}

function StatGrid({ className, children }: { className: string; children: React.ReactNode }) {
  return <div className={cn('grid gap-3', className)}>{children}</div>
}

// ── Financial Preview ────────────────────────────────────────────────────────

function FinancialPreview({ data }: { data: any }) {
  return (
    <div className="space-y-4">
      <StatGrid className="grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Users} title="Docentes" value={data.total_teachers} />
        <StatCard icon={BookOpen} title="Designaciones" value={data.total_designations} />
        <StatCard icon={Clock} title="Hrs Asignadas" value={`${data.total_base_hours}h`} tone="info" />
        <StatCard icon={UserX} title="Hrs Ausencia" value={`${data.total_absent_hours}h`} tone="warning" />
        <StatCard icon={Timer} title="Hrs a Pagar" value={`${data.total_payable_hours}h`} tone="info" />
        <StatCard icon={Receipt} title="Total Bruto (Bs)" value={formatMoney(data.total_gross_payment ?? data.total_payment)} />
        <StatCard icon={Percent} title="Ret. 13% (Bs)" value={formatMoney(data.total_retention ?? 0)} tone="warning" />
        <StatCard icon={Calculator} title="Total Neto (Bs)" value={formatMoney(data.total_payment)} tone="success" />
      </StatGrid>

      <TableCard className={PREVIEW_SCROLL}>
        <PreviewHead
          columns={[
            { label: 'Docente' }, { label: 'Materia' }, { label: 'Grupo' }, { label: 'Sem.' },
            { label: 'Hrs Base', numeric: true }, { label: 'Ausencias', numeric: true }, { label: 'Hrs Pagar', numeric: true },
            { label: 'Bruto (Bs)', numeric: true }, { label: 'Ret. 13%', numeric: true }, { label: 'Neto (Bs)', numeric: true },
          ]}
        />
        <TableBody>
          {data.rows.map((row: any) => (
            <TableRow key={`${row.teacher_ci}-${row.subject}-${row.group_code}`}>
              <TableCell className="max-w-[180px] truncate font-medium text-foreground">{row.teacher_name}</TableCell>
              <TableCell className="max-w-[160px] truncate">{row.subject}</TableCell>
              <TableCell className="text-muted-foreground">{row.group_code}</TableCell>
              <TableCell className="text-muted-foreground">{row.semester}</TableCell>
              <TableCell className={NUM}>{row.base_monthly_hours}h</TableCell>
              <TableCell className={NUM}>
                {row.absent_hours > 0
                  ? <span className={cn('font-medium', TONE_TEXT.destructive)}>-{row.absent_hours}h</span>
                  : <span className="text-muted-foreground">0h</span>}
              </TableCell>
              <TableCell className={cn(NUM, 'font-semibold text-foreground')}>{row.payable_hours}h</TableCell>
              <TableCell className={NUM}>{row.calculated_payment?.toFixed(2) ?? '—'}</TableCell>
              <TableCell className={NUM}>
                {(row.retention_amount ?? 0) > 0
                  ? <span className={TONE_TEXT.warning}>-{row.retention_amount.toFixed(2)}</span>
                  : <span className="text-muted-foreground">—</span>}
              </TableCell>
              <TableCell className={cn(NUM, 'font-semibold text-foreground')}>
                {(row.final_payment ?? row.calculated_payment)?.toFixed(2) ?? '—'}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </TableCard>
    </div>
  )
}

// ── Attendance Preview ───────────────────────────────────────────────────────

function AttendancePreview({ data }: { data: any }) {
  const STATUS_LABELS: Record<string, string> = {
    ATTENDED: 'Asistido', JUSTIFIED: 'Justificado', LATE: 'Tardanza', ABSENT: 'Ausente', NO_EXIT: 'Sin salida',
  }
  const STATUS_TONES: Record<string, Tone> = {
    ATTENDED: 'success',
    JUSTIFIED: 'info',
    LATE: 'warning',
    ABSENT: 'destructive',
    NO_EXIT: 'info',
  }

  return (
    <div className="space-y-4">
      <StatGrid className="grid-cols-1 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard icon={Hash} title="Total Registros" value={data.total_records} />
        <StatCard icon={UserCheck} title="Asistidos" value={data.attended} tone="success" />
        <StatCard icon={Timer} title="Tardanzas" value={data.late} tone="warning" />
        <StatCard icon={UserX} title="Ausencias" value={data.absent} tone="destructive" />
        <StatCard icon={Percent} title="Tasa Asistencia" value={`${data.attendance_rate}%`} tone="info" />
      </StatGrid>

      <TableCard className={PREVIEW_SCROLL}>
        <PreviewHead
          columns={[
            { label: 'Fecha' }, { label: 'Docente' }, { label: 'Tipo' }, { label: 'Estado' },
            { label: 'Entrada' }, { label: 'Salida' }, { label: 'Hrs Acad.', numeric: true },
          ]}
        />
        <TableBody>
          {data.records_sample.map((rec: any) => (
            <TableRow key={`${rec.record_kind}:${rec.source_key}:${rec.date}:${rec.scheduled_start}`}>
              <TableCell className="tabular-nums text-muted-foreground">
                {rec.date ? new Date(rec.date).toLocaleDateString('es-BO', { day: '2-digit', month: '2-digit' }) : '—'}
              </TableCell>
              <TableCell className="font-mono text-xs">{rec.teacher_ci}</TableCell>
              <TableCell className="text-muted-foreground">{rec.record_kind === 'practice' ? 'Práctica' : 'Regular'}</TableCell>
              <TableCell>
                <StatusBadge tone={STATUS_TONES[rec.status] ?? 'neutral'}>
                  {STATUS_LABELS[rec.status] ?? rec.status}
                </StatusBadge>
              </TableCell>
              <TableCell className="tabular-nums text-muted-foreground">{rec.check_in ?? '—'}</TableCell>
              <TableCell className="tabular-nums text-muted-foreground">{rec.check_out ?? '—'}</TableCell>
              <TableCell className={cn(NUM, 'font-semibold text-foreground')}>{rec.academic_hours ?? 0}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </TableCard>
      {data.total_records > 50 && (
        <p className="text-center text-xs text-muted-foreground">
          Mostrando 50 de {data.total_records} registros — generá el PDF para ver todos
        </p>
      )}
    </div>
  )
}

// ── Comparative Preview ──────────────────────────────────────────────────────

function ComparativePreview({ data }: { data: any }) {
  return (
    <div className="space-y-4">
      <StatGrid className="grid-cols-1 sm:grid-cols-2">
        <StatCard icon={CalendarDays} title="Meses con datos" value={data.months.length} />
        <StatCard icon={Calculator} title="Total Anual (Bs)" value={formatMoney(data.grand_total)} tone="success" />
      </StatGrid>

      <TableCard>
        <PreviewHead
          columns={[
            { label: 'Mes' }, { label: 'Docentes', numeric: true }, { label: 'Hrs Asignadas', numeric: true },
            { label: 'Hrs Ausencia', numeric: true }, { label: 'Hrs a Pagar', numeric: true }, { label: 'Total (Bs)', numeric: true },
          ]}
        />
        <TableBody>
          {data.months.map((md: any) => (
            <TableRow key={md.month}>
              <TableCell className="font-medium text-foreground">{md.month_name}</TableCell>
              <TableCell className={NUM}>{md.teachers}</TableCell>
              <TableCell className={NUM}>{md.base_hours}h</TableCell>
              <TableCell className={NUM}>
                {md.absent_hours > 0
                  ? <span className={cn('font-medium', TONE_TEXT.destructive)}>{md.absent_hours}h</span>
                  : <span className="text-muted-foreground">0h</span>}
              </TableCell>
              <TableCell className={NUM}>{md.payable_hours}h</TableCell>
              <TableCell className={cn(NUM, 'font-semibold text-foreground')}>{formatMoney(md.total_payment)}</TableCell>
            </TableRow>
          ))}
          <TableRow className="bg-muted/40 hover:bg-muted/40">
            <TableCell className="font-semibold text-foreground" colSpan={5}>TOTAL ANUAL</TableCell>
            <TableCell className={cn(NUM, 'font-semibold text-foreground')}>{formatMoney(data.grand_total)}</TableCell>
          </TableRow>
        </TableBody>
      </TableCard>
    </div>
  )
}

// ── Roster Preview ───────────────────────────────────────────────────────────

function RosterPreview({ data }: { data: any }) {
  return (
    <div className="space-y-4">
      <StatGrid className="grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Users} title="Total Docentes" value={data.total_teachers} />
        <StatCard icon={FileText} title="Con NIT" value={data.with_nit} tone="info" />
        <StatCard icon={Percent} title="Con Retención" value={data.with_retention} tone="warning" />
        <StatCard icon={ListChecks} title="Vista previa (máx. 50)" value={data.rows.length} tone="success" />
      </StatGrid>

      <TableCard className={PREVIEW_SCROLL}>
        <PreviewHead
          columns={[
            { label: 'Nº', numeric: true }, { label: 'Nombre Completo' }, { label: 'C.I.' }, { label: 'Teléfono' },
            { label: 'Email' }, { label: 'NIT/Ret.' }, { label: 'Materias', numeric: true },
          ]}
        />
        <TableBody>
          {data.rows.map((row: any, i: number) => (
            <TableRow key={row.ci}>
              <TableCell className={cn(NUM, 'text-muted-foreground')}>{i + 1}</TableCell>
              <TableCell className="max-w-[200px] truncate font-medium text-foreground">{row.full_name}</TableCell>
              <TableCell className="font-mono text-xs">{row.ci}</TableCell>
              <TableCell className="text-muted-foreground">{row.phone ?? '—'}</TableCell>
              <TableCell className="max-w-[180px] truncate text-muted-foreground">{row.email ?? '—'}</TableCell>
              <TableCell>
                {row.invoice_retention?.toUpperCase() === 'RETENCION' ? (
                  <StatusBadge tone="warning">RET</StatusBadge>
                ) : row.nit ? (
                  <span className="text-xs tabular-nums text-muted-foreground">{row.nit}</span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </TableCell>
              <TableCell className={NUM}>{row.designation_count}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </TableCard>
      {data.total_teachers > 50 && (
        <p className="text-center text-xs text-muted-foreground">
          Mostrando 50 de {data.total_teachers} docentes — generá el PDF para ver todos
        </p>
      )}
    </div>
  )
}

// ── Incidence Preview ────────────────────────────────────────────────────────

function IncidencePreview({ data }: { data: any }) {
  return (
    <div className="space-y-6">
      <StatGrid className="grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Hash} title="Total Registros" value={data.total_records} />
        <StatCard icon={UserX} title="Ausencias" value={data.total_absences} tone="destructive" />
        <StatCard icon={Timer} title="Tardanzas" value={data.total_lates} tone="warning" />
        <StatCard icon={FileSearch} title="Sin Biométrico" value={data.teachers_without_biometric} tone="info" />
      </StatGrid>

      <section className="space-y-2">
        <h4 className={cn('text-sm font-semibold', TONE_TEXT.destructive)}>Docentes con más ausencias</h4>
        {data.top_absentees?.length > 0 ? (
          <TableCard className={cn(PREVIEW_SCROLL, 'max-h-60')}>
            <PreviewHead
              columns={[
                { label: 'Nº', numeric: true }, { label: 'Docente' }, { label: 'Ausencias', numeric: true },
                { label: 'Total Clases', numeric: true }, { label: '% Ausencia', numeric: true },
              ]}
            />
            <TableBody>
              {data.top_absentees.map((row: any, i: number) => {
                const pct = row.total_slots > 0 ? (row.absences / row.total_slots * 100).toFixed(1) : '0'
                return (
                  <TableRow key={row.teacher_ci}>
                    <TableCell className={cn(NUM, 'text-muted-foreground')}>{i + 1}</TableCell>
                    <TableCell className="max-w-[200px] truncate font-medium text-foreground">{row.teacher_name}</TableCell>
                    <TableCell className={cn(NUM, 'font-semibold', TONE_TEXT.destructive)}>{row.absences}</TableCell>
                    <TableCell className={NUM}>{row.total_slots}</TableCell>
                    <TableCell className={cn(NUM, 'font-medium')}>{pct}%</TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </TableCard>
        ) : (
          <p className="text-sm italic text-muted-foreground">Sin ausencias registradas en el período.</p>
        )}
      </section>

      <section className="space-y-2">
        <h4 className={cn('text-sm font-semibold', TONE_TEXT.warning)}>Docentes con más tardanzas</h4>
        {data.top_lates?.length > 0 ? (
          <TableCard className={cn(PREVIEW_SCROLL, 'max-h-60')}>
            <PreviewHead
              columns={[
                { label: 'Nº', numeric: true }, { label: 'Docente' }, { label: 'Tardanzas', numeric: true },
                { label: 'Min. Promedio', numeric: true },
              ]}
            />
            <TableBody>
              {data.top_lates.map((row: any, i: number) => {
                const avgMin = row.lates > 0 ? Math.floor(row.late_minutes_total / row.lates) : 0
                return (
                  <TableRow key={row.teacher_ci}>
                    <TableCell className={cn(NUM, 'text-muted-foreground')}>{i + 1}</TableCell>
                    <TableCell className="max-w-[200px] truncate font-medium text-foreground">{row.teacher_name}</TableCell>
                    <TableCell className={cn(NUM, 'font-semibold', TONE_TEXT.warning)}>{row.lates}</TableCell>
                    <TableCell className={NUM}>{avgMin} min</TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </TableCard>
        ) : (
          <p className="text-sm italic text-muted-foreground">Sin tardanzas registradas en el período.</p>
        )}
      </section>

      <section className="space-y-2">
        <h4 className={cn('text-sm font-semibold', TONE_TEXT.info)}>Docentes sin biométrico</h4>
        {data.without_biometric?.length > 0 ? (
          <TableCard className={cn(PREVIEW_SCROLL, 'max-h-60')}>
            <PreviewHead columns={[{ label: 'Nº', numeric: true }, { label: 'Docente' }, { label: 'CI' }]} />
            <TableBody>
              {data.without_biometric.map((row: any, i: number) => (
                <TableRow key={row.teacher_ci}>
                  <TableCell className={cn(NUM, 'text-muted-foreground')}>{i + 1}</TableCell>
                  <TableCell className="max-w-[220px] truncate font-medium text-foreground">{row.teacher_name}</TableCell>
                  <TableCell className="font-mono text-xs">{row.teacher_ci}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </TableCard>
        ) : (
          <p className={cn('text-sm font-medium', TONE_TEXT.success)}>Todos los docentes tienen registro biométrico.</p>
        )}
      </section>
    </div>
  )
}

// ── Reconciliation Preview ───────────────────────────────────────────────────

function ReconciliationPreview({ data }: { data: any }) {
  const SEVERITY: Record<string, { row: string; tone: Tone; label: string }> = {
    high: { row: 'bg-destructive/4', tone: 'destructive', label: 'Alta' },
    medium: { row: 'bg-warning/4', tone: 'warning', label: 'Media' },
  }

  return (
    <div className="space-y-4">
      <StatGrid className="grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Users} title="Total Docentes" value={data.total_teachers} />
        <StatCard icon={Scale} title="Discrepancias" value={data.total_discrepancies} tone="info" />
        <StatCard icon={AlertTriangle} title="Severidad Alta" value={data.high_severity} tone="destructive" />
        <StatCard icon={AlertCircle} title="Severidad Media" value={data.medium_severity} tone="warning" />
      </StatGrid>

      {data.discrepancies?.length > 0 ? (
        <TableCard className={PREVIEW_SCROLL}>
          <PreviewHead
            columns={[
              { label: 'Nº', numeric: true }, { label: 'Docente' }, { label: 'Fuente' }, { label: 'Tipo' },
              { label: 'Descripción' }, { label: 'Hrs Esperadas', numeric: true }, { label: 'Hrs Reales', numeric: true },
              { label: 'Severidad' },
            ]}
          />
          <TableBody>
            {data.discrepancies.map((row: any, i: number) => {
              const sev = SEVERITY[row.severity] ?? SEVERITY.medium
              return (
                <TableRow key={`${row.teacher_ci ?? row.teacher_name}:${row.source}:${row.type}:${(row.source_keys ?? []).join(',')}`} className={sev.row}>
                  <TableCell className={cn(NUM, 'text-muted-foreground')}>{i + 1}</TableCell>
                  <TableCell className="max-w-[180px] truncate font-medium text-foreground">{row.teacher_name}</TableCell>
                  <TableCell className="text-muted-foreground">{row.source ?? '—'}</TableCell>
                  <TableCell>{row.type}</TableCell>
                  <TableCell className="max-w-[220px] truncate text-muted-foreground">{row.description}</TableCell>
                  <TableCell className={NUM}>{row.expected_hours}h</TableCell>
                  <TableCell className={cn(NUM, 'font-medium', row.actual_hours < row.expected_hours * 0.5 ? TONE_TEXT.destructive : 'text-foreground')}>
                    {row.actual_hours}h
                  </TableCell>
                  <TableCell>
                    <StatusBadge tone={sev.tone}>{row.severity === 'high' ? 'Alta' : 'Media'}</StatusBadge>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </TableCard>
      ) : (
        <Alert variant="success">
          <CheckCircle />
          <AlertDescription>
            ¡Sin discrepancias! Todos los docentes tienen registros de asistencia consistentes con sus designaciones.
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}

function PreviewSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-label="Cargando vista previa">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((n) => <Skeleton key={n} className="h-20 rounded-2xl" />)}
      </div>
      <Skeleton className="h-48 w-full rounded-2xl" />
    </div>
  )
}

// ── Main Page ────────────────────────────────────────────────────────────────

export function ReportsPage() {
  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1

  const [reportType, setReportType] = useState<ReportType>('financial')
  const [month, setMonth] = useState<number>(currentMonth)
  const [year, setYear] = useState<number>(currentYear)
  const [semester, setSemester] = useState<string>('')
  const [groupCode, setGroupCode] = useState<string>('')
  const [subject, setSubject] = useState<string>('')
  const [previewEnabled, setPreviewEnabled] = useState(false)
  const [lastGenerated, setLastGenerated] = useState<ReportInfo | null>(null)

  // Teacher search state
  const [teacherSearch, setTeacherSearch] = useState('')
  const [showTeacherDropdown, setShowTeacherDropdown] = useState(false)
  const [filters, setFilters] = useState<ReportFilters>({
    report_type: reportType,
    month: currentMonth,
    year: currentYear,
  })

  // Teachers for dropdown
  const { data: teachersData } = useTeachers({ perPage: 200 })
  const teachers = teachersData?.items ?? []

  // Filter teachers by search term
  const filteredTeachers = teachers.filter(t => {
    if (!teacherSearch) return true
    const term = teacherSearch.toLowerCase()
    return t.full_name.toLowerCase().includes(term) || t.ci.includes(term)
  })

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest('.teacher-search-container')) {
        setShowTeacherDropdown(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Keep filters in sync with month/year/semester/groupCode/subject/reportType
  useEffect(() => {
    const isRoster = reportType === 'roster'
    const isSimple = reportType === 'incidence' || reportType === 'reconciliation'
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Filters are intentionally synchronized from report controls before preview/generation.
    setFilters(f => ({
      ...f,
      report_type: reportType,
      month: (!isRoster && reportType !== 'comparative') || isSimple ? month : undefined,
      year: (!isRoster || isSimple) ? year : undefined,
      semester: (!isRoster && !isSimple) ? (semester || undefined) : undefined,
      group_code: (!isRoster && !isSimple) ? (groupCode || undefined) : undefined,
      subject: (!isRoster && !isSimple) ? (subject || undefined) : undefined,
    }))
  }, [reportType, month, year, semester, groupCode, subject])

  const { data: previewData, isLoading: previewLoading, isError: previewError, isFetching: previewFetching, refetch: refetchPreview } = useReportPreview(filters, previewEnabled)
  const generateReport = useGenerateReport()
  const { data: history, isLoading: historyLoading } = useReportHistory()

  const handlePreview = () => {
    setPreviewEnabled(true)
  }

  const handleGenerate = () => {
    setLastGenerated(null)
    generateReport.mutate(filters, {
      onSuccess: (data) => {
        setLastGenerated(data)
      },
    })
  }

  const handleTypeChange = (type: ReportType) => {
    setReportType(type)
    setPreviewEnabled(false)
    setFilters(f => ({ ...f, report_type: type }))
  }

  const needsMonth = reportType !== 'comparative' && reportType !== 'roster'
  const isSimpleReport = reportType === 'incidence' || reportType === 'reconciliation'

  const monthField = (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="report-month">Mes</Label>
      <Select
        value={String(month)}
        items={MONTH_ITEMS}
        onValueChange={(value) => { setMonth(Number(value)); setPreviewEnabled(false) }}
      >
        <SelectTrigger id="report-month"><SelectValue /></SelectTrigger>
        <SelectPopup>
          {MONTH_ITEMS.map(({ value, label }) => (
            <SelectItem key={value} value={value}>{label}</SelectItem>
          ))}
        </SelectPopup>
      </Select>
    </div>
  )

  const yearField = (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="report-year">Año</Label>
      <Input
        id="report-year"
        type="number"
        value={year}
        onChange={(e) => { setYear(Number(e.target.value)); setPreviewEnabled(false) }}
        min={2020}
        max={2030}
        inputClassName="tabular-nums"
      />
    </div>
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reportes"
        description="Generá reportes PDF financieros, de asistencia y comparativos"
      />

      {/* Report Type Selector */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Tipo de Reporte</CardTitle>
          <CardDescription>Seleccioná el tipo de análisis que necesitás</CardDescription>
        </CardHeader>
        <CardPanel>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {REPORT_TYPE_ENTRIES.map(([type, cfg]) => {
              const Icon = cfg.icon
              const isActive = reportType === type
              return (
                <button
                  key={type}
                  type="button"
                  aria-pressed={isActive}
                  onClick={() => handleTypeChange(type)}
                  className={cn(
                    'flex items-start gap-3 rounded-xl border p-3 text-left transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    isActive ? 'border-primary bg-primary/5 shadow-xs' : 'border-border hover:bg-accent/50',
                  )}
                >
                  <span className={cn('flex size-9 shrink-0 items-center justify-center rounded-lg', isActive ? TONE_CHIP.primary : TONE_CHIP[cfg.tone])}>
                    <Icon className="size-4" aria-hidden="true" />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold text-foreground">{cfg.label}</span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">{cfg.hint}</span>
                  </span>
                </button>
              )
            })}
          </div>
        </CardPanel>
      </Card>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filtros</CardTitle>
        </CardHeader>
        <CardPanel>
          {reportType === 'roster' ? (
            <p className="text-sm text-muted-foreground">
              El reporte de Plantel Docente incluye todos los docentes registrados. No requiere filtros adicionales.
            </p>
          ) : isSimpleReport ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {monthField}
              {yearField}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {needsMonth && monthField}
              {yearField}

              {/* Teacher — searchable */}
              <div className="teacher-search-container relative flex flex-col gap-1.5">
                <Label htmlFor="report-teacher">Docente (opcional)</Label>
                <div className="relative">
                  <Input
                    id="report-teacher"
                    type="text"
                    value={teacherSearch}
                    onChange={(e) => {
                      setTeacherSearch(e.target.value)
                      setShowTeacherDropdown(true)
                      setPreviewEnabled(false)
                      if (!e.target.value) setFilters(f => ({ ...f, teacher_ci: undefined }))
                    }}
                    onFocus={() => setShowTeacherDropdown(true)}
                    placeholder="Buscar por nombre o CI..."
                    inputClassName={filters.teacher_ci ? 'pr-9' : undefined}
                  />
                  {filters.teacher_ci && (
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      aria-label="Quitar docente"
                      className="absolute right-1.5 top-1/2 z-10 -translate-y-1/2"
                      onClick={() => {
                        setTeacherSearch('')
                        setFilters(f => ({ ...f, teacher_ci: undefined }))
                        setPreviewEnabled(false)
                      }}
                    >
                      <X />
                    </Button>
                  )}
                </div>
                {showTeacherDropdown && teacherSearch && filteredTeachers.length > 0 && (
                  <div className="absolute z-50 mt-1 max-h-48 w-full overflow-y-auto rounded-lg border bg-popover p-1 text-popover-foreground shadow-lg/5">
                    {filteredTeachers.slice(0, 20).map(t => (
                      <button
                        key={t.ci}
                        type="button"
                        onClick={() => {
                          setFilters(f => ({ ...f, teacher_ci: t.ci }))
                          setTeacherSearch(t.full_name)
                          setShowTeacherDropdown(false)
                          setPreviewEnabled(false)
                        }}
                        className="flex w-full items-center justify-between gap-3 rounded-md px-2.5 py-1.5 text-left text-sm hover:bg-accent"
                      >
                        <span className="font-medium text-foreground">{t.full_name}</span>
                        <span className="text-xs tabular-nums text-muted-foreground">{t.ci}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Semester — financial & attendance only */}
              {reportType !== 'comparative' && (
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="report-semester">Semestre (opcional)</Label>
                  <Input
                    id="report-semester"
                    type="text"
                    value={semester}
                    onChange={(e) => { setSemester(e.target.value); setPreviewEnabled(false) }}
                    placeholder="Ej: 1ER SEMESTRE"
                  />
                </div>
              )}

              {/* Group — financial & attendance only */}
              {reportType !== 'comparative' && (
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="report-group">Grupo (opcional)</Label>
                  <Input
                    id="report-group"
                    type="text"
                    value={groupCode}
                    onChange={(e) => { setGroupCode(e.target.value); setPreviewEnabled(false) }}
                    placeholder="Ej: M-1, T-2"
                  />
                </div>
              )}

              {/* Subject — financial only */}
              {reportType === 'financial' && (
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="report-subject">Materia (opcional)</Label>
                  <Input
                    id="report-subject"
                    type="text"
                    value={subject}
                    onChange={(e) => { setSubject(e.target.value); setPreviewEnabled(false) }}
                    placeholder="Ej: Anatomía"
                  />
                </div>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="mt-5 flex flex-wrap items-center gap-3 border-t pt-4">
            <Button variant="outline" onClick={handlePreview} loading={previewLoading} disabled={previewLoading}>
              <Eye />
              {previewLoading ? 'Cargando...' : 'Vista Previa'}
            </Button>

            <Button onClick={handleGenerate} loading={generateReport.isPending} disabled={generateReport.isPending}>
              <FileText />
              {generateReport.isPending ? 'Generando PDF...' : 'Generar PDF'}
            </Button>
          </div>

          {generateReport.isError && (
            <Alert variant="error" className="mt-4">
              <AlertCircle />
              <AlertDescription>
                Error al generar el reporte. Verificá que haya datos para el período seleccionado.
              </AlertDescription>
            </Alert>
          )}
        </CardPanel>
      </Card>

      {/* Success result */}
      {lastGenerated && (
        <Alert variant="success" className="items-center">
          <CheckCircle />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <AlertTitle>¡Reporte generado exitosamente!</AlertTitle>
              <AlertDescription>
                {lastGenerated.description}
                <span className="block text-xs tabular-nums text-muted-foreground">
                  {formatBytes(lastGenerated.file_size)} · {formatDate(lastGenerated.generated_at)}
                </span>
              </AlertDescription>
            </div>
            <Button
              variant="outline"
              onClick={() => void downloadReport(lastGenerated.id, `${lastGenerated.title.replace(/\s+/g, '_')}.pdf`)}
            >
              <Download />
              Descargar PDF
            </Button>
          </div>
        </Alert>
      )}

      {/* Preview Section */}
      {previewEnabled && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Vista Previa — {REPORT_TYPES[reportType].label}</CardTitle>
            <CardDescription>Datos que se incluirán en el reporte PDF</CardDescription>
          </CardHeader>
          <CardPanel>
            {previewLoading && <PreviewSkeleton />}
            {previewError && (
              <Alert variant="error">
                <AlertCircle />
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <AlertDescription>
                    No se pudo cargar la vista previa. Verificá que haya datos para el período seleccionado.
                  </AlertDescription>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void refetchPreview()}
                    loading={previewFetching}
                    disabled={previewFetching}
                  >
                    Reintentar
                  </Button>
                </div>
              </Alert>
            )}
            {previewData && !previewLoading && (
              <>
                {previewData.report_type === 'financial' && <FinancialPreview data={previewData} />}
                {previewData.report_type === 'attendance' && <AttendancePreview data={previewData} />}
                {previewData.report_type === 'comparative' && <ComparativePreview data={previewData} />}
                {previewData.report_type === 'roster' && <RosterPreview data={previewData} />}
                {previewData.report_type === 'incidence' && <IncidencePreview data={previewData} />}
                {previewData.report_type === 'reconciliation' && <ReconciliationPreview data={previewData} />}
              </>
            )}
          </CardPanel>
        </Card>
      )}

      {/* History */}
      {historyLoading ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Historial de Reportes</CardTitle>
            <CardDescription>Últimos 50 reportes generados</CardDescription>
          </CardHeader>
          <CardPanel className="space-y-2" role="status" aria-label="Cargando historial">
            {[0, 1, 2, 3].map((n) => <Skeleton key={n} className="h-8 w-full" />)}
          </CardPanel>
        </Card>
      ) : !history || history.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Historial de Reportes</CardTitle>
            <CardDescription>Últimos 50 reportes generados</CardDescription>
          </CardHeader>
          <EmptyState
            icon={History}
            title="No hay reportes generados aún"
            description="Usá los filtros de arriba para crear uno."
          />
        </Card>
      ) : (
        <TableCard title="Historial de Reportes" description="Últimos 50 reportes generados">
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {['Tipo', 'Título', 'Descripción', 'Tamaño', 'Generado el', 'Estado', 'Acción'].map(h => (
                <TableHead key={h}>{h}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {history.map((report) => (
              <TableRow key={report.id}>
                <TableCell><ReportTypeBadge type={report.report_type} /></TableCell>
                <TableCell className="max-w-[180px] truncate font-medium text-foreground">{report.title}</TableCell>
                <TableCell className="max-w-[200px] truncate text-muted-foreground">{report.description ?? '—'}</TableCell>
                <TableCell className="tabular-nums text-muted-foreground">
                  {report.file_size ? formatBytes(report.file_size) : '—'}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5 tabular-nums">
                    <Clock className="size-3" aria-hidden="true" />
                    {formatDate(report.generated_at)}
                  </span>
                </TableCell>
                <TableCell>
                  <StatusBadge tone={report.status === 'generated' ? 'success' : 'destructive'}>
                    {report.status === 'generated' ? 'Generado' : report.status}
                  </StatusBadge>
                </TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void downloadReport(report.id, `${report.title.replace(/\s+/g, '_')}.pdf`)}
                  >
                    <Download />
                    PDF
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </TableCard>
      )}
    </div>
  )
}
