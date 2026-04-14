import { useState, useEffect, useRef } from 'react'
import {
  ShieldCheck,
  Calendar,
  ClipboardCheck,
  Fingerprint,
  Loader2,
  X,
  Users,
  Download,
} from 'lucide-react'
import { useAttendanceAudit } from '@/api/hooks/useAttendance'
import { useTeachers } from '@/api/hooks/useTeachers'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { api } from '@/api/client'

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

function formatLocalDate(dateStr: string): string {
  if (!dateStr) return '—'
  // Parse as local date to avoid UTC offset shifting the day
  const [year, month, day] = dateStr.split('-')
  return `${day}/${month}/${year}`
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

  const { data: teachersData } = useTeachers({ page: 1, perPage: 500 })
  const teachers = teachersData?.items ?? []

  const filteredTeachers = teacherSearch
    ? teachers.filter(
        (t) =>
          t.full_name.toLowerCase().includes(teacherSearch.toLowerCase()) ||
          t.ci.includes(teacherSearch),
      )
    : []

  const { data, isLoading, isError } = useAttendanceAudit(
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

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center gap-3">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center"
          style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #0066CC 100%)' }}
        >
          <ShieldCheck size={20} className="text-white" />
        </div>
        <div>
          <h1 className="text-xl font-bold" style={{ color: '#003366' }}>
            Auditoría de Asistencia
          </h1>
          <p className="text-sm text-gray-500">
            Trazabilidad completa: horario asignado · datos biométricos · resultado del procesamiento
          </p>
        </div>
      </div>

      {/* Filter controls */}
      <div className="card-3d-static p-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Teacher searchable */}
          <div className="lg:col-span-2 relative" ref={dropdownRef}>
            <label className="text-sm font-medium text-gray-700 block mb-1">
              <Users size={13} className="inline mr-1" />
              Docente
            </label>
            <div className="relative">
              <input
                type="text"
                value={teacherSearch}
                onChange={(e) => {
                  setTeacherSearch(e.target.value)
                  setShowDropdown(true)
                  if (!e.target.value) setSelectedCi('')
                }}
                onFocus={() => setShowDropdown(true)}
                placeholder="Buscar por nombre o CI..."
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] focus:border-transparent bg-white"
              />
              {selectedCi && (
                <button
                  onClick={() => {
                    setTeacherSearch('')
                    setSelectedCi('')
                  }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  <X size={14} />
                </button>
              )}
            </div>
            {showDropdown && teacherSearch && filteredTeachers.length > 0 && (
              <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                {filteredTeachers.slice(0, 20).map((t) => (
                  <button
                    key={t.ci}
                    onClick={() => {
                      setSelectedCi(t.ci)
                      setTeacherSearch(t.full_name)
                      setShowDropdown(false)
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

          {/* Month */}
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">
              <Calendar size={13} className="inline mr-1" />
              Mes
            </label>
            <select
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
            >
              {Object.entries(MONTH_NAMES).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>

          {/* Year */}
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">
              <Calendar size={13} className="inline mr-1" />
              Año
            </label>
            <input
              type="number"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              min={2020}
              max={2030}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
            />
          </div>
        </div>
      </div>

      {/* Empty state */}
      {!selectedCi && (
        <div className="card-3d-static p-12 text-center">
          <ShieldCheck size={40} className="mx-auto mb-3 opacity-20" style={{ color: '#003366' }} />
          <p className="text-gray-400 font-medium">Seleccioná un docente para ver la auditoría</p>
          <p className="text-gray-300 text-sm mt-1">
            Vas a ver el horario asignado, los registros biométricos y el detalle del procesamiento
          </p>
        </div>
      )}

      {/* Loading */}
      {selectedCi && isLoading && (
        <div className="card-3d-static p-12 flex justify-center">
          <Loader2 size={28} className="animate-spin" style={{ color: '#003366' }} />
        </div>
      )}

      {/* Error */}
      {selectedCi && isError && (
        <div className="card-3d-static p-6 border-l-4 border-red-500">
          <p className="text-red-600 font-medium">No se pudo cargar la auditoría.</p>
          <p className="text-sm text-gray-500 mt-1">
            Verificá que el docente tenga datos procesados para el período seleccionado.
          </p>
        </div>
      )}

      {/* AUDIT DATA */}
      {data && !isLoading && (
        <>
          {/* Section A: Teacher Info + Summary */}
          <div className="card-3d-static p-5">
            <div className="flex items-center gap-4 mb-4">
              <div
                className="w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0"
                style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #004d99 100%)' }}
              >
                <span className="text-white text-lg font-bold">
                  {data.teacher_name?.[0] ?? '?'}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-lg" style={{ color: '#003366' }}>
                  {data.teacher_name}
                </h3>
                <p className="text-sm text-gray-500">
                  CI: {data.teacher_ci} · {MONTH_NAMES[data.month as number]} {data.year}
                </p>
              </div>
              <Badge
                className={
                  data.has_biometric
                    ? 'bg-green-100 text-green-700'
                    : 'bg-yellow-100 text-yellow-700'
                }
              >
                {data.has_biometric
                  ? `${data.biometric_records_count} registros biométricos`
                  : 'Sin biométrico'}
              </Badge>
              <Button
                variant="outline"
                size="sm"
                className="gap-2 border-[#0066CC] text-[#0066CC] hover:bg-blue-50"
                onClick={handleDownloadPDF}
                disabled={downloading}
              >
                {downloading ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Download size={14} />
                )}
                Descargar PDF
              </Button>
            </div>

            {/* Summary cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-green-50 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-green-700">{data.summary.attended}</p>
                <p className="text-xs text-green-600">Asistidos</p>
              </div>
              <div className="bg-yellow-50 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-yellow-700">{data.summary.late}</p>
                <p className="text-xs text-yellow-600">Tardanzas</p>
              </div>
              <div className="bg-red-50 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-red-700">{data.summary.absent}</p>
                <p className="text-xs text-red-600">Ausencias</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-gray-700">{data.summary.no_exit}</p>
                <p className="text-xs text-gray-600">Sin salida</p>
              </div>
            </div>

            {data.summary.total_slots > 0 && (
              <div className="mt-3 flex items-center gap-2">
                <div className="flex-1 bg-gray-100 rounded-full h-2">
                  <div
                    className="h-2 rounded-full"
                    style={{
                      width: `${data.summary.attendance_rate}%`,
                      backgroundImage: 'linear-gradient(90deg, #003366, #0066CC)',
                    }}
                  />
                </div>
                <span className="text-xs font-semibold" style={{ color: '#003366' }}>
                  {data.summary.attendance_rate}% asistencia
                </span>
              </div>
            )}
          </div>

          {/* Section B: Horario Asignado */}
          {data.schedule.length > 0 && (
            <div className="card-3d-static overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
                <Calendar size={16} style={{ color: '#003366' }} />
                <h4 className="font-semibold text-sm" style={{ color: '#003366' }}>
                  Horario Asignado
                </h4>
              </div>
              <div className="p-4 space-y-2">
                {data.schedule.map((s: any) => (
                  <div key={s.designation_id} className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="font-medium text-gray-800">{s.subject}</span>
                    <Badge className="bg-gray-100 text-gray-600 text-xs">{s.group_code}</Badge>
                    <Badge className="bg-blue-50 text-blue-600 text-xs">{s.semester}</Badge>
                    <div className="flex flex-wrap gap-1 ml-auto">
                      {(s.slots ?? []).map((slot: any, i: number) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 rounded-full bg-blue-50 border border-blue-200 text-xs text-blue-700"
                        >
                          {slot.dia} {slot.hora_inicio}–{slot.hora_fin}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section C: Detalle de Asistencia — AUDIT TABLE */}
          <div className="card-3d-static overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
              <ClipboardCheck size={16} style={{ color: '#003366' }} />
              <h4 className="font-semibold text-sm" style={{ color: '#003366' }}>
                Detalle de Asistencia — Auditoría
              </h4>
              <span className="ml-auto text-xs text-gray-400">
                {data.attendance_detail.length} registros
              </span>
            </div>

            {data.attendance_detail.length === 0 ? (
              <div className="p-10 text-center text-gray-400">
                <ClipboardCheck size={32} className="mx-auto mb-2 opacity-30" />
                <p>Sin registros de asistencia procesados para este período</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr
                      style={{
                        backgroundImage:
                          'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)',
                      }}
                    >
                      {[
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
                      ].map((h) => (
                        <th
                          key={h}
                          className="px-3 py-2.5 text-left text-white font-semibold text-xs whitespace-nowrap"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.attendance_detail.map((row: any, i: number) => (
                      <tr
                        key={i}
                        className={`border-b hover:bg-blue-50/50 transition-colors ${
                          row.status === 'ABSENT'
                            ? 'bg-red-50/30'
                            : row.status === 'LATE'
                              ? 'bg-yellow-50/30'
                              : i % 2 === 1
                                ? 'bg-gray-50/50'
                                : ''
                        }`}
                      >
                        <td className="px-3 py-2 text-gray-800 font-medium whitespace-nowrap">
                          {formatLocalDate(row.date)}
                        </td>
                        <td className="px-3 py-2 text-gray-600 capitalize whitespace-nowrap">
                          {row.day_name}
                        </td>
                        <td className="px-3 py-2 text-gray-700 max-w-[140px] truncate" title={row.subject}>
                          {row.subject}
                        </td>
                        <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{row.group_code}</td>
                        <td className="px-3 py-2 text-gray-700 font-mono whitespace-nowrap">
                          {row.scheduled_start} - {row.scheduled_end}
                        </td>
                        <td className="px-3 py-2 font-mono whitespace-nowrap">
                          {row.actual_entry ? (
                            <span
                              className={
                                row.status === 'LATE'
                                  ? 'text-yellow-600 font-semibold'
                                  : 'text-green-600'
                              }
                            >
                              {row.actual_entry}
                            </span>
                          ) : (
                            <span className="text-red-400">—</span>
                          )}
                        </td>
                        <td className="px-3 py-2 font-mono whitespace-nowrap">
                          {row.actual_exit ? (
                            <span className="text-gray-600">{row.actual_exit}</span>
                          ) : (
                            <span className="text-gray-300">—</span>
                          )}
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          <Badge
                            className={
                              row.status === 'ATTENDED'
                                ? 'bg-green-100 text-green-700'
                                : row.status === 'LATE'
                                  ? 'bg-yellow-100 text-yellow-700'
                                  : row.status === 'ABSENT'
                                    ? 'bg-red-100 text-red-700'
                                    : 'bg-gray-100 text-gray-700'
                            }
                          >
                            {row.status === 'ATTENDED'
                              ? 'Asistido'
                              : row.status === 'LATE'
                                ? 'Tardanza'
                                : row.status === 'ABSENT'
                                  ? 'Ausente'
                                  : 'Sin salida'}
                          </Badge>
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          {row.late_minutes > 0 ? (
                            <span className="text-yellow-600 font-semibold">
                              {row.late_minutes} min
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="px-3 py-2 text-center font-semibold whitespace-nowrap">
                          {row.academic_hours}h
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          {row.has_biometric_link ? (
                            <span className="text-green-600 text-xs">✓ Vinculado</span>
                          ) : (
                            <span className="text-red-400 text-xs">✗ Sin registro</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-500 max-w-[200px]">
                          {row.explanation}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Section D: Raw Biometric Records */}
          <div className="card-3d-static overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
              <Fingerprint size={16} style={{ color: '#003366' }} />
              <h4 className="font-semibold text-sm" style={{ color: '#003366' }}>
                Registros Biométricos Originales ({data.biometric_raw.length})
              </h4>
            </div>
            {data.biometric_raw.length > 0 ? (
              <div className="p-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200">
                      {['Fecha', 'Entrada', 'Salida', 'Minutos Trabajados'].map((h) => (
                        <th
                          key={h}
                          className="px-3 py-2 text-left text-gray-500 text-xs uppercase tracking-wide"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.biometric_raw.map((bio: any, i: number) => (
                      <tr
                        key={i}
                        className={`border-b last:border-0 hover:bg-gray-50 ${i % 2 === 1 ? 'bg-gray-50/50' : ''}`}
                      >
                        <td className="px-3 py-2 text-gray-800">{formatLocalDate(bio.date)}</td>
                        <td className="px-3 py-2 font-mono text-gray-700">
                          {bio.entry_time ?? '—'}
                        </td>
                        <td className="px-3 py-2 font-mono text-gray-700">
                          {bio.exit_time ?? '—'}
                        </td>
                        <td className="px-3 py-2 text-gray-600">
                          {bio.worked_minutes != null ? `${bio.worked_minutes} min` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center text-gray-400">
                <Fingerprint size={32} className="mx-auto mb-2 opacity-30" />
                <p>Sin registros biométricos para este período</p>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
