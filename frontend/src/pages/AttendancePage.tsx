import { useState, useEffect } from 'react'
import { ClipboardCheck, Loader2, Info } from 'lucide-react'
import {
  useAttendance,
  useAttendanceSummary,
  useProcessAttendance,
} from '@/api/hooks/useAttendance'
import { useUploadHistory, useBiometricDateRange } from '@/api/hooks/useBiometric'
import { StatCard } from '@/components/shared/StatCard'
import { DataTable } from '@/components/shared/DataTable'
import { LoadingPage } from '@/components/shared/LoadingSpinner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { AttendanceWithDetails } from '@/api/types'
import type { Column } from '@/components/shared/DataTable'
import { Users, AlertTriangle, XCircle, Clock } from 'lucide-react'

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`
}

function formatTime(timeStr: string | null): string {
  if (!timeStr) return '—'
  return timeStr.slice(0, 5)
}

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  ATTENDED: { label: 'Asistió', className: 'bg-green-100 text-green-700' },
  LATE: { label: 'Tardanza', className: 'bg-yellow-100 text-yellow-700' },
  ABSENT: { label: 'Ausente', className: 'bg-red-100 text-red-700' },
  NO_EXIT: { label: 'Sin Salida', className: 'bg-orange-100 text-orange-700' },
}

const attendanceColumns: Column<AttendanceWithDetails>[] = [
  {
    key: 'teacher_name',
    header: 'Docente',
    render: (item) => (
      <span className="font-medium">{item.teacher_name ?? item.teacher_ci}</span>
    ),
  },
  { key: 'subject', header: 'Materia' },
  { key: 'group_code', header: 'Grupo' },
  {
    key: 'date',
    header: 'Fecha',
    render: (item) => formatDate(item.date),
  },
  {
    key: 'scheduled_start',
    header: 'Horario',
    render: (item) => `${formatTime(item.scheduled_start)} - ${formatTime(item.scheduled_end)}`,
  },
  {
    key: 'actual_entry',
    header: 'Entrada',
    render: (item) => formatTime(item.actual_entry),
  },
  {
    key: 'status',
    header: 'Estado',
    render: (item) => {
      const cfg = STATUS_CONFIG[item.status] ?? { label: item.status, className: 'bg-gray-100 text-gray-700' }
      return <Badge className={cfg.className}>{cfg.label}</Badge>
    },
  },
  {
    key: 'academic_hours',
    header: 'Horas',
    render: (item) => `${item.academic_hours}h`,
  },
]

export function AttendancePage() {
  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1

  const [month, setMonth] = useState<number>(currentMonth)
  const [year, setYear] = useState<number>(currentYear)
  const [page, setPage] = useState(1)
  const [processed, setProcessed] = useState(false)
  const [selectedUploadId, setSelectedUploadId] = useState<number | null>(null)
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [datesManuallySet, setDatesManuallySet] = useState(false)

  const { data: bioRange } = useBiometricDateRange(month, year)

  // Reset manual flag when month/year changes so auto-fill can run again
  useEffect(() => {
    setDatesManuallySet(false)
  }, [month, year])

  // Auto-fill dates from biometric range when available
  useEffect(() => {
    if (!datesManuallySet && bioRange?.has_data && bioRange.suggested_start && bioRange.suggested_end) {
      setStartDate(bioRange.suggested_start)
      setEndDate(bioRange.suggested_end)
    } else if (!datesManuallySet && bioRange !== undefined && !bioRange.has_data) {
      // No biometric data: fall back to standard cut-off period
      const prevMonth = month === 1 ? 12 : month - 1
      const prevYear = month === 1 ? year - 1 : year
      setStartDate(`${prevYear}-${String(prevMonth).padStart(2, '0')}-21`)
      setEndDate(`${year}-${String(month).padStart(2, '0')}-20`)
    }
  }, [bioRange, datesManuallySet, month, year])

  const { data: uploads } = useUploadHistory()
  const processAttendance = useProcessAttendance()

  const { data: summary, isLoading: summaryLoading } = useAttendanceSummary(month, year)
  const { data: records, isLoading: recordsLoading } = useAttendance({
    month,
    year,
    page,
    perPage: 15,
  })

  const totalPages = records ? Math.ceil(records.total / 15) : 1

  const handleProcess = () => {
    if (!selectedUploadId) return
    processAttendance.mutate(
      {
        upload_id: selectedUploadId,
        month,
        year,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      },
      { onSuccess: () => setProcessed(true) },
    )
  }

  const hasData = summary && (summary.attended + summary.late + summary.absent + summary.no_exit > 0)

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="card-3d-static overflow-hidden">
        <div className="py-4 px-6">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Mes</label>
              <select
                value={month}
                onChange={(e) => { setMonth(Number(e.target.value)); setPage(1) }}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] min-w-[130px]"
              >
                {Object.entries(MONTH_NAMES).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Año</label>
              <input
                type="number"
                value={year}
                onChange={(e) => { setYear(Number(e.target.value)); setPage(1) }}
                min={2020}
                max={2030}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] w-24"
              />
            </div>

            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Upload biométrico</label>
              <select
                value={selectedUploadId ?? ''}
                onChange={(e) => setSelectedUploadId(e.target.value ? Number(e.target.value) : null)}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] min-w-[200px]"
              >
                <option value="">Seleccioná un upload</option>
                {uploads?.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.filename} — {MONTH_NAMES[u.month]} {u.year}
                  </option>
                ))}
              </select>
            </div>

            <Button
              onClick={handleProcess}
              disabled={!selectedUploadId || processAttendance.isPending}
              className="h-10"
              style={{ backgroundColor: '#003366' }}
            >
              {processAttendance.isPending ? (
                <>
                  <Loader2 size={16} className="animate-spin mr-2" />
                  Procesando...
                </>
              ) : (
                <>
                  <ClipboardCheck size={16} className="mr-2" />
                  Procesar Asistencia
                </>
              )}
            </Button>
          </div>

          <div className="mt-4 pt-4 bg-gray-50/50 rounded-lg p-4">
            <p className="text-sm text-gray-500 mb-2 font-medium">Período de corte</p>

            {/* Biometric Coverage Info */}
            {bioRange && (
              <div className={`flex items-start gap-2 p-3 rounded-lg border mb-3 ${
                bioRange.has_data ? 'bg-blue-50 border-blue-200' : 'bg-yellow-50 border-yellow-200'
              }`}>
                {bioRange.has_data ? (
                  <>
                    <Info size={16} className="text-blue-500 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-sm text-blue-700 font-medium">Rango biométrico detectado</p>
                      <p className="text-xs text-blue-600 mt-0.5">{bioRange.message}</p>
                      <p className="text-xs text-blue-500 mt-1">
                        Las fechas de inicio y fin se han ajustado automáticamente al rango del biométrico.
                        Puede modificarlas si lo necesita.
                      </p>
                    </div>
                  </>
                ) : (
                  <>
                    <AlertTriangle size={16} className="text-yellow-500 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-sm text-yellow-700 font-medium">Sin datos biométricos</p>
                      <p className="text-xs text-yellow-600 mt-0.5">{bioRange.message}</p>
                    </div>
                  </>
                )}
              </div>
            )}

            <div className="flex items-end gap-4 flex-wrap">
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Fecha inicio</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => { setStartDate(e.target.value); setDatesManuallySet(true) }}
                  className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Fecha fin</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => { setEndDate(e.target.value); setDatesManuallySet(true) }}
                  className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
                />
              </div>
              <p className="text-xs text-gray-400 self-center">
                Estándar: del 21 del mes anterior al 20 del mes actual
              </p>
            </div>

            {/* Warning: dates extend beyond biometric coverage */}
            {bioRange?.has_data && startDate && endDate &&
              (startDate < (bioRange.suggested_start ?? '') || endDate > (bioRange.suggested_end ?? '')) && (
              <div className="flex items-start gap-2 p-3 bg-orange-50 rounded-lg border border-orange-200 mt-2">
                <AlertTriangle size={16} className="text-orange-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm text-orange-700 font-medium">Rango extendido más allá del biométrico</p>
                  <p className="text-xs text-orange-600 mt-0.5">
                    El rango seleccionado ({startDate} — {endDate}) excede la cobertura del biométrico
                    ({bioRange.suggested_start} — {bioRange.suggested_end}). Los días sin cobertura generarán
                    ausencias para todos los docentes con biométrico.
                  </p>
                </div>
              </div>
            )}
          </div>

          {processAttendance.isError && (
            <p className="text-red-500 text-sm mt-3">
              Error al procesar. Verificá que el upload corresponda al mes seleccionado.
            </p>
          )}
          {(processAttendance.isSuccess || processed) && (
            <p className="text-green-600 text-sm mt-3 font-medium">
              ✓ Asistencia procesada exitosamente
            </p>
          )}
        </div>
      </div>

      {/* Summary Cards */}
      {summaryLoading ? (
        <LoadingPage />
      ) : hasData ? (
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
          <div>
            <StatCard
              icon={Users}
              title="Asistencias"
              value={summary.attended}
              color="#16a34a"
            />
          </div>
          <div>
            <StatCard
              icon={Clock}
              title="Tardanzas"
              value={summary.late}
              color="#d97706"
            />
          </div>
          <div>
            <StatCard
              icon={XCircle}
              title="Ausencias"
              value={summary.absent}
              color="#dc2626"
            />
          </div>
          <div>
            <StatCard
              icon={AlertTriangle}
              title="Sin Salida"
              value={summary.no_exit}
              color="#ea580c"
            />
          </div>
        </div>
      ) : (
        <div className="bg-gray-50 rounded-lg border-2 border-dashed border-gray-200 py-16 text-center">
          <ClipboardCheck size={40} className="mx-auto text-gray-300 mb-3" />
          <p className="text-gray-500 font-medium">
            Seleccioná un mes y procesá la asistencia para ver los resultados
          </p>
          <p className="text-gray-400 text-sm mt-1">
            Asegurate de haber subido el reporte biométrico primero
          </p>
        </div>
      )}

      {/* Records Table */}
      {hasData && (
        <div className="card-3d-static overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
              Registros de Asistencia — {MONTH_NAMES[month]} {year}
            </h3>
          </div>
          <div className="p-5">
            {recordsLoading ? (
              <LoadingPage />
            ) : (
              <DataTable
                columns={attendanceColumns}
                data={records?.items ?? []}
                page={page}
                totalPages={totalPages}
                onPageChange={setPage}
                emptyMessage="No hay registros para este período"
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
