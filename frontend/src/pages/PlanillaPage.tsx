import { useState, useEffect, useRef } from 'react'
import { FileSpreadsheet, Download, Loader2, CheckCircle, XCircle, Clock, Users, Search, Send, EyeOff, Pencil, Check, X, History, Calendar, Info, AlertTriangle, Plus, Trash2, CalendarOff, Mail } from 'lucide-react'
import { useGeneratePlanilla, usePlanillaHistory, downloadPlanilla, downloadSalaryReport, usePlanillaDetail, useApprovePlanilla, useRejectPlanilla, usePlanillaStatus } from '@/api/hooks/usePlanilla'
import { usePublicationStatus, usePublishBilling, useUnpublishBilling, useSendBillingEmails } from '@/api/hooks/useBillingPublication'
import { useBiometricDateRange } from '@/api/hooks/useBiometric'
import { LoadingPage } from '@/components/shared/LoadingSpinner'
import { api } from '@/api/client'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { DesignationOption, DesignationOptions, ExcludedDay, PlanillaGenerateResponse } from '@/api/types'

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

type ExclusionRow = ExcludedDay & {
  selectedSemesters?: string[]
  selectedSubjects?: string[]
  subjectSelections?: DesignationOption[]
}

function getSubjectOptionKey(option: DesignationOption): string {
  return `${option.subject}||${option.group_code}||${option.semester}`
}

function getSubjectGroupKey(option: DesignationOption): string {
  return `${option.subject}||${option.group_code}`
}

function getUniqueSubjects(options: DesignationOption[]): string[] {
  return Array.from(new Set(options.map(option => option.subject))).sort((a, b) => a.localeCompare(b))
}

