import { useState } from 'react'
import {
  FileSpreadsheet,
  Download,
  Loader2,
  CheckCircle,
  Users,
  Search,
  History,
  Calendar,
  AlertTriangle,
} from 'lucide-react'
import {
  useGeneratePracticePlanilla,
  usePracticePlanillaHistory,
  usePracticePlanillaDetail,
  downloadPracticePlanilla,
  downloadPracticeSalaryReport,
} from '@/api/hooks/usePracticePlanilla'
import type { PracticePlanillaGenerateResponse } from '@/api/hooks/usePracticePlanilla'
import { LoadingPage } from '@/components/shared/LoadingSpinner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`
}

function formatShortDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`
}

export function PracticePlanillaPage() {
  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1

  const [month, setMonth] = useState<number>(currentMonth)
  const [year, setYear] = useState<number>(currentYear)
  const [lastResult, setLastResult] = useState<PracticePlanillaGenerateResponse | null>(null)
  const [startDate, setStartDate] = useState<string>(() => {
    const prevMonth = currentMonth === 1 ? 12 : currentMonth - 1
    const prevYear = currentMonth === 1 ? currentYear - 1 : currentYear
    return `${prevYear}-${String(prevMonth).padStart(2, '0')}-21`
  })
  const [endDate, setEndDate] = useState<string>(
    () => `${currentYear}-${String(currentMonth).padStart(2, '0')}-20`,
  )
  const [showDetail, setShowDetail] = useState(true)
  const [showHistory, setShowHistory] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [discountMode, setDiscountMode] = useState<'attendance' | 'full'>('attendance')

  const [salaryReportLoading, setSalaryReportLoading] = useState<Record<string, boolean>>({})

  const generatePlanilla = useGeneratePracticePlanilla()
  const { data: history, isLoading: historyLoading } = usePracticePlanillaHistory()
  const { data: detail, isLoading: detailLoading } = usePracticePlanillaDetail(
    month,
    year,
    showDetail,
    startDate || undefined,
    endDate || undefined,
    discountMode,
  )

  // Recalculate default dates when month/year changes
  const handleMonthChange = (newMonth: number) => {
    setMonth(newMonth)
    const prevM = newMonth === 1 ? 12 : newMonth - 1
    const prevY = newMonth === 1 ? year - 1 : year
    setStartDate(`${prevY}-${String(prevM).padStart(2, '0')}-21`)
    setEndDate(`${year}-${String(newMonth).padStart(2, '0')}-20`)
  }

  const handleYearChange = (newYear: number) => {
    setYear(newYear)
    const prevM = month === 1 ? 12 : month - 1
    const prevY = month === 1 ? newYear - 1 : newYear
    setStartDate(`${prevY}-${String(prevM).padStart(2, '0')}-21`)
    setEndDate(`${newYear}-${String(month).padStart(2, '0')}-20`)
  }

  const handleGenerate = () => {
    setLastResult(null)
    generatePlanilla.mutate(
      {
        month,
        year,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        discount_mode: discountMode,
      },
      {
        onSuccess: (data) => setLastResult(data),
      },
    )
  }

  return (
    <div className="space-y-6">
      {/* Generator Card */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-6 py-5 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg gradient-stat-navy flex items-center justify-center">
              <FileSpreadsheet size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold" style={{ color: '#003366' }}>
                Planilla Docentes Asistenciales
              </h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Practicas Internas — Generacion y gestion de planilla de haberes
              </p>
            </div>
          </div>
        </div>
        <div className="px-6 py-5">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Mes</label>
              <select
                value={month}
                onChange={(e) => handleMonthChange(Number(e.target.value))}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] min-w-[130px]"
              >
                {Object.entries(MONTH_NAMES).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Ano</label>
              <input
                type="number"
                value={year}
                onChange={(e) => handleYearChange(Number(e.target.value))}
                min={2020}
                max={2030}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] w-24"
              />
            </div>

            <Button
              onClick={handleGenerate}
              disabled={generatePlanilla.isPending}
              className="h-10"
              style={{ backgroundColor: '#003366' }}
            >
              {generatePlanilla.isPending ? (
                <>
                  <Loader2 size={16} className="animate-spin mr-2" />
                  Generando...
                </>
              ) : (
                <>
                  <FileSpreadsheet size={16} className="mr-2" />
                  Generar Planilla
                </>
              )}
            </Button>
          </div>

          {/* Cut-off period */}
          <div className="mt-4 bg-gray-50/50 rounded-lg p-4">
            <p className="text-sm text-gray-500 mb-2 font-medium">Periodo de corte</p>
            <div className="flex items-end gap-4 flex-wrap">
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Fecha inicio</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Fecha fin</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
                />
              </div>
              <p className="text-xs text-gray-400 self-center">
                Estandar: del 21 del mes anterior al 20 del mes actual
              </p>
            </div>
          </div>

          {/* Discount Mode Switch */}
          <div className="mt-4 bg-gray-50/50 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-700">Modo de calculo</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {discountMode === 'attendance'
                    ? 'Se aplican descuentos por ausencias registradas'
                    : 'Todos los docentes cobran el 100% de sus horas asignadas (sin descuentos)'}
                </p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={discountMode === 'full'}
                onClick={() => setDiscountMode(prev => prev === 'attendance' ? 'full' : 'attendance')}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-[#0066CC] focus:ring-offset-2 ${
                  discountMode === 'full' ? 'bg-[#0066CC]' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    discountMode === 'full' ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
            <div className="mt-2 flex items-center gap-2">
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                discountMode === 'attendance'
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-green-100 text-green-700'
              }`}>
                {discountMode === 'attendance' ? 'Con descuentos' : 'Sin descuentos — pago completo'}
              </span>
            </div>
            {discountMode === 'full' && (
              <div className="flex items-start gap-2 p-3 bg-amber-50 rounded-lg border border-amber-200 mt-3">
                <AlertTriangle size={16} className="text-amber-500 mt-0.5 flex-shrink-0" />
                <p className="text-xs text-amber-700">
                  <strong>Atencion:</strong> En este modo no se aplicaran descuentos por ausencias.
                  Todos los docentes recibiran el monto total correspondiente a sus horas asignadas.
                </p>
              </div>
            )}
          </div>

          {generatePlanilla.isError && (
            <div className="mt-4 p-3 bg-red-50 rounded-lg border border-red-200">
              <p className="text-sm text-red-600">
                Error al generar la planilla. Verifica que la asistencia este procesada para el periodo seleccionado.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Result Card */}
      {lastResult && (
        <div
          className="card-3d-static overflow-hidden border-l-4"
          style={{ borderLeftColor: '#16a34a' }}
        >
          <div className="py-5 px-5">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <CheckCircle size={24} className="text-green-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-green-700">
                    Planilla de practicas generada exitosamente!
                  </p>
                  <p className="text-sm text-gray-600 mt-1">
                    {MONTH_NAMES[lastResult.month]} {lastResult.year} · {lastResult.total_teachers} docentes · {lastResult.total_hours}h totales
                  </p>
                  <p className="text-lg font-bold mt-2" style={{ color: '#003366' }}>
                    Total: Bs {parseFloat(lastResult.total_payment).toFixed(2)}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    Tarifa por hora: {detail?.rows?.[0]?.rate_per_hour ?? '50'} Bs
                  </p>
                  {lastResult.warnings.length > 0 && (
                    <div className="mt-2">
                      <p className="text-xs text-yellow-600 font-medium">
                        {lastResult.warnings.length} advertencia(s):
                      </p>
                      <ul className="text-xs text-yellow-600 mt-1 space-y-0.5">
                        {lastResult.warnings.map((w, i) => (
                          <li key={i}>- {w}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
              {lastResult.file_path && (
                <div className="flex items-center gap-2 flex-wrap">
                  <Button
                    variant="outline"
                    className="border-[#0066CC] text-[#0066CC] hover:bg-blue-50 gap-2"
                    onClick={() => void downloadPracticePlanilla(lastResult.planilla_id)}
                  >
                    <Download size={16} />
                    Descargar Excel
                  </Button>
                  <button
                    onClick={async () => {
                      setSalaryReportLoading(prev => ({ ...prev, current: true }))
                      try {
                        await downloadPracticeSalaryReport({
                          month: lastResult.month,
                          year: lastResult.year,
                          discount_mode: discountMode,
                          start_date: startDate || undefined,
                          end_date: endDate || undefined,
                        })
                      } finally {
                        setSalaryReportLoading(prev => ({ ...prev, current: false }))
                      }
                    }}
                    disabled={salaryReportLoading.current}
                    className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm font-medium"
                  >
                    {salaryReportLoading.current ? <Loader2 size={16} className="animate-spin" /> : <FileSpreadsheet size={16} />}
                    Planilla Salarios
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Detail Section */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 flex items-center justify-between border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg gradient-stat-navy flex items-center justify-center">
              <Users size={16} className="text-white" />
            </div>
            <div>
              <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
                Detalle por Docente
              </h3>
              <p className="text-xs text-gray-500">
                {detail ? `${detail.total_teachers} docentes` : 'Cargando...'} · {MONTH_NAMES[month]} {year}
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowDetail(!showDetail)}
            className="text-sm text-[#0066CC] hover:underline font-medium"
          >
            {showDetail ? 'Ocultar detalle' : 'Ver detalle'}
          </button>
        </div>

        {showDetail && (
          <div className="p-5">
            {detailLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 size={24} className="animate-spin text-[#003366]" />
              </div>
            ) : detail ? (
              <div className="space-y-4">
                {/* Summary stats */}
                <div className="grid grid-cols-4 gap-3">
                  <div className="bg-blue-50/50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold" style={{ color: '#003366' }}>{detail.total_teachers}</p>
                    <p className="text-xs text-gray-500">Docentes</p>
                  </div>
                  <div className="bg-blue-50/50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold" style={{ color: '#003366' }}>
                      Bs {detail.total_gross.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                    </p>
                    <p className="text-xs text-gray-500">Total Bruto</p>
                  </div>
                  <div className="bg-red-50/50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-red-600">
                      Bs {detail.total_retention.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                    </p>
                    <p className="text-xs text-gray-500">Retenciones</p>
                  </div>
                  <div className="bg-green-50/50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-green-700">
                      Bs {detail.total_net.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                    </p>
                    <p className="text-xs text-gray-500">Total Neto</p>
                  </div>
                </div>

                {/* Warnings */}
                {detail.warnings.length > 0 && (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                    <p className="text-sm font-medium text-yellow-800">Advertencias:</p>
                    <ul className="text-xs text-yellow-700 mt-1 space-y-0.5">
                      {detail.warnings.map((w, i) => (
                        <li key={i}>- {w}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Search */}
                <div className="relative max-w-sm">
                  <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="Buscar docente por nombre o CI..."
                    className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] focus:border-transparent bg-gray-50/50"
                  />
                </div>

                {/* Detail table */}
                <div className="overflow-x-auto rounded-lg border border-gray-200">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)' }}>
                        {['Docente', 'Materia', 'Grupo', 'Sem.', 'Hrs Base', 'Hrs Ausentes', 'Hrs Pagables', 'Monto (Bs)', 'Retencion', 'Neto (Bs)', 'Observacion'].map(h => (
                          <th key={h} className="text-left text-white font-semibold text-xs uppercase tracking-wider px-3 py-2.5">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {detail.rows
                        .filter(row => {
                          if (!searchTerm) return true
                          const term = searchTerm.toLowerCase()
                          return row.teacher_name.toLowerCase().includes(term) || row.teacher_ci.includes(term)
                        })
                        .map((row, i) => (
                          <tr
                            key={`${row.teacher_ci}-${row.subject}-${row.group_code}`}
                            className={`border-b last:border-0 hover:bg-blue-50/70 transition-colors ${i % 2 === 1 ? 'bg-gray-50' : 'bg-white'}`}
                          >
                            <td className="px-3 py-2.5 font-medium text-gray-800 max-w-[200px] truncate">{row.teacher_name}</td>
                            <td className="px-3 py-2.5 text-gray-700 max-w-[180px] truncate">{row.subject}</td>
                            <td className="px-3 py-2.5 text-gray-600">{row.group_code}</td>
                            <td className="px-3 py-2.5 text-gray-600">{row.semester}</td>
                            <td className="px-3 py-2.5 text-gray-700 font-medium">{row.base_monthly_hours}h</td>
                            <td className="px-3 py-2.5">
                              {row.absent_hours > 0 ? (
                                <span className="text-red-600 font-medium">-{row.absent_hours}h</span>
                              ) : (
                                <span className="text-green-600">0h</span>
                              )}
                            </td>
                            <td className="px-3 py-2.5 text-gray-800 font-semibold">{row.payable_hours}h</td>
                            <td className="px-3 py-2.5 font-bold" style={{ color: '#003366' }}>
                              {row.calculated_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                            </td>
                            <td className="px-3 py-2.5">
                              {row.has_retention ? (
                                <span className="text-red-600 font-medium">
                                  -{row.retention_amount.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                                </span>
                              ) : (
                                <span className="text-gray-400">—</span>
                              )}
                            </td>
                            <td className="px-3 py-2.5 font-bold text-green-700">
                              {row.final_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                            </td>
                            <td className="px-3 py-2.5 text-gray-500 text-xs max-w-[150px] truncate" title={row.observation}>
                              {row.observation || '—'}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                    {/* Totals row */}
                    <tfoot>
                      <tr className="bg-gray-100 font-semibold border-t-2 border-gray-300">
                        <td colSpan={7} className="px-3 py-2.5 text-right text-gray-700">Totales:</td>
                        <td className="px-3 py-2.5 font-bold" style={{ color: '#003366' }}>
                          {detail.total_gross.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-3 py-2.5 font-bold text-red-600">
                          -{detail.total_retention.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-3 py-2.5 font-bold text-green-700">
                          {detail.total_net.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                        </td>
                        <td />
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>
            ) : (
              <div className="text-center py-10 text-gray-400 text-sm">
                No hay datos para {MONTH_NAMES[month]} {year}. Genera la planilla para ver el detalle.
              </div>
            )}
          </div>
        )}
      </div>

      {/* History */}
      <div className="card-3d-static overflow-hidden">
        <div
          className="px-5 py-4 border-b border-gray-100 flex items-center justify-between cursor-pointer"
          onClick={() => setShowHistory(!showHistory)}
        >
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg gradient-stat-navy flex items-center justify-center">
              <History size={16} className="text-white" />
            </div>
            <div>
              <h3 className="text-base font-semibold" style={{ color: '#003366' }}>Historial de Planillas</h3>
              <p className="text-xs text-gray-500">
                {history ? `${history.length} planilla(s) generada(s)` : 'Cargando...'}
              </p>
            </div>
          </div>
          <button className="text-sm text-[#0066CC] hover:underline font-medium">
            {showHistory ? 'Ocultar' : 'Mostrar'}
          </button>
        </div>
        {showHistory && (
          <div className="p-0">
            {historyLoading ? (
              <div className="p-5">
                <LoadingPage />
              </div>
            ) : !history || history.length === 0 ? (
              <div className="text-center py-10 text-gray-400 text-sm">
                No hay planillas de practicas generadas aun
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)' }}>
                      {['Periodo', 'Corte', 'Generada el', 'Docentes', 'Horas', 'Total (Bs)', 'Estado', 'Descarga'].map(h => (
                        <th key={h} className="text-left text-white font-semibold text-xs uppercase tracking-wider px-4 py-3 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((item, i) => (
                      <tr
                        key={item.id}
                        className={`border-b last:border-0 hover:bg-blue-50/70 transition-colors cursor-pointer ${i % 2 === 1 ? 'bg-gray-50/60' : 'bg-white'}`}
                        onClick={() => {
                          setMonth(item.month)
                          setYear(item.year)
                          setShowDetail(true)
                        }}
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <Calendar size={14} className="text-[#0066CC] flex-shrink-0" />
                            <span className="font-semibold text-gray-800">{MONTH_NAMES[item.month]} {item.year}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
                          {item.start_date && item.end_date
                            ? `${formatShortDate(item.start_date)} — ${formatShortDate(item.end_date)}`
                            : <span className="text-gray-300">—</span>
                          }
                        </td>
                        <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{formatDate(item.generated_at)}</td>
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center gap-1 text-gray-700 font-medium">
                            <Users size={13} className="text-gray-400" />
                            {item.total_teachers}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-700 font-medium">{item.total_hours}h</td>
                        <td className="px-4 py-3">
                          <span className="font-bold" style={{ color: '#003366' }}>
                            {parseFloat(item.total_payment).toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <Badge className="bg-green-100 text-green-700 text-xs">
                            {item.status === 'generated' ? 'Generada' : item.status}
                          </Badge>
                        </td>
                        <td className="px-4 py-3">
                          {item.file_path ? (
                            <div className="flex items-center gap-1 flex-wrap">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  void downloadPracticePlanilla(item.id)
                                }}
                                className="inline-flex items-center gap-1 px-2 py-1 rounded text-[#0066CC] hover:bg-blue-50 border border-[#0066CC]/30 text-xs font-medium transition-colors"
                              >
                                <Download size={12} />
                                Excel
                              </button>
                              <button
                                onClick={async (e) => {
                                  e.stopPropagation()
                                  const key = `row-${item.id}`
                                  setSalaryReportLoading(prev => ({ ...prev, [key]: true }))
                                  try {
                                    await downloadPracticeSalaryReport({
                                      month: item.month,
                                      year: item.year,
                                      discount_mode: item.discount_mode,
                                    })
                                  } finally {
                                    setSalaryReportLoading(prev => ({ ...prev, [key]: false }))
                                  }
                                }}
                                disabled={salaryReportLoading[`row-${item.id}`]}
                                className="inline-flex items-center gap-1 px-2 py-1 rounded text-green-700 hover:bg-green-50 border border-green-600/30 text-xs font-medium transition-colors disabled:opacity-50"
                              >
                                {salaryReportLoading[`row-${item.id}`]
                                  ? <Loader2 size={12} className="animate-spin" />
                                  : <FileSpreadsheet size={12} />}
                                Salarios
                              </button>
                            </div>
                          ) : (
                            <span className="text-gray-300 text-xs">No disponible</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
