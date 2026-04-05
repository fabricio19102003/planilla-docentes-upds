import { useState, useEffect } from 'react'
import {
  FileText,
  Download,
  Filter,
  Eye,
  Loader2,
  BarChart3,
  Users,
  Calendar,
  DollarSign,
  ClipboardCheck,
  CheckCircle,
  Clock,
  History,
  X,
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
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

const REPORT_TYPES = {
  financial: { label: 'Financiero', icon: DollarSign, color: '#003366', bgClass: 'bg-blue-950/10 border-[#003366]' },
  attendance: { label: 'Asistencia', icon: ClipboardCheck, color: '#0066CC', bgClass: 'bg-blue-600/10 border-[#0066CC]' },
  comparative: { label: 'Comparativo', icon: BarChart3, color: '#4DA8DA', bgClass: 'bg-sky-400/10 border-[#4DA8DA]' },
} as const

type ReportType = keyof typeof REPORT_TYPES

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function ReportTypeBadge({ type }: { type: string }) {
  const cfg = REPORT_TYPES[type as ReportType]
  if (!cfg) return <Badge className="bg-gray-100 text-gray-600">{type}</Badge>
  const Icon = cfg.icon
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold border"
      style={{ color: cfg.color, borderColor: cfg.color, backgroundColor: `${cfg.color}15` }}
    >
      <Icon size={11} />
      {cfg.label}
    </span>
  )
}

// ── Financial Preview ────────────────────────────────────────────────────────

