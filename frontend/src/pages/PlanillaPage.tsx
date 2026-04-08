import { useState, useEffect } from 'react'
import { FileSpreadsheet, Download, Loader2, CheckCircle, XCircle, Clock, Users, Search, Send, EyeOff, Pencil, Check, X, History, Calendar } from 'lucide-react'
import { useGeneratePlanilla, usePlanillaHistory, downloadPlanilla, usePlanillaDetail, useApprovePlanilla, useRejectPlanilla, usePlanillaStatus } from '@/api/hooks/usePlanilla'
import { usePublicationStatus, usePublishBilling, useUnpublishBilling } from '@/api/hooks/useBillingPublication'
import { LoadingPage } from '@/components/shared/LoadingSpinner'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { PlanillaGenerateResponse } from '@/api/types'

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

export function PlanillaPage() {
  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1

  const [month, setMonth] = useState<number>(currentMonth)
  const [year, setYear] = useState<number>(currentYear)
  const [lastResult, setLastResult] = useState<PlanillaGenerateResponse | null>(null)
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [showDetail] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [detailTab, setDetailTab] = useState<'designations' | 'teachers'>('teachers')

  // Payment override state
  const [paymentOverrides, setPaymentOverrides] = useState<Record<string, number>>({})
  const [editingOverride, setEditingOverride] = useState<string | null>(null)
  const [overrideValue, setOverrideValue] = useState('')

  useEffect(() => {
    if (month === 3 && year === 2026) {
      setStartDate('2026-03-02')
      setEndDate('2026-03-20')
    } else {
      const prevMonth = month === 1 ? 12 : month - 1
      const prevYear = month === 1 ? year - 1 : year
      setStartDate(`${prevYear}-${String(prevMonth).padStart(2, '0')}-21`)
      setEndDate(`${year}-${String(month).padStart(2, '0')}-20`)
    }
  }, [month, year])

  const generatePlanilla = useGeneratePlanilla()
  const { data: history, isLoading: historyLoading } = usePlanillaHistory()
  const { data: detail, isLoading: detailLoading } = usePlanillaDetail(month, year, showDetail, startDate || undefined, endDate || undefined)
  const { data: publication } = usePublicationStatus(month, year)
  const { data: planillaStatus } = usePlanillaStatus(month, year)
  const publishBilling = usePublishBilling()
  const unpublishBilling = useUnpublishBilling()
  const approvePlanilla = useApprovePlanilla()
  const rejectPlanilla = useRejectPlanilla()

  const handleGenerate = () => {
    setLastResult(null)
    generatePlanilla.mutate(
      {
        month,
        year,
        payment_overrides: paymentOverrides,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
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
          <h2 className="text-lg font-semibold" style={{ color: '#003366' }}>Generar Planilla de Pagos</h2>
          <p className="text-sm text-gray-500 mt-0.5">Seleccioná el período y generá la planilla de haberes docentes</p>
        </div>
        <div className="px-6 py-5">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Mes</label>
              <select
                value={month}
                onChange={(e) => setMonth(Number(e.target.value))}
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
                onChange={(e) => setYear(Number(e.target.value))}
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

          {Object.keys(paymentOverrides).length > 0 && (
            <div className="mt-3 bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm">
              <p className="font-medium text-yellow-800">
                {Object.keys(paymentOverrides).length} ajuste(s) de monto pendiente(s)
              </p>
              <p className="text-yellow-600 text-xs mt-1">
                Estos ajustes se aplicarán al generar la planilla
              </p>
            </div>
          )}

          <div className="mt-4 bg-gray-50/50 rounded-lg p-4">
            <p className="text-sm text-gray-500 mb-2 font-medium">Período de corte</p>
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
                Estándar: del 21 del mes anterior al 20 del mes actual
              </p>
            </div>
          </div>

          {generatePlanilla.isError && (
            <div className="mt-4 p-3 bg-red-50 rounded-lg border border-red-200">
              <p className="text-sm text-red-600">
                Error al generar la planilla. Verificá que la asistencia esté procesada para el período seleccionado.
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
                    ¡Planilla generada exitosamente!
                  </p>
                  <p className="text-sm text-gray-600 mt-1">
                    {MONTH_NAMES[lastResult.month]} {lastResult.year} · {lastResult.total_teachers} docentes · {lastResult.total_hours}h totales
                  </p>
                  <p className="text-lg font-bold mt-2" style={{ color: '#003366' }}>
                    Total: Bs {parseFloat(lastResult.total_payment).toFixed(2)}
                  </p>
                  {lastResult.warnings.length > 0 && (
                    <p className="text-xs text-yellow-600 mt-1">
                      {lastResult.warnings.length} advertencia(s) durante la generación
                    </p>
                  )}
                </div>
              </div>
              {lastResult.file_path && (
                <Button
                  variant="outline"
                  className="border-[#0066CC] text-[#0066CC] hover:bg-blue-50 gap-2"
                  onClick={() => void downloadPlanilla(lastResult.planilla_id, `planilla_${MONTH_NAMES[lastResult.month]}_${lastResult.year}.xlsx`)}
                >
                  <Download size={16} />
                  Descargar Excel
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Approval Status — show when there is a planilla for this period */}
      {planillaStatus && (
        <div className="card-3d-static overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                planillaStatus.status === 'approved' ? 'bg-green-100' :
                planillaStatus.status === 'rejected' ? 'bg-red-100' : 'bg-yellow-100'
              }`}>
                {planillaStatus.status === 'approved'
                  ? <CheckCircle size={16} className="text-green-600" />
                  : planillaStatus.status === 'rejected'
                    ? <XCircle size={16} className="text-red-600" />
                    : <Clock size={16} className="text-yellow-600" />
                }
              </div>
              <div>
                <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
                  Estado de la Planilla
                </h3>
                <p className="text-xs text-gray-500">
                  {planillaStatus.status === 'approved'
                    ? 'Aprobada — lista para publicar'
                    : planillaStatus.status === 'rejected'
                      ? 'Rechazada — requiere regeneración'
                      : 'Pendiente de aprobación'}
                </p>
              </div>
            </div>

            {planillaStatus.status === 'generated' && (
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  className="bg-green-600 hover:bg-green-700 text-white gap-1"
                  onClick={() => approvePlanilla.mutate(planillaStatus.id)}
                  disabled={approvePlanilla.isPending}
                >
                  <Check size={14} /> Aprobar
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="border-red-300 text-red-600 hover:bg-red-50 gap-1"
                  onClick={() => rejectPlanilla.mutate(planillaStatus.id)}
                  disabled={rejectPlanilla.isPending}
                >
                  <X size={14} /> Rechazar
                </Button>
              </div>
            )}

            {planillaStatus.status === 'approved' && (
              <span className="text-sm text-green-700 font-medium">✅ Lista para publicar</span>
            )}

            {planillaStatus.status === 'rejected' && (
              <span className="text-sm text-red-600 font-medium">❌ Regenerá la planilla</span>
            )}
          </div>
        </div>
      )}

      {/* Publication Status — at the top so admin doesn't need to scroll */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
              publication?.status === 'published' ? 'bg-green-100' : 'bg-gray-100'
            }`}>
              {publication?.status === 'published'
                ? <Send size={16} className="text-green-600" />
                : <EyeOff size={16} className="text-gray-400" />
              }
            </div>
            <div>
              <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
                Publicación de Facturación
              </h3>
              <p className="text-xs text-gray-500">
                {MONTH_NAMES[month]} {year} — {
                  publication?.status === 'published'
                    ? `Publicado el ${new Date(publication.published_at!).toLocaleDateString('es-BO')}`
                    : 'No publicado para docentes'
                }
              </p>
            </div>
          </div>

          {publication?.status === 'published' ? (
            <Button
              variant="outline"
              className="border-red-300 text-red-600 hover:bg-red-50 gap-2"
              onClick={() => unpublishBilling.mutate({ month, year })}
              disabled={unpublishBilling.isPending}
            >
              <EyeOff size={14} />
              {unpublishBilling.isPending ? 'Despublicando...' : 'Despublicar'}
            </Button>
          ) : (
            <Button
              className="gap-2 text-white"
              style={{ backgroundColor: planillaStatus?.status === 'approved' ? '#16a34a' : '#9ca3af' }}
              onClick={() => publishBilling.mutate({ month, year })}
              disabled={publishBilling.isPending || planillaStatus?.status !== 'approved'}
              title={planillaStatus?.status !== 'approved' ? 'La planilla debe estar aprobada antes de publicar' : undefined}
            >
              <Send size={14} />
              {publishBilling.isPending ? 'Publicando...' : 'Publicar para Docentes'}
            </Button>
          )}
        </div>

        {publication?.status === 'published' && (
          <div className="px-5 py-3 bg-green-50/50 text-sm text-green-700 flex items-center gap-2">
            <span>✅ Los docentes pueden ver sus montos a facturar para {MONTH_NAMES[month]} {year}.</span>
            {publication.total_teachers > 0 && (
              <span className="text-green-600">
                ({publication.total_teachers} docentes · Bs {publication.total_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })})
              </span>
            )}
          </div>
        )}

        {!planillaStatus && publication?.status !== 'published' && (
          <div className="px-5 py-3 bg-yellow-50/50 text-sm text-yellow-700">
            Generá y aprobá la planilla antes de publicar.
          </div>
        )}

        {planillaStatus && planillaStatus.status !== 'approved' && publication?.status !== 'published' && (
          <div className="px-5 py-3 bg-yellow-50/50 text-sm text-yellow-700">
            {planillaStatus.status === 'rejected'
              ? 'La planilla fue rechazada. Regenerá con los ajustes necesarios.'
              : 'Aprobá la planilla antes de publicar para docentes.'}
          </div>
        )}
      </div>

      {/* Planilla Detail Section — ALWAYS visible */}
      <div className="card-3d-static overflow-hidden">
        {/* Header */}
        <div className="px-5 py-4 flex items-center gap-3 border-b border-gray-100">
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

        {/* Detail content */}
        <div className="p-5">
          {detailLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 size={24} className="animate-spin text-[#003366]" />
            </div>
          ) : detail ? (
            <div className="space-y-4">
              {/* Summary stats */}
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-blue-50/50 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold" style={{ color: '#003366' }}>{detail.total_teachers}</p>
                  <p className="text-xs text-gray-500">Docentes</p>
                </div>
                <div className="bg-blue-50/50 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold" style={{ color: '#003366' }}>{detail.total_designations}</p>
                  <p className="text-xs text-gray-500">Designaciones</p>
                </div>
                <div className="bg-blue-50/50 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold" style={{ color: '#003366' }}>Bs {detail.total_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })}</p>
                  <p className="text-xs text-gray-500">Total a Pagar</p>
                </div>
              </div>

              {/* Tabs + Search row */}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
                  <button
                    onClick={() => setDetailTab('teachers')}
                    className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                      detailTab === 'teachers' ? 'bg-white shadow-sm text-gray-800' : 'text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    Por Docente
                  </button>
                  <button
                    onClick={() => setDetailTab('designations')}
                    className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                      detailTab === 'designations' ? 'bg-white shadow-sm text-gray-800' : 'text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    Por Designación
                  </button>
                </div>

                {/* Search */}
                <div className="relative flex-1 min-w-[200px] max-w-sm">
                  <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="Buscar docente por nombre o CI..."
                    className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] focus:border-transparent bg-gray-50/50"
                  />
                </div>
              </div>

              {/* Tab: Por Docente */}
              {detailTab === 'teachers' && (
                <div className="space-y-3">
                  {detail.teacher_totals
                    .filter(t => {
                      if (!searchTerm) return true
                      const term = searchTerm.toLowerCase()
                      return t.teacher_name.toLowerCase().includes(term) || t.teacher_ci.includes(term)
                    })
                    .sort((a, b) => b.total_payment - a.total_payment)
                    .map(teacher => (
                      <div key={teacher.teacher_ci} className="border border-gray-200 rounded-lg overflow-hidden">
                        {/* Teacher header */}
                        <div className="flex items-center justify-between px-4 py-3 bg-gray-50/50">
                          <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-full gradient-stat-navy flex items-center justify-center">
                              <span className="text-white text-sm font-bold">{teacher.teacher_name.charAt(0)}</span>
                            </div>
                            <div>
                              <p className="font-medium text-gray-800 text-sm">{teacher.teacher_name}</p>
                              <p className="text-xs text-gray-500">CI: {teacher.teacher_ci} · {teacher.designation_count} materia(s)</p>
                            </div>
                          </div>
                          <div className="text-right">
                            {editingOverride === teacher.teacher_ci ? (
                              <div className="flex items-center gap-2 justify-end">
                                <span className="text-xs text-gray-500">Bs</span>
                                <input
                                  type="number"
                                  value={overrideValue}
                                  onChange={e => setOverrideValue(e.target.value)}
                                  className="w-24 border border-[#0066CC] rounded px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-[#0066CC]"
                                  // eslint-disable-next-line jsx-a11y/no-autofocus
                                  autoFocus
                                />
                                <button
                                  onClick={() => {
                                    if (overrideValue) {
                                      setPaymentOverrides(prev => ({ ...prev, [teacher.teacher_ci]: Number(overrideValue) }))
                                    }
                                    setEditingOverride(null)
                                    setOverrideValue('')
                                  }}
                                  className="text-green-600 hover:text-green-800"
                                  title="Confirmar ajuste"
                                >
                                  <Check size={14} />
                                </button>
                                <button
                                  onClick={() => { setEditingOverride(null); setOverrideValue('') }}
                                  className="text-gray-400 hover:text-gray-600"
                                  title="Cancelar"
                                >
                                  <X size={14} />
                                </button>
                              </div>
                            ) : (
                              <div className="flex flex-col items-end gap-0.5">
                                {teacher.has_retention ? (
                                  <>
                                    <p className="text-xs text-gray-400 line-through">
                                      Bruto: Bs {teacher.total_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                                    </p>
                                    <p className="text-xs text-red-500">
                                      Retención 13%: -Bs {(teacher.retention_amount ?? 0).toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                                    </p>
                                    <div className="flex items-center gap-2">
                                      <p
                                        className={`text-lg font-bold ${paymentOverrides[teacher.teacher_ci] != null ? 'line-through text-red-700' : ''}`}
                                        style={{ color: paymentOverrides[teacher.teacher_ci] != null ? undefined : '#003366' }}
                                      >
                                        Neto: Bs {(teacher.final_payment ?? teacher.total_payment).toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                                      </p>
                                      {paymentOverrides[teacher.teacher_ci] != null && (
                                        <p className="text-lg font-bold text-green-700">
                                          Bs {paymentOverrides[teacher.teacher_ci].toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                                        </p>
                                      )}
                                      <button
                                        onClick={() => {
                                          setEditingOverride(teacher.teacher_ci)
                                          setOverrideValue(String(paymentOverrides[teacher.teacher_ci] ?? (teacher.final_payment ?? teacher.total_payment)))
                                        }}
                                        className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-[#0066CC] transition-colors"
                                        title="Ajustar monto"
                                      >
                                        <Pencil size={13} />
                                      </button>
                                    </div>
                                  </>
                                ) : (
                                  <div className="flex items-center gap-2 justify-end">
                                    <p
                                      className={`text-lg font-bold ${paymentOverrides[teacher.teacher_ci] != null ? 'line-through text-red-700' : ''}`}
                                      style={{ color: paymentOverrides[teacher.teacher_ci] != null ? undefined : '#003366' }}
                                    >
                                      Bs {teacher.total_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                                    </p>
                                    {paymentOverrides[teacher.teacher_ci] != null && (
                                      <p className="text-lg font-bold text-green-700">
                                        Bs {paymentOverrides[teacher.teacher_ci].toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                                      </p>
                                    )}
                                    <button
                                      onClick={() => {
                                        setEditingOverride(teacher.teacher_ci)
                                        setOverrideValue(String(paymentOverrides[teacher.teacher_ci] ?? teacher.total_payment))
                                      }}
                                      className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-[#0066CC] transition-colors"
                                      title="Ajustar monto"
                                    >
                                      <Pencil size={13} />
                                    </button>
                                  </div>
                                )}

                                {paymentOverrides[teacher.teacher_ci] != null && (
                                  <button
                                    onClick={() => {
                                      setPaymentOverrides(prev => {
                                        const next = { ...prev }
                                        delete next[teacher.teacher_ci]
                                        return next
                                      })
                                    }}
                                    className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-red-500 transition-colors"
                                    title="Quitar ajuste"
                                  >
                                    <X size={13} />
                                  </button>
                                )}
                              </div>
                            )}
                            <p className="text-xs text-gray-500 mt-1">
                              {teacher.total_payable_hours}h de {teacher.total_base_hours}h
                              {!teacher.has_biometric && (
                                <span className="ml-1 text-yellow-600 font-medium">· Sin Bio</span>
                              )}
                            </p>
                          </div>
                        </div>
                        {/* Teacher designations */}
                        <div className="divide-y divide-gray-100">
                          {detail.detail
                            .filter(d => d.teacher_ci === teacher.teacher_ci)
                            .map(d => (
                              <div key={`${d.subject}-${d.group_code}`} className="flex items-center justify-between px-4 py-2 text-sm">
                                <div className="flex items-center gap-2">
                                  <span className="text-gray-700">{d.subject}</span>
                                  <Badge className="bg-gray-100 text-gray-600 text-xs">{d.group_code}</Badge>
                                  <span className="text-gray-400 text-xs">{d.semester}</span>
                                </div>
                                <div className="flex items-center gap-4 text-xs">
                                  <span className="text-gray-500">{d.base_monthly_hours}h base</span>
                                  {d.absent_hours > 0 && <span className="text-red-500">-{d.absent_hours}h</span>}
                                  <span className="font-semibold text-gray-800">{d.payable_hours}h</span>
                                  <span className="font-bold min-w-[80px] text-right" style={{ color: '#003366' }}>
                                    Bs {d.calculated_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                                  </span>
                                </div>
                              </div>
                            ))
                          }
                        </div>
                      </div>
                    ))
                  }
                </div>
              )}

              {/* Tab: Por Designación */}
              {detailTab === 'designations' && (
                <div className="overflow-x-auto rounded-lg border border-gray-200">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)' }}>
                        {['Docente', 'Materia', 'Grupo', 'Sem.', 'Hrs Base', 'Ausencias', 'Hrs a Pagar', 'Monto (Bs)', 'Estado'].map(h => (
                          <th key={h} className="text-left text-white font-semibold text-xs uppercase tracking-wider px-3 py-2.5">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {detail.detail
                        .filter(row => {
                          if (!searchTerm) return true
                          const term = searchTerm.toLowerCase()
                          return row.teacher_name.toLowerCase().includes(term) || row.teacher_ci.includes(term)
                        })
                        .map((row, i) => (
                          <tr key={`${row.teacher_ci}-${row.subject}-${row.group_code}`} className={`border-b last:border-0 hover:bg-blue-50/70 transition-colors ${i % 2 === 1 ? 'bg-gray-50' : 'bg-white'}`}>
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
                            <td className="px-3 py-2.5 font-bold" style={{ color: '#003366' }}>{row.calculated_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })}</td>
                            <td className="px-3 py-2.5">
                              {!row.has_biometric ? (
                                <Badge className="bg-yellow-100 text-yellow-700 text-xs">Sin Bio</Badge>
                              ) : row.absent_count > 0 ? (
                                <Badge className="bg-red-100 text-red-700 text-xs">{row.absent_count} falta(s)</Badge>
                              ) : (
                                <Badge className="bg-green-100 text-green-700 text-xs">Completo</Badge>
                              )}
                            </td>
                          </tr>
                        ))
                      }
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-10 text-gray-400 text-sm">
              No hay datos para {MONTH_NAMES[month]} {year}. Generá la planilla para ver el detalle.
            </div>
          )}
        </div>
      </div>

      {/* History */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-3">
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
        <div className="p-0">
          {historyLoading ? (
            <div className="p-5">
              <LoadingPage />
            </div>
          ) : !history || history.length === 0 ? (
            <div className="text-center py-10 text-gray-400 text-sm">
              No hay planillas generadas aún
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)' }}>
                    {['Período', 'Corte', 'Generada el', 'Docentes', 'Horas', 'Total (Bs)', 'Estado', 'Descarga'].map(h => (
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
                        <Badge
                          className={
                            item.status?.toLowerCase() === 'approved'
                              ? 'bg-green-100 text-green-700 text-xs'
                              : item.status?.toLowerCase() === 'rejected'
                                ? 'bg-red-100 text-red-700 text-xs'
                                : 'bg-yellow-100 text-yellow-700 text-xs'
                          }
                        >
                          {item.status?.toLowerCase() === 'approved'
                            ? 'Aprobada'
                            : item.status?.toLowerCase() === 'rejected'
                              ? 'Rechazada'
                              : 'Pend. Aprobación'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        {item.file_path ? (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              void downloadPlanilla(item.id, `planilla_${MONTH_NAMES[item.month]}_${item.year}.xlsx`)
                            }}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded text-[#0066CC] hover:bg-blue-50 border border-[#0066CC]/30 text-xs font-medium transition-colors"
                          >
                            <Download size={12} />
                            Excel
                          </button>
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
      </div>
    </div>
  )
}