function getGroupsForSubject(options: DesignationOption[], subject: string): DesignationOption[] {
  const seen = new Set<string>()
  return options.filter((option) => {
    if (option.subject !== subject) return false
    const key = getSubjectGroupKey(option)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function expandExcludedDays(rows: ExclusionRow[]): ExcludedDay[] {
  return rows.flatMap<ExcludedDay>((row) => {
    if (row.scope === 'subject') {
      const selections = row.subjectSelections ?? []
      return selections.map((selection) => ({
        date: row.date,
        scope: 'subject' as const,
        subject_id: selection.subject,
        group_id: selection.group_code,
        reason: row.reason,
      }))
    }

    if (row.scope === 'semester') {
      const semesters = row.selectedSemesters ?? (row.semester_id ? [row.semester_id] : [])
      return semesters.map((semester) => ({
        date: row.date,
        scope: 'semester' as const,
        semester_id: semester,
        reason: row.reason,
      }))
    }

    return [{ date: row.date, scope: 'global', reason: row.reason }]
  })
}

function hydrateExclusionRows(excludedDays: ExcludedDay[]): ExclusionRow[] {
  const rows = new Map<string, ExclusionRow>()

  for (const excluded of excludedDays) {
    // Group by date + scope + reason to preserve distinct reasons on the same day
    const key = `${excluded.date}||${excluded.scope}||${excluded.reason ?? ''}`
    const current = rows.get(key)

    if (excluded.scope === 'global') {
      if (!current) {
        rows.set(key, { date: excluded.date, scope: 'global', reason: excluded.reason })
      }
      continue
    }

    if (excluded.scope === 'semester') {
      const selectedSemesters = current?.selectedSemesters ?? []
      rows.set(key, {
        date: excluded.date,
        scope: 'semester',
        reason: excluded.reason,
        selectedSemesters: excluded.semester_id && !selectedSemesters.includes(excluded.semester_id)
          ? [...selectedSemesters, excluded.semester_id]
          : selectedSemesters,
      })
      continue
    }

    const subjectSelections = current?.subjectSelections ?? []
    const selectedSubjects = current?.selectedSubjects ?? []
    const subject = excluded.subject_id
    const group = excluded.group_id
    const hasSelection = subjectSelections.some(selection => selection.subject === subject && selection.group_code === group)

    rows.set(key, {
      date: excluded.date,
      scope: 'subject',
      reason: excluded.reason,
      selectedSubjects: subject && !selectedSubjects.includes(subject)
        ? [...selectedSubjects, subject]
        : selectedSubjects,
      subjectSelections: subject && group && !hasSelection
        ? [...subjectSelections, { subject, group_code: group, semester: '' }]
        : subjectSelections,
    })
  }

  return Array.from(rows.values())
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
  const [datesManuallySet, setDatesManuallySet] = useState(false)
  const [showDetail] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [detailTab, setDetailTab] = useState<'designations' | 'teachers'>('teachers')
  const [selectedTeachers, setSelectedTeachers] = useState<Set<string>>(() => new Set())
  const [discountMode, setDiscountMode] = useState<'attendance' | 'full'>('attendance')
  const [discountModeManuallySet, setDiscountModeManuallySet] = useState(false)

  // Payment override state
  const [paymentOverrides, setPaymentOverrides] = useState<Record<string, number>>({})
  const [editingOverride, setEditingOverride] = useState<string | null>(null)
  const [overrideValue, setOverrideValue] = useState('')

  // Exclusion days state
  const [excludedDays, setExcludedDays] = useState<ExclusionRow[]>([])
  const [exclusionsEdited, setExclusionsEdited] = useState(false)
  const [newExclusion, setNewExclusion] = useState<ExclusionRow>(() => ({ date: new Date().toISOString().slice(0, 10), scope: 'global' }))
  const [exclusionPanelOpen, setExclusionPanelOpen] = useState(false)
  const [designationOptions, setDesignationOptions] = useState<DesignationOptions>({ subjects: [], semesters: [], groups: [] })
  const [designationOptionsLoading, setDesignationOptionsLoading] = useState(false)
  const restoringHistoryRef = useRef(false)

  // Salary report download loading state (keyed by planilla id for history rows,
  // "current" for the main action bar). Using a map lets multiple rows spin
  // independently without one blocking the others.
  const [salaryReportLoading, setSalaryReportLoading] = useState<Record<string, boolean>>({})

  const { data: bioRange } = useBiometricDateRange(month, year)
  const { data: planillaStatus } = usePlanillaStatus(month, year)

  // Reset manual flags when month/year changes so auto-fill can run again
  useEffect(() => {
    if (restoringHistoryRef.current) {
      restoringHistoryRef.current = false
      return
    }

    setDatesManuallySet(false)
    setDiscountModeManuallySet(false)
    setExclusionsEdited(false)
    setExcludedDays([])
  }, [month, year])

  // Auto-fill dates: prefer stored planilla dates, then biometric, then fallback
  useEffect(() => {
    if (datesManuallySet) return

    // If there's a stored planilla with dates, use those (ensures consistency)
    if (planillaStatus?.start_date && planillaStatus?.end_date) {
      setStartDate(planillaStatus.start_date)
      setEndDate(planillaStatus.end_date)
      return
    }

    // Otherwise use biometric suggestion
    if (bioRange?.has_data && bioRange.suggested_start && bioRange.suggested_end) {
      setStartDate(bioRange.suggested_start)
      setEndDate(bioRange.suggested_end)
    } else if (bioRange !== undefined && !bioRange.has_data) {
      // No biometric data: fall back to standard cut-off period
      const prevMonth = month === 1 ? 12 : month - 1
      const prevYear = month === 1 ? year - 1 : year
      setStartDate(`${prevYear}-${String(prevMonth).padStart(2, '0')}-21`)
      setEndDate(`${year}-${String(month).padStart(2, '0')}-20`)
    }
  }, [bioRange, datesManuallySet, month, year, planillaStatus])

  useEffect(() => {
    if (!exclusionPanelOpen) return

    setDesignationOptionsLoading(true)
    api.get<DesignationOptions>('/planilla/designation-options')
      .then(res => setDesignationOptions(res.data))
      .catch(() => setDesignationOptions({ subjects: [], semesters: [], groups: [] }))
      .finally(() => setDesignationOptionsLoading(false))
  }, [exclusionPanelOpen])

  const generatePlanilla = useGeneratePlanilla()
  const { data: history, isLoading: historyLoading } = usePlanillaHistory()
  const { data: publication } = usePublicationStatus(month, year)

  useEffect(() => {
    if (exclusionsEdited) return
    setExcludedDays(hydrateExclusionRows(planillaStatus?.excluded_days_json ?? []))
    setExclusionsEdited(false)
  }, [planillaStatus?.excluded_days_json, exclusionsEdited, month, year])

  // Derive the effective discount mode: if the user manually toggled, use their
  // choice. Otherwise fall back to the stored planilla's mode (if one exists),
  // then to the local state default ("attendance"). This is a single source of
  // truth — no sync effect, no race condition, no clobbering on refetch.
  const effectiveDiscountMode: 'attendance' | 'full' = discountModeManuallySet
    ? discountMode
    : (planillaStatus?.discount_mode === 'attendance' || planillaStatus?.discount_mode === 'full')
      ? planillaStatus.discount_mode
      : discountMode

  const expandedExcludedDays = expandExcludedDays(excludedDays)
  // Pass exclusions to detail preview only when the user has actively edited them.
  // undefined = inherit stored exclusions; [] = explicit clear (no exclusions).
  const previewExclusions = exclusionsEdited ? expandedExcludedDays : undefined
  const { data: detail, isLoading: detailLoading } = usePlanillaDetail(month, year, showDetail, startDate || undefined, endDate || undefined, effectiveDiscountMode, previewExclusions)
  const publishBilling = usePublishBilling()
  const unpublishBilling = useUnpublishBilling()
  const sendBillingEmails = useSendBillingEmails()
  const approvePlanilla = useApprovePlanilla()
  const rejectPlanilla = useRejectPlanilla()

  const isBillingPublished = publication?.status === 'published'
  const visibleTeacherTotals = detail?.teacher_totals
    .filter(t => {
      if (!searchTerm) return true
      const term = searchTerm.toLowerCase()
      return t.teacher_name.toLowerCase().includes(term) || t.teacher_ci.includes(term)
    })
    .sort((a, b) => b.total_payment - a.total_payment) ?? []
  const allVisibleTeachersSelected = visibleTeacherTotals.length > 0 && visibleTeacherTotals.every(t => selectedTeachers.has(t.teacher_ci))

  useEffect(() => {
    if (!isBillingPublished) {
      setSelectedTeachers(new Set())
    }
  }, [isBillingPublished, month, year])

  const toggleTeacherSelection = (teacherCi: string) => {
    setSelectedTeachers(prev => {
      const next = new Set(prev)
      if (next.has(teacherCi)) {
        next.delete(teacherCi)
      } else {
        next.add(teacherCi)
      }
      return next
    })
  }

  const toggleAllVisibleTeachers = () => {
    setSelectedTeachers(prev => {
      const next = new Set(prev)
      if (allVisibleTeachersSelected) {
        visibleTeacherTotals.forEach(t => next.delete(t.teacher_ci))
      } else {
        visibleTeacherTotals.forEach(t => next.add(t.teacher_ci))
      }
      return next
    })
  }

  const handleSendSelectedBillingEmails = () => {
    if (selectedTeachers.size === 0) return

    sendBillingEmails.mutate(
      { month, year, teacher_cis: Array.from(selectedTeachers) },
      {
        onSuccess: (result) => {
          alert(`Correos enviados: ${result.sent}. Fallidos: ${result.failed}. Omitidos: ${result.skipped}.`)
          setSelectedTeachers(new Set())
        },
        onError: () => {
          alert('No se pudieron enviar los correos seleccionados. Intentá nuevamente.')
        },
      },
    )
  }

  const handleGenerate = () => {
    // Validate exclusion rows before generating
    for (let i = 0; i < excludedDays.length; i++) {
      const row = excludedDays[i]
      if (row.scope === 'semester' && (!row.selectedSemesters || row.selectedSemesters.length === 0)) {
        alert(`Exclusión #${i + 1}: seleccioná al menos un semestre o cambiá el alcance.`)
        return
      }
      if (row.scope === 'subject' && (!row.subjectSelections || row.subjectSelections.length === 0)) {
        alert(`Exclusión #${i + 1}: seleccioná al menos una materia/grupo o cambiá el alcance.`)
        return
      }
    }

    setLastResult(null)

    generatePlanilla.mutate(
      {
        month,
        year,
        payment_overrides: paymentOverrides,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        discount_mode: effectiveDiscountMode,
        excluded_days: expandedExcludedDays.length > 0 ? expandedExcludedDays : undefined,
      },
      {
        onSuccess: (data) => setLastResult(data),
      },
    )
  }

  const resetNewExclusion = () => {
    const today = new Date().toISOString().slice(0, 10)
    setNewExclusion({ date: today, scope: 'global' })
  }

  const addExclusionRow = () => {
    if (!newExclusion.date) return
    if (newExclusion.scope === 'semester' && (!newExclusion.selectedSemesters || newExclusion.selectedSemesters.length === 0)) return
    if (newExclusion.scope === 'subject' && (!newExclusion.subjectSelections || newExclusion.subjectSelections.length === 0)) return

    setExcludedDays(prev => [...prev, newExclusion])
    setExclusionsEdited(true)
    resetNewExclusion()
  }

  const removeExclusionRow = (index: number) => {
    setExcludedDays(prev => prev.filter((_, i) => i !== index))
    setExclusionsEdited(true)
  }

  const updateNewExclusion = (patch: Partial<ExclusionRow>) => {
    setNewExclusion(prev => {
      const updated = { ...prev, ...patch }
      // Clear scope-specific fields when scope changes
      if (patch.scope === 'global') {
        return { date: updated.date, scope: 'global', reason: updated.reason }
      }
      if (patch.scope === 'semester') {
        return { date: updated.date, scope: 'semester', selectedSemesters: [], reason: updated.reason }
      }
      if (patch.scope === 'subject') {
        return { date: updated.date, scope: 'subject', selectedSubjects: [], subjectSelections: [], reason: updated.reason }
      }
      return updated
    })
  }

  const canAddExclusion = Boolean(newExclusion.date) && (
    newExclusion.scope === 'global' ||
    (newExclusion.scope === 'semester' && Boolean(newExclusion.selectedSemesters?.length)) ||
    (newExclusion.scope === 'subject' && Boolean(newExclusion.subjectSelections?.length))
  )

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

          {/* Discount Mode Switch */}
          <div className="mt-4 bg-gray-50/50 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-700">Modo de cálculo</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {effectiveDiscountMode === 'attendance'
                    ? 'Se aplican descuentos por ausencias registradas en el biométrico'
                    : 'Todos los docentes cobran el 100% de sus horas asignadas (sin descuentos)'}
                </p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={effectiveDiscountMode === 'full'}
                onClick={() => { setDiscountModeManuallySet(true); setDiscountMode(prev => prev === 'attendance' ? 'full' : 'attendance') }}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-[#0066CC] focus:ring-offset-2 ${
                  effectiveDiscountMode === 'full' ? 'bg-[#0066CC]' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    effectiveDiscountMode === 'full' ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
            <div className="mt-2 flex items-center gap-2">
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                effectiveDiscountMode === 'attendance'
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-green-100 text-green-700'
              }`}>
                {effectiveDiscountMode === 'attendance' ? 'Con descuentos' : 'Sin descuentos — pago completo'}
              </span>
            </div>
            {effectiveDiscountMode === 'full' && (
              <div className="flex items-start gap-2 p-3 bg-amber-50 rounded-lg border border-amber-200 mt-3">
                <AlertTriangle size={16} className="text-amber-500 mt-0.5 flex-shrink-0" />
                <p className="text-xs text-amber-700">
                  <strong>Atención:</strong> En este modo no se aplicarán descuentos por ausencias.
                  Todos los docentes recibirán el monto total correspondiente a sus horas asignadas.
                </p>
              </div>
            )}
          </div>

          {/* Exclusion Days Section */}
          <div className="mt-4 bg-gray-50/50 rounded-lg border border-gray-200 overflow-hidden">
            {/* Collapsible header */}
            <button
              type="button"
              onClick={() => setExclusionPanelOpen(prev => !prev)}
              className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-100/50 transition-colors"
            >
              <div className="flex items-center gap-2">
                <CalendarOff size={16} className="text-purple-600 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-gray-700">
                    Días excluidos del cálculo
                    {excludedDays.length > 0 && (
                      <span className="ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full bg-purple-100 text-purple-700 text-xs font-bold">
                        {excludedDays.length}
                      </span>
                    )}
                  </p>
                  <p className="text-xs text-gray-500">
                    {excludedDays.length === 0
                      ? 'Sin exclusiones — todos los días se calculan normalmente'
                      : `${excludedDays.length} día(s) excluido(s) de la planilla`}
                  </p>
                </div>
              </div>
              <span className="text-gray-400 text-xs font-medium">
                {exclusionPanelOpen ? '▲ Cerrar' : '▼ Abrir'}
              </span>
            </button>

            {exclusionPanelOpen && (
              <div className="px-4 pb-4 border-t border-gray-200">
                {/* Add exclusion form */}
                <form
                  onSubmit={(e) => { e.preventDefault(); addExclusionRow() }}
                  className="mt-3 rounded-lg border border-dashed border-purple-300 bg-white p-3"
                >
                  <div className="flex items-center justify-between gap-3 mb-3">
                    <div>
                      <p className="text-sm font-semibold text-gray-700">Agregar exclusión</p>
                      <p className="text-xs text-gray-500">Completá los datos y confirmá para enviarla a la lista.</p>
                    </div>
                    <button
                      type="submit"
                      disabled={!canAddExclusion}
                      className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-purple-600 text-white hover:bg-purple-700 disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed text-sm font-medium transition-colors"
                    >
                      <Plus size={14} />
                      Agregar
                    </button>
                  </div>

                  <div className="flex flex-wrap items-start gap-3">
                    <div className="flex flex-col gap-0.5">
                      <label className="text-xs text-gray-500 font-medium">Fecha <span className="text-red-400">*</span></label>
                      <input
                        type="date"
                        value={newExclusion.date}
                        onChange={e => updateNewExclusion({ date: e.target.value })}
                        className="border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-400"
                        required
                      />
                    </div>

                    <div className="flex flex-col gap-0.5">
                      <label className="text-xs text-gray-500 font-medium">Alcance</label>
                      <select
                        value={newExclusion.scope}
                        onChange={e => updateNewExclusion({ scope: e.target.value as ExcludedDay['scope'] })}
                        className="border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-400 min-w-[130px]"
                      >
                        <option value="global">Global</option>
                        <option value="semester">Por semestre</option>
                        <option value="subject">Por materia</option>
                      </select>
                    </div>

                    {newExclusion.scope === 'semester' && (
                      <div className="flex flex-col gap-2 min-w-[220px] max-w-sm flex-1">
                        <label className="text-xs text-gray-500 font-medium">Semestres <span className="text-red-400">*</span></label>
                        <div className="max-h-44 overflow-y-auto rounded border border-purple-100 bg-purple-50/40 p-2 space-y-1">
                          {designationOptionsLoading ? (
                            <p className="text-xs text-purple-500 px-1 py-1">Cargando opciones...</p>
                          ) : designationOptions.semesters.length === 0 ? (
                            <p className="text-xs text-gray-400 px-1 py-1">No hay semestres cargados para el período activo.</p>
                          ) : (
                            designationOptions.semesters.map((semester) => {
                              const selectedSemesters = newExclusion.selectedSemesters ?? []
                              const checked = selectedSemesters.includes(semester)

                              return (
                                <label key={semester} className="flex items-center gap-2 rounded bg-white/60 px-2 py-1.5 text-sm text-gray-700 hover:bg-purple-50 cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={(e) => {
                                      updateNewExclusion({
                                        selectedSemesters: e.target.checked
                                          ? [...selectedSemesters, semester]
                                          : selectedSemesters.filter(selected => selected !== semester),
                                      })
                                    }}
                                    className="rounded border-gray-300 text-purple-600 focus:ring-purple-400"
                                  />
                                  <span>{semester}</span>
                                </label>
                              )
                            })
                          )}
                        </div>
                      </div>
                    )}

                    {newExclusion.scope === 'subject' && (
                      <div className="flex flex-col gap-2 min-w-[260px] max-w-xl flex-1">
                        <label className="text-xs text-gray-500 font-medium">Materias y grupos <span className="text-red-400">*</span></label>
                        <div className="max-h-44 overflow-y-auto rounded border border-purple-100 bg-purple-50/40 p-2 space-y-2">
                          {designationOptionsLoading ? (
                            <p className="text-xs text-purple-500 px-1 py-1">Cargando opciones...</p>
                          ) : designationOptions.subjects.length === 0 ? (
                            <p className="text-xs text-gray-400 px-1 py-1">No hay materias cargadas para el período activo.</p>
                          ) : (
                            getUniqueSubjects(designationOptions.subjects).map((subject) => {
                              const selectedSubjects = newExclusion.selectedSubjects ?? []
                              const subjectChecked = selectedSubjects.includes(subject)
                              const groups = getGroupsForSubject(designationOptions.subjects, subject)

                              return (
                                <div key={subject} className="rounded-md bg-white/60 px-2 py-1.5">
                                  <label className="flex items-center gap-2 text-sm font-medium text-gray-700 cursor-pointer">
                                    <input
                                      type="checkbox"
                                      checked={subjectChecked}
                                      onChange={(e) => {
                                        const currentSelections = newExclusion.subjectSelections ?? []
                                        updateNewExclusion({
                                          selectedSubjects: e.target.checked
                                            ? [...selectedSubjects, subject]
                                            : selectedSubjects.filter(selected => selected !== subject),
                                          subjectSelections: e.target.checked
                                            ? currentSelections
                                            : currentSelections.filter(selection => selection.subject !== subject),
                                        })
                                      }}
                                      className="rounded border-gray-300 text-purple-600 focus:ring-purple-400"
                                    />
                                    <span>{subject}</span>
                                  </label>

                                  {subjectChecked && (
                                    <div className="ml-6 mt-1.5 grid grid-cols-2 gap-1">
                                      {groups.map((option) => {
                                        const optionKey = getSubjectOptionKey(option)
                                        const checked = (newExclusion.subjectSelections ?? []).some(selection => getSubjectOptionKey(selection) === optionKey)

                                        return (
                                          <label key={optionKey} className="flex items-center gap-1.5 rounded px-1.5 py-0.5 text-xs text-gray-600 hover:bg-purple-50 cursor-pointer">
                                            <input
                                              type="checkbox"
                                              checked={checked}
                                              onChange={(e) => {
                                                const current = newExclusion.subjectSelections ?? []
                                                updateNewExclusion({
                                                  subjectSelections: e.target.checked
                                                    ? [...current, option]
                                                    : current.filter(selection => getSubjectOptionKey(selection) !== optionKey),
                                                })
                                              }}
                                              className="rounded border-gray-300 text-purple-600 focus:ring-purple-400"
                                            />
                                            <span>{option.group_code}</span>
                                          </label>
                                        )
                                      })}
                                    </div>
                                  )}
                                </div>
                              )
                            })
                          )}
                        </div>
                      </div>
                    )}

                    <div className="flex flex-col gap-0.5 flex-1 min-w-[180px]">
                      <label className="text-xs text-gray-500 font-medium">Motivo <span className="text-gray-300">(opcional)</span></label>
                      <input
                        type="text"
                        value={newExclusion.reason ?? ''}
                        onChange={e => updateNewExclusion({ reason: e.target.value || undefined })}
                        placeholder="ej: Feriado institucional"
                        className="border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-400"
                      />
                    </div>
                  </div>
                </form>

                {/* Confirmed exclusion list */}
                <div className="mt-4">
                  <div className="flex items-center justify-between gap-3 mb-2">
                    <p className="text-sm font-semibold text-gray-700">Exclusiones configuradas</p>
                    <span className="text-xs text-gray-400">{excludedDays.length} confirmada(s)</span>
                  </div>

                  {excludedDays.length === 0 ? (
                    <p className="text-xs text-gray-400 py-4 text-center bg-white rounded-lg border border-gray-200">
                      No hay exclusiones configuradas
                    </p>
                  ) : (
                    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
                      {excludedDays.map((row, index) => (
                        <div key={index} className={`grid grid-cols-1 md:grid-cols-[110px_120px_1fr_1fr_36px] gap-3 px-3 py-3 text-sm ${index % 2 === 0 ? 'bg-white' : 'bg-gray-50/60'} border-b border-gray-100 last:border-b-0`}>
                          <div>
                            <p className="text-xs text-gray-400 font-medium">Fecha</p>
                            <p className="text-gray-700 font-medium">{formatDate(row.date)}</p>
                          </div>
                          <div>
                            <p className="text-xs text-gray-400 font-medium">Alcance</p>
                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
                              row.scope === 'global'
                                ? 'bg-purple-100 text-purple-700'
                                : row.scope === 'semester'
                                  ? 'bg-blue-100 text-blue-700'
                                  : 'bg-amber-100 text-amber-700'
                            }`}>
                              {row.scope === 'global' ? 'Global' : row.scope === 'semester' ? 'Semestre' : 'Materia'}
                            </span>
                          </div>
                          <div>
                            <p className="text-xs text-gray-400 font-medium">Detalle</p>
                            {row.scope === 'global' && <p className="text-gray-500">Todos los docentes</p>}
                            {row.scope === 'semester' && (
                              <div className="flex flex-wrap gap-1">
                                {(row.selectedSemesters ?? (row.semester_id ? [row.semester_id] : [])).map((semester) => (
                                  <span key={semester} className="inline-flex rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 border border-blue-100">
                                    {semester}
                                  </span>
                                ))}
                              </div>
                            )}
                            {row.scope === 'subject' && (
                              <div className="flex flex-wrap gap-1">
                                {(row.subjectSelections ?? []).map((selection) => (
                                  <span key={getSubjectOptionKey(selection)} className="inline-flex rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 border border-amber-100">
                                    {selection.subject} ({selection.group_code})
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                          <div>
                            <p className="text-xs text-gray-400 font-medium">Motivo</p>
                            <p className="text-gray-600">{row.reason || 'Sin motivo'}</p>
                          </div>
                          <div className="flex items-start md:justify-end">
                            <button
                              type="button"
                              onClick={() => removeExclusionRow(index)}
                              className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
                              title="Quitar exclusión"
                              aria-label="Quitar exclusión"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex items-start gap-2 p-2.5 bg-purple-50 rounded-lg border border-purple-200 mt-3">
                  <Info size={14} className="text-purple-500 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-purple-700">
                    <strong>Global</strong>: excluye el día para todos los docentes. <strong>Por semestre</strong>: solo el semestre indicado. <strong>Por materia</strong>: solo la materia y grupo exactos. Las celdas excluidas aparecen en rojo en el Excel.
                  </p>
                </div>
              </div>
            )}
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
                    Total: Bs {parseFloat(lastResult.total_payment).toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                  {lastResult.warnings.length > 0 && (
                    <p className="text-xs text-yellow-600 mt-1">
                      {lastResult.warnings.length} advertencia(s) durante la generación
                    </p>
                  )}
                </div>
              </div>
              {lastResult.file_path && (
                <div className="flex items-center gap-2 flex-wrap">
                  <Button
                    variant="outline"
                    className="border-[#0066CC] text-[#0066CC] hover:bg-blue-50 gap-2"
                    onClick={() => void downloadPlanilla(lastResult.planilla_id, `planilla_${MONTH_NAMES[lastResult.month]}_${lastResult.year}.xlsx`)}
                  >
                    <Download size={16} />
                    Descargar Excel
                  </Button>
                  <button
                    onClick={async () => {
                      setSalaryReportLoading((prev) => ({ ...prev, current: true }))
                      try {
                        await downloadSalaryReport({
                          month: lastResult.month,
                          year: lastResult.year,
                          discount_mode: effectiveDiscountMode,
                          start_date: startDate || undefined,
                          end_date: endDate || undefined,
                        })
                      } finally {
                        setSalaryReportLoading((prev) => ({ ...prev, current: false }))
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
              style={{ backgroundColor: planillaStatus?.status === 'approved' && !exclusionsEdited ? '#16a34a' : '#9ca3af' }}
              onClick={() => publishBilling.mutate({ month, year })}
              disabled={publishBilling.isPending || planillaStatus?.status !== 'approved' || exclusionsEdited}
              title={exclusionsEdited ? 'Regenerá la planilla para aplicar los cambios de exclusiones antes de publicar' : planillaStatus?.status !== 'approved' ? 'La planilla debe estar aprobada antes de publicar' : undefined}
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

        {exclusionsEdited && publication?.status !== 'published' && (
          <div className="px-5 py-3 bg-amber-50/50 text-sm text-amber-700">
            Regenerá la planilla para aplicar los cambios de exclusiones antes de publicar.
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
                  {isBillingPublished && (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#0066CC]/20 bg-blue-50/50 px-4 py-3">
                      <label className="flex items-center gap-2 text-sm font-medium text-gray-700 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={allVisibleTeachersSelected}
                          onChange={toggleAllVisibleTeachers}
                          disabled={visibleTeacherTotals.length === 0}
                          className="h-4 w-4 rounded border-gray-300 text-[#0066CC] focus:ring-[#0066CC]"
                        />
                        Seleccionar todos
                      </label>
                      <Badge className="bg-[#003366] text-white">
                        {selectedTeachers.size} seleccionado(s)
                      </Badge>
                    </div>
                  )}

                  {visibleTeacherTotals.map(teacher => (
                      <div key={teacher.teacher_ci} className="border border-gray-200 rounded-lg overflow-hidden">
                        {/* Teacher header */}
                        <div className="flex items-center justify-between px-4 py-3 bg-gray-50/50">
                          <div className="flex items-center gap-3">
                            {isBillingPublished && (
                              <input
                                type="checkbox"
                                checked={selectedTeachers.has(teacher.teacher_ci)}
                                onChange={() => toggleTeacherSelection(teacher.teacher_ci)}
                                aria-label={`Seleccionar ${teacher.teacher_name}`}
                                className="h-4 w-4 rounded border-gray-300 text-[#0066CC] focus:ring-[#0066CC]"
                              />
                            )}
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
                                    Bs {(d.final_payment ?? d.calculated_payment).toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                                    {(d.retention_amount ?? 0) > 0 && <span className="ml-1 text-xs text-red-500 font-medium">(con retención)</span>}
                                  </span>
                                </div>
                              </div>
                            ))
                          }
                        </div>
                      </div>
                    ))}

                  {isBillingPublished && selectedTeachers.size > 0 && (
                    <div className="sticky bottom-4 z-10 rounded-xl border border-[#0066CC]/30 bg-[#003366] px-4 py-3 text-white shadow-lg">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <p className="text-sm font-semibold">
                          {selectedTeachers.size} docente(s) seleccionado(s)
                        </p>
                        <div className="flex flex-wrap items-center gap-2">
                          <Button
                            type="button"
                            onClick={handleSendSelectedBillingEmails}
                            disabled={sendBillingEmails.isPending}
                            className="gap-2 bg-white text-[#003366] hover:bg-blue-50"
                          >
                            {sendBillingEmails.isPending ? (
                              <Loader2 size={16} className="animate-spin" />
                            ) : (
                              <Mail size={16} />
                            )}
                            Enviar correo
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => setSelectedTeachers(new Set())}
                            disabled={sendBillingEmails.isPending}
                            className="border-white/40 text-white hover:bg-white/10 hover:text-white"
                          >
                            Limpiar selección
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}
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
                            <td className="px-3 py-2.5 font-bold" style={{ color: '#003366' }}>
                              {(row.final_payment ?? row.calculated_payment).toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                              {(row.retention_amount ?? 0) > 0 && <span className="ml-1 text-xs text-red-500 font-medium">(con retención)</span>}
                            </td>
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
                        restoringHistoryRef.current = item.month !== month || item.year !== year
                        setMonth(item.month)
                        setYear(item.year)
                        setStartDate(item.start_date ?? '')
                        setEndDate(item.end_date ?? '')
                        setDatesManuallySet(true)
                        setDiscountMode(item.discount_mode)
                        setDiscountModeManuallySet(true)
                        setExclusionsEdited(false)
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
                          <div className="flex items-center gap-1 flex-wrap">
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
                            <button
                              onClick={async (e) => {
                                e.stopPropagation()
                                const key = `row-${item.id}`
                                setSalaryReportLoading((prev) => ({ ...prev, [key]: true }))
                                try {
                                  await downloadSalaryReport({
                                    month: item.month,
                                    year: item.year,
                                    discount_mode: item.discount_mode,
                                  })
                                } finally {
                                  setSalaryReportLoading((prev) => ({ ...prev, [key]: false }))
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
      </div>
    </div>
  )
}