function FinancialPreview({ data }: { data: any }) {
  return (
    <div className="space-y-4">
      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          { label: 'Docentes', value: data.total_teachers },
          { label: 'Designaciones', value: data.total_designations },
          { label: 'Hrs Asignadas', value: `${data.total_base_hours}h` },
          { label: 'Hrs Ausencia', value: `${data.total_absent_hours}h` },
          { label: 'Hrs a Pagar', value: `${data.total_payable_hours}h` },
          { label: 'Total (Bs)', value: data.total_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 }) },
        ].map(({ label, value }) => (
          <div key={label} className="bg-blue-50/60 rounded-lg p-3 text-center">
            <p className="text-lg font-bold" style={{ color: '#003366' }}>{value}</p>
            <p className="text-xs text-gray-500 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Detail table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200 max-h-80 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0">
            <tr style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)' }}>
              {['Docente', 'Materia', 'Grupo', 'Sem.', 'Hrs Base', 'Ausencias', 'Hrs Pagar', 'Monto (Bs)'].map(h => (
                <th key={h} className="text-left text-white font-semibold text-xs uppercase tracking-wider px-3 py-2.5 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row: any, i: number) => (
              <tr key={`${row.teacher_ci}-${row.subject}-${row.group_code}`}
                  className={`border-b last:border-0 hover:bg-blue-50/70 transition-colors ${i % 2 === 1 ? 'bg-gray-50' : 'bg-white'}`}>
                <td className="px-3 py-2 font-medium text-gray-800 max-w-[180px] truncate">{row.teacher_name}</td>
                <td className="px-3 py-2 text-gray-700 max-w-[160px] truncate">{row.subject}</td>
                <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{row.group_code}</td>
                <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{row.semester}</td>
                <td className="px-3 py-2 text-gray-700 font-medium text-center">{row.base_monthly_hours}h</td>
                <td className="px-3 py-2 text-center">
                  {row.absent_hours > 0
                    ? <span className="text-red-600 font-medium">-{row.absent_hours}h</span>
                    : <span className="text-green-600">0h</span>}
                </td>
                <td className="px-3 py-2 text-gray-800 font-semibold text-center">{row.payable_hours}h</td>
                <td className="px-3 py-2 font-bold text-right pr-4" style={{ color: '#003366' }}>
                  {row.calculated_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Attendance Preview ───────────────────────────────────────────────────────

function AttendancePreview({ data }: { data: any }) {
  const STATUS_LABELS: Record<string, string> = {
    ATTENDED: 'Asistido', LATE: 'Tardanza', ABSENT: 'Ausente', NO_EXIT: 'Sin salida',
  }
  const STATUS_COLORS: Record<string, string> = {
    ATTENDED: 'bg-green-100 text-green-700',
    LATE: 'bg-yellow-100 text-yellow-700',
    ABSENT: 'bg-red-100 text-red-700',
    NO_EXIT: 'bg-blue-100 text-blue-700',
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {[
          { label: 'Total Registros', value: data.total_records, color: '#003366' },
          { label: 'Asistidos', value: data.attended, color: '#16a34a' },
          { label: 'Tardanzas', value: data.late, color: '#d97706' },
          { label: 'Ausencias', value: data.absent, color: '#dc2626' },
          { label: 'Tasa Asistencia', value: `${data.attendance_rate}%`, color: '#0066CC' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-blue-50/60 rounded-lg p-3 text-center">
            <p className="text-xl font-bold" style={{ color }}>{value}</p>
            <p className="text-xs text-gray-500 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-200 max-h-80 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0">
            <tr style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)' }}>
              {['Fecha', 'Docente', 'Estado', 'Entrada', 'Salida', 'Hrs Acad.'].map(h => (
                <th key={h} className="text-left text-white font-semibold text-xs uppercase tracking-wider px-3 py-2.5 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.records_sample.map((rec: any, i: number) => (
              <tr key={i} className={`border-b last:border-0 hover:bg-blue-50/70 transition-colors ${i % 2 === 1 ? 'bg-gray-50' : 'bg-white'}`}>
                <td className="px-3 py-2 text-gray-600 whitespace-nowrap">
                  {rec.date ? new Date(rec.date).toLocaleDateString('es-BO', { day: '2-digit', month: '2-digit' }) : '—'}
                </td>
                <td className="px-3 py-2 text-gray-700 font-mono text-xs">{rec.teacher_ci}</td>
                <td className="px-3 py-2">
                  <Badge className={`text-xs ${STATUS_COLORS[rec.status] ?? 'bg-gray-100 text-gray-600'}`}>
                    {STATUS_LABELS[rec.status] ?? rec.status}
                  </Badge>
                </td>
                <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{rec.check_in ?? '—'}</td>
                <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{rec.check_out ?? '—'}</td>
                <td className="px-3 py-2 text-center font-semibold text-gray-800">{rec.academic_hours ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.total_records > 50 && (
        <p className="text-xs text-gray-400 text-center">
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
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-blue-50/60 rounded-lg p-3 text-center">
          <p className="text-xl font-bold" style={{ color: '#003366' }}>{data.months.length}</p>
          <p className="text-xs text-gray-500">Meses con datos</p>
        </div>
        <div className="bg-blue-50/60 rounded-lg p-3 text-center">
          <p className="text-xl font-bold" style={{ color: '#003366' }}>
            {data.grand_total.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
          </p>
          <p className="text-xs text-gray-500">Total Anual (Bs)</p>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)' }}>
              {['Mes', 'Docentes', 'Hrs Asignadas', 'Hrs Ausencia', 'Hrs a Pagar', 'Total (Bs)'].map(h => (
                <th key={h} className="text-left text-white font-semibold text-xs uppercase tracking-wider px-3 py-2.5 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.months.map((md: any, i: number) => (
              <tr key={md.month} className={`border-b last:border-0 hover:bg-blue-50/70 transition-colors ${i % 2 === 1 ? 'bg-gray-50' : 'bg-white'}`}>
                <td className="px-3 py-2.5 font-semibold text-gray-800">{md.month_name}</td>
                <td className="px-3 py-2.5 text-gray-700 text-center">{md.teachers}</td>
                <td className="px-3 py-2.5 text-gray-700 text-center">{md.base_hours}h</td>
                <td className="px-3 py-2.5 text-center">
                  {md.absent_hours > 0
                    ? <span className="text-red-500 font-medium">{md.absent_hours}h</span>
                    : <span className="text-green-600">0h</span>}
                </td>
                <td className="px-3 py-2.5 text-gray-800 font-medium text-center">{md.payable_hours}h</td>
                <td className="px-3 py-2.5 font-bold text-right pr-4" style={{ color: '#003366' }}>
                  {md.total_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                </td>
              </tr>
            ))}
            {/* Total row */}
            <tr className="border-t-2 border-gray-300" style={{ backgroundColor: '#003366' }}>
              <td className="px-3 py-2.5 text-white font-bold" colSpan={5}>TOTAL ANUAL</td>
              <td className="px-3 py-2.5 text-white font-bold text-right pr-4">
                {data.grand_total.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
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
    setFilters(f => ({
      ...f,
      report_type: reportType,
      month: reportType !== 'comparative' ? month : undefined,
      year,
      semester: semester || undefined,
      group_code: groupCode || undefined,
      subject: subject || undefined,
    }))
  }, [reportType, month, year, semester, groupCode, subject])

  const { data: previewData, isLoading: previewLoading, isError: previewError } = useReportPreview(filters, previewEnabled)
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

  const needsMonth = reportType !== 'comparative'

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="gradient-navy rounded-xl p-6 text-white">
        <div className="flex items-center gap-3">
          <FileText size={28} className="text-white/90" />
          <div>
            <h2 className="text-2xl font-bold">Reportes</h2>
            <p className="text-white/70 mt-0.5">Generá reportes PDF financieros, de asistencia y comparativos</p>
          </div>
        </div>
      </div>

      {/* Report Type Selector */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h3 className="text-base font-semibold" style={{ color: '#003366' }}>Tipo de Reporte</h3>
          <p className="text-sm text-gray-500 mt-0.5">Seleccioná el tipo de análisis que necesitás</p>
        </div>
        <div className="px-6 py-5">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {(Object.entries(REPORT_TYPES) as [ReportType, typeof REPORT_TYPES[ReportType]][]).map(([type, cfg]) => {
              const Icon = cfg.icon
              const isActive = reportType === type
              return (
                <button
                  key={type}
                  onClick={() => handleTypeChange(type)}
                  className={`flex items-center gap-3 p-4 rounded-xl border-2 transition-all duration-200 text-left ${
                    isActive
                      ? 'shadow-md'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50/50'
                  }`}
                  style={isActive ? { borderColor: cfg.color, backgroundColor: `${cfg.color}0d` } : undefined}
                >
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{ backgroundColor: isActive ? cfg.color : '#f3f4f6' }}
                  >
                    <Icon size={20} style={{ color: isActive ? 'white' : cfg.color }} />
                  </div>
                  <div>
                    <p className="font-semibold text-sm" style={{ color: isActive ? cfg.color : '#374151' }}>
                      {cfg.label}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {type === 'financial' && 'Pagos por docente/designación'}
                      {type === 'attendance' && 'Registros de asistencia detallados'}
                      {type === 'comparative' && 'Evolución mensual del año'}
                    </p>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
          <Filter size={16} style={{ color: '#0066CC' }} />
          <h3 className="text-base font-semibold" style={{ color: '#003366' }}>Filtros</h3>
        </div>
        <div className="px-6 py-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">

            {/* Month — not for comparative */}
            {needsMonth && (
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">
                  <Calendar size={13} className="inline mr-1" />Mes
                </label>
                <select
                  value={month}
                  onChange={(e) => { setMonth(Number(e.target.value)); setPreviewEnabled(false) }}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
                >
                  {Object.entries(MONTH_NAMES).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
            )}

            {/* Year */}
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">
                <Calendar size={13} className="inline mr-1" />Año
              </label>
              <input
                type="number"
                value={year}
                onChange={(e) => { setYear(Number(e.target.value)); setPreviewEnabled(false) }}
                min={2020}
                max={2030}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
              />
            </div>

            {/* Teacher — searchable */}
            <div className="teacher-search-container relative">
              <label className="text-sm font-medium text-gray-700 block mb-1">
                <Users size={13} className="inline mr-1" />Docente (opcional)
              </label>
              <div className="relative">
                <input
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
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] focus:border-transparent bg-white"
                />
                {filters.teacher_ci && (
                  <button
                    onClick={() => {
                      setTeacherSearch('')
                      setFilters(f => ({ ...f, teacher_ci: undefined }))
                      setPreviewEnabled(false)
                    }}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
              {showTeacherDropdown && teacherSearch && filteredTeachers.length > 0 && (
                <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                  {filteredTeachers.slice(0, 20).map(t => (
                    <button
                      key={t.ci}
                      onClick={() => {
                        setFilters(f => ({ ...f, teacher_ci: t.ci }))
                        setTeacherSearch(t.full_name)
                        setShowTeacherDropdown(false)
                        setPreviewEnabled(false)
                      }}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 flex items-center justify-between"
                    >
                      <span className="font-medium text-gray-800">{t.full_name}</span>
                      <span className="text-xs text-gray-400">{t.ci}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Semester — financial & attendance only */}
            {reportType !== 'comparative' && (
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Semestre (opcional)</label>
                <input
                  type="text"
                  value={semester}
                  onChange={(e) => { setSemester(e.target.value); setPreviewEnabled(false) }}
                  placeholder="Ej: 1ER SEMESTRE"
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
                />
              </div>
            )}

            {/* Group — financial & attendance only */}
            {reportType !== 'comparative' && (
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Grupo (opcional)</label>
                <input
                  type="text"
                  value={groupCode}
                  onChange={(e) => { setGroupCode(e.target.value); setPreviewEnabled(false) }}
                  placeholder="Ej: M-1, T-2"
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
                />
              </div>
            )}

            {/* Subject — financial only */}
            {reportType === 'financial' && (
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Materia (opcional)</label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => { setSubject(e.target.value); setPreviewEnabled(false) }}
                  placeholder="Ej: Anatomía"
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
                />
              </div>
            )}

          </div>

          {/* Actions */}
          <div className="flex flex-wrap items-center gap-3 mt-5 pt-4 border-t border-gray-100">
            <Button
              variant="outline"
              onClick={handlePreview}
              disabled={previewLoading}
              className="gap-2 border-[#0066CC] text-[#0066CC] hover:bg-blue-50"
            >
              {previewLoading ? (
                <><Loader2 size={15} className="animate-spin" />Cargando...</>
              ) : (
                <><Eye size={15} />Vista Previa</>
              )}
            </Button>

            <Button
              onClick={handleGenerate}
              disabled={generateReport.isPending}
              className="gap-2 text-white"
              style={{ backgroundColor: '#003366' }}
            >
              {generateReport.isPending ? (
                <><Loader2 size={15} className="animate-spin" />Generando PDF...</>
              ) : (
                <><FileText size={15} />Generar PDF</>
              )}
            </Button>

            {generateReport.isError && (
              <p className="text-sm text-red-600 flex-1">
                Error al generar el reporte. Verificá que haya datos para el período seleccionado.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Success result */}
      {lastGenerated && (
        <div
          className="card-3d-static overflow-hidden border-l-4"
          style={{ borderLeftColor: '#16a34a' }}
        >
          <div className="px-6 py-5">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div className="flex items-start gap-3">
                <CheckCircle size={22} className="text-green-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-green-700">¡Reporte generado exitosamente!</p>
                  <p className="text-sm text-gray-600 mt-0.5">{lastGenerated.description}</p>
                  <p className="text-xs text-gray-400 mt-1">
                    {formatBytes(lastGenerated.file_size)} · {formatDate(lastGenerated.generated_at)}
                  </p>
                </div>
              </div>
              <Button
                variant="outline"
                className="border-[#0066CC] text-[#0066CC] hover:bg-blue-50 gap-2"
                onClick={() => void downloadReport(lastGenerated.id, `${lastGenerated.title.replace(/\s+/g, '_')}.pdf`)}
              >
                <Download size={15} />
                Descargar PDF
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Preview Section */}
      {previewEnabled && (
        <div className="card-3d-static overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: '#0066CC' }}>
              <Eye size={16} className="text-white" />
            </div>
            <div>
              <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
                Vista Previa — {REPORT_TYPES[reportType].label}
              </h3>
              <p className="text-xs text-gray-500">Datos que se incluirán en el reporte PDF</p>
            </div>
          </div>
          <div className="p-6">
            {previewLoading && (
              <div className="flex justify-center py-10">
                <Loader2 size={28} className="animate-spin text-[#003366]" />
              </div>
            )}
            {previewError && (
              <div className="p-4 bg-red-50 rounded-lg border border-red-200 text-sm text-red-600">
                No se pudo cargar la vista previa. Verificá que haya datos para el período seleccionado.
              </div>
            )}
            {previewData && !previewLoading && (
              <>
                {previewData.report_type === 'financial' && <FinancialPreview data={previewData} />}
                {previewData.report_type === 'attendance' && <AttendancePreview data={previewData} />}
                {previewData.report_type === 'comparative' && <ComparativePreview data={previewData} />}
              </>
            )}
          </div>
        </div>
      )}

      {/* History */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center gradient-stat-navy">
            <History size={16} className="text-white" />
          </div>
          <div>
            <h3 className="text-base font-semibold" style={{ color: '#003366' }}>Historial de Reportes</h3>
            <p className="text-xs text-gray-500">Últimos 50 reportes generados</p>
          </div>
        </div>
        <div className="p-6">
          {historyLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 size={24} className="animate-spin text-[#003366]" />
            </div>
          ) : !history || history.length === 0 ? (
            <div className="text-center py-10 text-gray-400 text-sm">
              No hay reportes generados aún. Usá los filtros de arriba para crear uno.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)' }}>
                    {['Tipo', 'Título', 'Descripción', 'Tamaño', 'Generado el', 'Estado', 'Acción'].map(h => (
                      <th key={h} className="text-left text-white font-semibold text-xs uppercase tracking-wider px-3 py-2.5 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {history.map((report, i) => (
                    <tr
                      key={report.id}
                      className={`border-b last:border-0 hover:bg-blue-50/70 transition-colors ${i % 2 === 1 ? 'bg-gray-50' : 'bg-white'}`}
                    >
                      <td className="px-3 py-3 whitespace-nowrap">
                        <ReportTypeBadge type={report.report_type} />
                      </td>
                      <td className="px-3 py-3 font-medium text-gray-800 max-w-[180px] truncate">{report.title}</td>
                      <td className="px-3 py-3 text-gray-600 max-w-[200px] truncate">{report.description ?? '—'}</td>
                      <td className="px-3 py-3 text-gray-500 whitespace-nowrap">
                        {report.file_size ? formatBytes(report.file_size) : '—'}
                      </td>
                      <td className="px-3 py-3 text-gray-500 whitespace-nowrap">
                        <div className="flex items-center gap-1">
                          <Clock size={12} className="text-gray-400" />
                          {formatDate(report.generated_at)}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <Badge className={report.status === 'generated' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                          {report.status === 'generated' ? 'Generado' : report.status}
                        </Badge>
                      </td>
                      <td className="px-3 py-3">
                        <button
                          onClick={() => void downloadReport(report.id, `${report.title.replace(/\s+/g, '_')}.pdf`)}
                          className="inline-flex items-center gap-1.5 text-[#0066CC] hover:underline text-sm font-medium whitespace-nowrap"
                        >
                          <Download size={13} />
                          PDF
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
