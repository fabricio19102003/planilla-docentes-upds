import { useState, useMemo } from 'react'
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
} from 'lucide-react'
import {
  usePracticeAttendance,
  usePracticeAttendanceSummary,
  useGeneratePracticeAttendance,
  useUpdatePracticeAttendance,
  useDeletePracticeAttendance,
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

const STATUS_CONFIG: Record<string, { label: string; bg: string; text: string }> = {
  attended: { label: 'Asistio', bg: 'bg-green-100', text: 'text-green-700' },
  absent:   { label: 'Ausente', bg: 'bg-red-100', text: 'text-red-700' },
  late:     { label: 'Tardanza', bg: 'bg-yellow-100', text: 'text-yellow-700' },
  justified:{ label: 'Justificado', bg: 'bg-blue-100', text: 'text-blue-700' },
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '\u2014'
  const d = new Date(dateStr + 'T00:00:00')
  const days = ['Dom', 'Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab']
  return `${days[d.getDay()]} ${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`
}

function formatTime(timeStr: string | null): string {
  if (!timeStr) return '\u2014'
  return timeStr.slice(0, 5)
}

export function PracticeAttendancePage() {
  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1

  const [month, setMonth] = useState<number>(currentMonth)
  const [year, setYear] = useState<number>(currentYear)
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [teacherFilter, setTeacherFilter] = useState<string>('')
  const [editingObs, setEditingObs] = useState<number | null>(null)
  const [obsValue, setObsValue] = useState('')

  const { data: entries, isLoading } = usePracticeAttendance(
    month, year,
    teacherFilter || undefined,
    startDate || undefined,
    endDate || undefined,
  )
  const { data: summaries } = usePracticeAttendanceSummary(month, year)
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

  // Group entries by teacher
  const grouped = useMemo(() => {
    if (!entries) return []
    const map = new Map<string, { name: string; entries: PracticeAttendanceEntry[] }>()
    for (const e of entries) {
      const key = e.teacher_ci
      if (!map.has(key)) {
        map.set(key, { name: e.teacher_name ?? key, entries: [] })
      }
      map.get(key)!.entries.push(e)
    }
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name))
  }, [entries])

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

      {/* Detailed entries grouped by teacher */}
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
                {group.entries.map((entry) => {
                  const cfg = STATUS_CONFIG[entry.status] ?? STATUS_CONFIG.absent
                  return (
                    <tr key={entry.id} className="hover:bg-gray-50/50">
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
                          className={`text-xs font-medium rounded-full px-3 py-1 border-0 cursor-pointer ${cfg.bg} ${cfg.text}`}
                          value={entry.status}
                          onChange={(e) => handleStatusChange(entry, e.target.value)}
                          disabled={updateMutation.isPending}
                        >
                          <option value="attended">Asistio</option>
                          <option value="absent">Ausente</option>
                          <option value="late">Tardanza</option>
                          <option value="justified">Justificado</option>
                        </select>
                      </td>
                      <td className="text-center px-3 py-2">
                        <input
                          type="time"
                          className="border border-gray-200 rounded px-2 py-1 text-xs w-20 text-center"
                          value={entry.actual_start?.slice(0, 5) ?? ''}
                          onChange={(e) => updateMutation.mutate({ id: entry.id, actual_start: e.target.value || undefined })}
                        />
                      </td>
                      <td className="text-center px-3 py-2">
                        <input
                          type="time"
                          className="border border-gray-200 rounded px-2 py-1 text-xs w-20 text-center"
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
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {/* Loading overlay for mutations */}
      {(updateMutation.isPending || deleteMutation.isPending) && (
        <div className="fixed bottom-4 right-4 bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2 text-sm z-50">
          <Loader2 size={14} className="animate-spin" />
          Guardando...
        </div>
      )}
    </div>
  )
}
