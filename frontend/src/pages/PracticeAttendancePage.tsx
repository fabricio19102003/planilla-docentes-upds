import { useState, useMemo, Fragment } from 'react'
import {
  ClipboardCheck,
  Loader2,
  Users,
  Calendar,
  CheckCircle,
  XCircle,
  Clock,
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
import { StatCard } from '@/components/shared/StatCard'
import { LoadingPage } from '@/components/shared/LoadingSpinner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

const STATUS_CONFIG: Record<string, { label: string; bg: string; text: string; rowBg: string }> = {
  attended:  { label: 'ASISTIÓ',      bg: 'bg-green-100',  text: 'text-green-700',  rowBg: 'bg-green-50/40' },
  absent:    { label: 'AUSENTE',      bg: 'bg-red-100',    text: 'text-red-700',    rowBg: 'bg-red-50/40' },
  late:      { label: 'TARDANZA',     bg: 'bg-yellow-100', text: 'text-yellow-700', rowBg: 'bg-yellow-50/40' },
  justified: { label: 'JUSTIFICADO', bg: 'bg-blue-100',   text: 'text-blue-700',   rowBg: 'bg-blue-50/40' },
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

  const { data: entries, isLoading } = usePracticeAttendance(
    month, year,
    teacherFilter || undefined,
    startDate || undefined,
    endDate || undefined,
  )
  const { data: summaries } = usePracticeAttendanceSummary(month, year, startDate || undefined, endDate || undefined)
  const generateMutation = useGeneratePracticeAttendance()
  const updateMutation = useUpdatePracticeAttendance()
  const deleteMutation = useDeletePracticeAttendance()

  // Unique teachers for filter dropdown
  const teachers = useMemo(() => {
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
  }, [entries])

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
    updateMutation.mutate({ id: entryId, observation: obsValue || undefined })
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

  function navigateDate(direction: -1 | 1) {
    if (!selectedDate) return
    const d = new Date(selectedDate + 'T00:00:00')
    d.setDate(d.getDate() + direction)
    setSelectedDate(d.toISOString().split('T')[0])
  }

  if (isLoading) return <LoadingPage />

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl gradient-stat-blue flex items-center justify-center shadow-lg">
            <ClipboardCheck size={20} className="text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-800">Asistencia Practicas Internas</h1>
            <p className="text-gray-500 text-sm">Registro manual de asistencia de docentes asistenciales</p>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <div className="flex flex-wrap items-end gap-4">
          {/* Month */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Mes</label>
            <select
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
            >
              {Object.entries(MONTH_NAMES).map(([m, name]) => (
                <option key={m} value={m}>{name}</option>
              ))}
            </select>
          </div>

          {/* Year */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Anio</label>
            <select
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
            >
              {[currentYear - 1, currentYear, currentYear + 1].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>

          {/* Start date */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Desde</label>
            <input
              type="date"
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>

          {/* End date */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Hasta</label>
            <input
              type="date"
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>

          {/* Teacher filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Docente</label>
            <select
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              value={teacherFilter}
              onChange={(e) => setTeacherFilter(e.target.value)}
            >
              <option value="">Todos</option>
              {teachers.map((t) => (
                <option key={t.ci} value={t.ci}>{t.name}</option>
              ))}
            </select>
          </div>

          {/* Specific date filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              <CalendarDays size={14} className="inline mr-1" />
              Fecha Especifica
            </label>
            <div className="flex items-center gap-1">
              <input
                type="date"
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
              />
              {selectedDate && (
                <button
                  onClick={() => setSelectedDate('')}
                  className="text-gray-400 hover:text-red-500 transition-colors p-1"
                  title="Limpiar fecha"
                >
                  <X size={16} />
                </button>
              )}
            </div>
          </div>

          {/* Generate button */}
          <div>
            <Button
              onClick={handleGenerate}
              disabled={generateMutation.isPending}
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              {generateMutation.isPending ? (
                <Loader2 size={16} className="animate-spin mr-2" />
              ) : (
                <Calendar size={16} className="mr-2" />
              )}
              Generar Asistencia
            </Button>
          </div>

          {/* Export buttons */}
          <div className="flex gap-2">
            <button
              onClick={async () => {
                setPdfLoading(true)
                try {
                  await downloadPracticeAttendancePdf({
                    month, year,
                    start_date: startDate || undefined,
                    end_date: endDate || undefined,
                    teacher_ci: teacherFilter || undefined,
                  })
                } finally { setPdfLoading(false) }
              }}
              disabled={pdfLoading}
              className="flex items-center gap-2 px-3 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 text-sm font-medium"
            >
              {pdfLoading ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
              Exportar PDF
            </button>
            <button
              onClick={async () => {
                setExcelLoading(true)
                try {
                  await downloadPracticeAttendanceExcel({
                    month, year,
                    start_date: startDate || undefined,
                    end_date: endDate || undefined,
                    teacher_ci: teacherFilter || undefined,
                  })
                } finally { setExcelLoading(false) }
              }}
              disabled={excelLoading}
              className="flex items-center gap-2 px-3 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm font-medium"
            >
              {excelLoading ? <Loader2 size={16} className="animate-spin" /> : <FileSpreadsheet size={16} />}
              Exportar Excel
            </button>
          </div>
        </div>

        {generateMutation.isSuccess && (
          <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
            Se crearon {generateMutation.data.created} entradas de asistencia para {MONTH_NAMES[month]} {year}.
          </div>
        )}
        {generateMutation.isError && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            Error: {(generateMutation.error as Error)?.message ?? 'No se pudo generar la asistencia'}
          </div>
        )}
      </div>

      {/* Summary cards */}
      {summaries && summaries.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard icon={Users} title="Docentes" value={summaries.length} color="#0066CC" />
          <StatCard icon={Calendar} title="Clases Programadas" value={totals.scheduled} color="#003366" />
          <StatCard icon={CheckCircle} title="Asistidas" value={totals.attended} subtitle={`${totals.rate}%`} color="#16a34a" />
          <StatCard icon={XCircle} title="Ausentes" value={totals.absent} color="#dc2626" />
        </div>
      )}

      {/* Per-teacher summary table */}
      {summaries && summaries.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-lg font-semibold text-gray-800">Resumen por Docente</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Docente</th>
                  <th className="text-center px-3 py-3 font-medium text-gray-600">Programadas</th>
                  <th className="text-center px-3 py-3 font-medium text-gray-600">Asistidas</th>
                  <th className="text-center px-3 py-3 font-medium text-gray-600">Ausentes</th>
                  <th className="text-center px-3 py-3 font-medium text-gray-600">Tardanzas</th>
                  <th className="text-center px-3 py-3 font-medium text-gray-600">Justificadas</th>
                  <th className="text-center px-3 py-3 font-medium text-gray-600">Hrs Prog.</th>
                  <th className="text-center px-3 py-3 font-medium text-gray-600">Hrs Asist.</th>
                  <th className="text-center px-3 py-3 font-medium text-gray-600">Tasa</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {summaries.map((s) => (
                  <tr key={s.teacher_ci} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-800">{s.teacher_name}</td>
                    <td className="text-center px-3 py-3">{s.total_scheduled}</td>
                    <td className="text-center px-3 py-3 text-green-600 font-medium">{s.total_attended}</td>
                    <td className="text-center px-3 py-3 text-red-600 font-medium">{s.total_absent}</td>
                    <td className="text-center px-3 py-3 text-yellow-600">{s.total_late}</td>
                    <td className="text-center px-3 py-3 text-blue-600">{s.total_justified}</td>
                    <td className="text-center px-3 py-3">{s.total_hours_scheduled}h</td>
                    <td className="text-center px-3 py-3">{s.total_hours_attended}h</td>
                    <td className="text-center px-3 py-3">
                      <Badge className={s.attendance_rate >= 80 ? 'bg-green-100 text-green-700' : s.attendance_rate >= 50 ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'}>
                        {s.attendance_rate}%
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ===== DAILY VIEW (when a specific date is selected) ===== */}
      {selectedDate && (
        <>
          {/* Daily view header with navigation */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => navigateDate(-1)}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <ChevronLeft size={16} />
                  Dia anterior
                </button>
                <div className="text-center">
                  <h2 className="text-lg font-semibold text-blue-800">
                    <CalendarDays size={18} className="inline mr-2" />
                    Asistencia del {formatFullDate(selectedDate)}
                  </h2>
                  <p className="text-sm text-blue-600">
                    {dailyEntries.length} clase{dailyEntries.length !== 1 ? 's' : ''} programada{dailyEntries.length !== 1 ? 's' : ''}
                  </p>
                </div>
                <button
                  onClick={() => navigateDate(1)}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Dia siguiente
                  <ChevronRight size={16} />
                </button>
              </div>

              {/* Bulk action buttons */}
              {dailyEntries.length > 0 && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleBulkStatus('attended')}
                    disabled={bulkLoading || updateMutation.isPending}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-green-100 text-green-700 border border-green-300 rounded-lg hover:bg-green-200 disabled:opacity-50 transition-colors"
                  >
                    {bulkLoading ? <Loader2 size={14} className="animate-spin" /> : <CheckCheck size={14} />}
                    Todos Asistieron
                  </button>
                  <button
                    onClick={() => handleBulkStatus('absent')}
                    disabled={bulkLoading || updateMutation.isPending}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-red-100 text-red-700 border border-red-300 rounded-lg hover:bg-red-200 disabled:opacity-50 transition-colors"
                  >
                    {bulkLoading ? <Loader2 size={14} className="animate-spin" /> : <X size={14} />}
                    Todos Ausentes
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Daily flat table */}
          {dailyEntries.length === 0 ? (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center">
              <Calendar size={48} className="mx-auto text-gray-300 mb-4" />
              <p className="text-gray-500 text-lg">No hay clases programadas para esta fecha</p>
              <p className="text-gray-400 text-sm mt-1">Selecciona otra fecha o usa los botones de navegacion</p>
            </div>
          ) : (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600">Docente</th>
                      <th className="text-left px-3 py-3 font-medium text-gray-600">Materia</th>
                      <th className="text-left px-3 py-3 font-medium text-gray-600">Grupo</th>
                      <th className="text-center px-3 py-3 font-medium text-gray-600">Horario</th>
                      <th className="text-center px-3 py-3 font-medium text-gray-600">Estado</th>
                      <th className="text-center px-3 py-3 font-medium text-gray-600">Hora Llegada</th>
                      <th className="text-center px-3 py-3 font-medium text-gray-600">Hora Salida</th>
                      <th className="text-left px-3 py-3 font-medium text-gray-600">Obs</th>
                      <th className="px-2 py-3"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {dailyEntries.map((entry) => {
                      const cfg = STATUS_CONFIG[entry.status] ?? STATUS_CONFIG.absent
                      return (
                        <tr key={entry.id} className={`hover:bg-gray-50 ${cfg.rowBg}`}>
                          <td className="px-4 py-2.5 font-medium text-gray-800 whitespace-nowrap">
                            {entry.teacher_name ?? entry.teacher_ci}
                          </td>
                          <td className="px-3 py-2.5 text-gray-700 max-w-[200px] truncate" title={entry.subject ?? ''}>
                            {entry.subject}
                          </td>
                          <td className="px-3 py-2.5 text-gray-600">{entry.group_code}</td>
                          <td className="text-center px-3 py-2.5 text-gray-600 whitespace-nowrap">
                            {formatTime(entry.scheduled_start)} - {formatTime(entry.scheduled_end)}
                          </td>
                          <td className="text-center px-3 py-2.5">
                            <select
                              className={`text-xs font-semibold rounded-full px-3 py-1 border-0 cursor-pointer ${cfg.bg} ${cfg.text}`}
                              value={entry.status}
                              onChange={(e) => handleStatusChange(entry, e.target.value)}
                              disabled={updateMutation.isPending}
                            >
                              {Object.entries(STATUS_CONFIG).map(([value, sc]) => (
                                <option key={value} value={value}>{sc.label}</option>
                              ))}
                            </select>
                          </td>
                          <td className="text-center px-3 py-2.5">
                            <input
                              type="time"
                              step="60"
                              className="border border-gray-200 rounded px-2 py-1 text-sm min-w-[6rem] text-center"
                              value={entry.actual_start?.slice(0, 5) ?? ''}
                              onChange={(e) => {
                                const newStart = e.target.value || undefined
                                updateMutation.mutate({ id: entry.id, actual_start: newStart })
                                if (newStart && entry.scheduled_start) {
                                  const newStatus = autoSetStatus(entry.scheduled_start, newStart)
                                  if (newStatus && newStatus !== entry.status) {
                                    updateMutation.mutate({ id: entry.id, status: newStatus })
                                  }
                                }
                              }}
                            />
                          </td>
                          <td className="text-center px-3 py-2.5">
                            <input
                              type="time"
                              step="60"
                              className="border border-gray-200 rounded px-2 py-1 text-sm min-w-[6rem] text-center"
                              value={entry.actual_end?.slice(0, 5) ?? ''}
                              onChange={(e) => updateMutation.mutate({ id: entry.id, actual_end: e.target.value || undefined })}
                            />
                          </td>
                          <td className="px-3 py-2.5">
                            {editingObs === entry.id ? (
                              <div className="flex items-center gap-1">
                                <input
                                  type="text"
                                  className="border border-gray-300 rounded px-2 py-1 text-xs w-32"
                                  value={obsValue}
                                  onChange={(e) => setObsValue(e.target.value)}
                                  onKeyDown={(e) => e.key === 'Enter' && handleObsSave(entry.id)}
                                  autoFocus
                                />
                                <button
                                  className="text-green-600 hover:text-green-800"
                                  onClick={() => handleObsSave(entry.id)}
                                >
                                  <CheckCircle size={14} />
                                </button>
                                <button
                                  className="text-gray-400 hover:text-gray-600"
                                  onClick={() => { setEditingObs(null); setObsValue('') }}
                                >
                                  <XCircle size={14} />
                                </button>
                              </div>
                            ) : (
                              <span
                                className="text-xs text-gray-500 cursor-pointer hover:text-gray-700 truncate max-w-[120px] inline-block"
                                title={entry.observation ?? 'Click para agregar'}
                                onClick={() => { setEditingObs(entry.id); setObsValue(entry.observation ?? '') }}
                              >
                                {entry.observation || <span className="italic text-gray-300">sin obs.</span>}
                              </span>
                            )}
                          </td>
                          <td className="px-2 py-2.5">
                            <button
                              className="text-gray-300 hover:text-red-500 transition-colors"
                              title="Eliminar"
                              onClick={() => {
                                if (confirm('Eliminar este registro de asistencia?')) {
                                  deleteMutation.mutate(entry.id)
                                }
                              }}
                            >
                              <Trash2 size={14} />
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {/* ===== GROUPED VIEW (when no specific date is selected) ===== */}
      {!selectedDate && (
        <>
          {grouped.length === 0 && !isLoading && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center">
              <AlertTriangle size={48} className="mx-auto text-gray-300 mb-4" />
              <p className="text-gray-500 text-lg">No hay registros de asistencia para este periodo</p>
              <p className="text-gray-400 text-sm mt-1">Usa el boton "Generar Asistencia" para crear los registros desde el horario</p>
            </div>
          )}

          {grouped.map((group) => (
            <div key={group.name} className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100 bg-gray-50">
                <h3 className="text-base font-semibold text-gray-800">{group.name}</h3>
                <p className="text-xs text-gray-500">{group.entries.length} registros</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50/50">
                    <tr>
                      <th className="text-left px-4 py-2 font-medium text-gray-600">Fecha</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600">Materia</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600">Grupo</th>
                      <th className="text-center px-3 py-2 font-medium text-gray-600">Horario Prog.</th>
                      <th className="text-center px-3 py-2 font-medium text-gray-600">Estado</th>
                      <th className="text-center px-3 py-2 font-medium text-gray-600">Hora Real Inicio</th>
                      <th className="text-center px-3 py-2 font-medium text-gray-600">Hora Real Fin</th>
                      <th className="text-center px-3 py-2 font-medium text-gray-600">Hrs</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600">Observacion</th>
                      <th className="px-2 py-2"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {group.entries.map((entry, idx, arr) => {
                      const cfg = STATUS_CONFIG[entry.status] ?? STATUS_CONFIG.absent
                      const showDateHeader = idx === 0 || arr[idx - 1].date !== entry.date
                      return (
                        <Fragment key={entry.id}>
                        {showDateHeader && (
                          <tr className="bg-gray-100/80">
                            <td colSpan={10} className="px-4 py-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                              {formatDate(entry.date)}
                            </td>
                          </tr>
                        )}
                        <tr className={`hover:bg-gray-100/60 ${cfg.rowBg}`}>
                          <td className="px-4 py-2 whitespace-nowrap text-gray-700">{formatDate(entry.date)}</td>
                          <td className="px-3 py-2 text-gray-700 max-w-[200px] truncate" title={entry.subject ?? ''}>
                            {entry.subject}
                          </td>
                          <td className="px-3 py-2 text-gray-600">{entry.group_code}</td>
                          <td className="text-center px-3 py-2 text-gray-600 whitespace-nowrap">
                            {formatTime(entry.scheduled_start)} - {formatTime(entry.scheduled_end)}
                          </td>
                          <td className="text-center px-3 py-2">
                            <select
                              className={`text-xs font-semibold rounded-full px-3 py-1 border-0 cursor-pointer ${cfg.bg} ${cfg.text}`}
                              value={entry.status}
                              onChange={(e) => handleStatusChange(entry, e.target.value)}
                              disabled={updateMutation.isPending}
                            >
                              {Object.entries(STATUS_CONFIG).map(([value, sc]) => (
                                <option key={value} value={value}>{sc.label}</option>
                              ))}
                            </select>
                          </td>
                          <td className="text-center px-3 py-2">
                            <input
                              type="time"
                              step="60"
                              placeholder="HH:MM"
                              className="border border-gray-200 rounded px-2 py-1 text-sm min-w-[6rem] text-center"
                              value={entry.actual_start?.slice(0, 5) ?? ''}
                              onChange={(e) => {
                                const newStart = e.target.value || undefined
                                updateMutation.mutate({ id: entry.id, actual_start: newStart })
                                if (newStart && entry.scheduled_start) {
                                  const newStatus = autoSetStatus(entry.scheduled_start, newStart)
                                  if (newStatus && newStatus !== entry.status) {
                                    updateMutation.mutate({ id: entry.id, status: newStatus })
                                  }
                                }
                              }}
                            />
                          </td>
                          <td className="text-center px-3 py-2">
                            <input
                              type="time"
                              step="60"
                              placeholder="HH:MM"
                              className="border border-gray-200 rounded px-2 py-1 text-sm min-w-[6rem] text-center"
                              value={entry.actual_end?.slice(0, 5) ?? ''}
                              onChange={(e) => updateMutation.mutate({ id: entry.id, actual_end: e.target.value || undefined })}
                            />
                          </td>
                          <td className="text-center px-3 py-2 text-gray-600">{entry.academic_hours}h</td>
                          <td className="px-3 py-2">
                            {editingObs === entry.id ? (
                              <div className="flex items-center gap-1">
                                <input
                                  type="text"
                                  className="border border-gray-300 rounded px-2 py-1 text-xs w-32"
                                  value={obsValue}
                                  onChange={(e) => setObsValue(e.target.value)}
                                  onKeyDown={(e) => e.key === 'Enter' && handleObsSave(entry.id)}
                                  autoFocus
                                />
                                <button
                                  className="text-green-600 hover:text-green-800"
                                  onClick={() => handleObsSave(entry.id)}
                                >
                                  <CheckCircle size={14} />
                                </button>
                                <button
                                  className="text-gray-400 hover:text-gray-600"
                                  onClick={() => { setEditingObs(null); setObsValue('') }}
                                >
                                  <XCircle size={14} />
                                </button>
                              </div>
                            ) : (
                              <span
                                className="text-xs text-gray-500 cursor-pointer hover:text-gray-700 truncate max-w-[120px] inline-block"
                                title={entry.observation ?? 'Click para agregar'}
                                onClick={() => { setEditingObs(entry.id); setObsValue(entry.observation ?? '') }}
                              >
                                {entry.observation || <span className="italic text-gray-300">sin obs.</span>}
                              </span>
                            )}
                          </td>
                          <td className="px-2 py-2">
                            <button
                              className="text-gray-300 hover:text-red-500 transition-colors"
                              title="Eliminar"
                              onClick={() => {
                                if (confirm('Eliminar este registro de asistencia?')) {
                                  deleteMutation.mutate(entry.id)
                                }
                              }}
                            >
                              <Trash2 size={14} />
                            </button>
                          </td>
                        </tr>
                        </Fragment>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </>
      )}

      {/* Loading overlay for mutations */}
      {(updateMutation.isPending || deleteMutation.isPending || bulkLoading) && (
        <div className="fixed bottom-4 right-4 bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2 text-sm z-50">
          <Loader2 size={14} className="animate-spin" />
          Guardando...
        </div>
      )}
    </div>
  )
}
