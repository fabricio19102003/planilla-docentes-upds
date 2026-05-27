import { useState, useEffect, useRef } from 'react'
import {
  FileSpreadsheet,
  Download,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  Users,
  Search,
  Send,
  EyeOff,
  Pencil,
  Check,
  X,
  History,
  Calendar,
  Info,
  AlertTriangle,
  AlertCircle,
  Plus,
  Trash2,
  CalendarOff,
  Mail,
} from 'lucide-react'
import {
  useGeneratePracticePlanilla,
  usePracticePlanillaHistory,
  usePracticePlanillaDetailWithExclusions,
  usePracticePlanillaStatus,
  useApprovePracticePlanilla,
  useRejectPracticePlanilla,
  usePracticePublicationStatus,
  usePublishPracticeBilling,
  useUnpublishPracticeBilling,
  useSendPracticeBillingEmails,
  usePracticeDesignationOptions,
  downloadPracticePlanilla,
  downloadPracticeSalaryReport,
} from '@/api/hooks/usePracticePlanilla'
import type { PracticePlanillaGenerateResponse } from '@/api/hooks/usePracticePlanilla'
import { LoadingPage } from '@/components/shared/LoadingSpinner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { ExcludedDay } from '@/api/types'

// ─── Types ────────────────────────────────────────────────────────────────────

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

interface PracticeDesignationOption {
  subject: string
  group_code: string
  semester: string
}

type ExclusionRow = ExcludedDay & {
  selectedSemesters?: string[]
  selectedSubjects?: string[]
  subjectSelections?: PracticeDesignationOption[]
}

function getSubjectOptionKey(option: PracticeDesignationOption): string {
  return `${option.subject}||${option.group_code}||${option.semester}`
}

function getSubjectGroupKey(option: PracticeDesignationOption): string {
  return `${option.subject}||${option.group_code}`
}

function getUniqueSubjects(options: PracticeDesignationOption[]): string[] {
  return Array.from(new Set(options.map(o => o.subject))).sort((a, b) => a.localeCompare(b))
}

function getGroupsForSubject(options: PracticeDesignationOption[], subject: string): PracticeDesignationOption[] {
  const seen = new Set<string>()
  return options.filter((o) => {
    if (o.subject !== subject) return false
    const key = getSubjectGroupKey(o)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function expandExcludedDays(rows: ExclusionRow[]): ExcludedDay[] {
  return rows.flatMap<ExcludedDay>((row) => {
    if (row.scope === 'subject') {
      const selections = row.subjectSelections ?? []
      return selections.map((s) => ({
        date: row.date,
        scope: 'subject' as const,
        subject_id: s.subject,
        group_id: s.group_code,
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
    const key = `${excluded.date}||${excluded.scope}||${excluded.reason ?? ''}`
    const current = rows.get(key)

    if (excluded.scope === 'global') {
      if (!current) rows.set(key, { date: excluded.date, scope: 'global', reason: excluded.reason })
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
    const subjectSelections = (current?.subjectSelections ?? []) as PracticeDesignationOption[]
    const selectedSubjects = current?.selectedSubjects ?? []
    const subject = excluded.subject_id
    const group = excluded.group_id
    const hasSelection = subjectSelections.some(s => s.subject === subject && s.group_code === group)
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

function getPlanillaErrorMessage(error: unknown): string {
  const fallback = 'Error al generar la planilla. Verificá que la asistencia esté procesada para el período seleccionado.'
  if (!error || typeof error !== 'object') return fallback
  const response = (error as { response?: { data?: { detail?: unknown } } }).response
  const detail = response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object') {
    const message = (detail as { message?: unknown }).message
    if (typeof message === 'string') return message
  }
  const message = (error as { message?: unknown }).message
  return typeof message === 'string' ? message : fallback
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface PracticaPlanillaContentProps {
  month: number
  year: number
  setMonth: (month: number) => void
  setYear: (year: number) => void
}

// ─── Component ────────────────────────────────────────────────────────────────

export function PracticaPlanillaContent({ month, year, setMonth, setYear }: PracticaPlanillaContentProps) {
  const [lastResult, setLastResult] = useState<PracticePlanillaGenerateResponse | null>(null)
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [datesManuallySet, setDatesManuallySet] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedTeachers, setSelectedTeachers] = useState<Set<string>>(() => new Set())
  const [discountMode, setDiscountMode] = useState<'attendance' | 'full'>('attendance')
  const [discountModeManuallySet, setDiscountModeManuallySet] = useState(false)

  // Payment override state
  const [paymentOverrides, setPaymentOverrides] = useState<Record<string, number>>({})
  const [paymentOverridesEdited, setPaymentOverridesEdited] = useState(false)
  const [editingOverride, setEditingOverride] = useState<string | null>(null)
  const [overrideValue, setOverrideValue] = useState('')

  // Exclusion days state
  const [excludedDays, setExcludedDays] = useState<ExclusionRow[]>([])
  const [exclusionsEdited, setExclusionsEdited] = useState(false)
  const [newExclusion, setNewExclusion] = useState<ExclusionRow>(() => ({ date: new Date().toISOString().slice(0, 10), scope: 'global' }))
  const [exclusionPanelOpen, setExclusionPanelOpen] = useState(false)

  const [salaryReportLoading, setSalaryReportLoading] = useState<Record<string, boolean>>({})
  const [emailSendResult, setEmailSendResult] = useState<{ sent: number; failed: number; skipped: number } | null>(null)
  const [emailSendError, setEmailSendError] = useState(false)

  const restoringHistoryRef = useRef(false)

  // Hooks
  const { data: planillaStatus } = usePracticePlanillaStatus(month, year)
  const { data: publication } = usePracticePublicationStatus(month, year)
  const { data: history, isLoading: historyLoading } = usePracticePlanillaHistory()
  const { data: designationOptions, isLoading: designationOptionsLoading } = usePracticeDesignationOptions(exclusionPanelOpen)
  const generatePlanilla = useGeneratePracticePlanilla()
  const approvePlanilla = useApprovePracticePlanilla()
  const rejectPlanilla = useRejectPracticePlanilla()
  const publishBilling = usePublishPracticeBilling()
  const unpublishBilling = useUnpublishPracticeBilling()
  const sendBillingEmails = useSendPracticeBillingEmails()

  // Reset manual flags when month/year changes
  useEffect(() => {
    if (restoringHistoryRef.current) {
      restoringHistoryRef.current = false
      return
    }
    setDatesManuallySet(false)
    setDiscountModeManuallySet(false)
    setPaymentOverrides({})
    setPaymentOverridesEdited(false)
    setExclusionsEdited(false)
    setExcludedDays([])
  }, [month, year])

  // Auto-fill dates from stored planilla, then fallback to standard period
  useEffect(() => {
    if (datesManuallySet) return
    if (planillaStatus?.start_date && planillaStatus?.end_date) {
      setStartDate(planillaStatus.start_date)
      setEndDate(planillaStatus.end_date)
      return
    }
    // Fallback: standard cut-off period
    const prevMonth = month === 1 ? 12 : month - 1
    const prevYear = month === 1 ? year - 1 : year
    setStartDate(`${prevYear}-${String(prevMonth).padStart(2, '0')}-21`)
    setEndDate(`${year}-${String(month).padStart(2, '0')}-20`)
  }, [planillaStatus, datesManuallySet, month, year])

  // Sync exclusions from stored planilla (when not manually edited)
  useEffect(() => {
    if (exclusionsEdited) return
    setExcludedDays(hydrateExclusionRows(planillaStatus?.excluded_days_json ?? []))
    setExclusionsEdited(false)
  }, [planillaStatus?.excluded_days_json, exclusionsEdited, month, year])

  useEffect(() => {
    if (paymentOverridesEdited) return
    setPaymentOverrides(planillaStatus?.payment_overrides_json ?? {})
  }, [planillaStatus?.payment_overrides_json, paymentOverridesEdited, month, year])

  // Effective discount mode: manual override takes precedence, then stored value
  const effectiveDiscountMode: 'attendance' | 'full' = discountModeManuallySet
    ? discountMode
    : (planillaStatus?.discount_mode === 'attendance' || planillaStatus?.discount_mode === 'full')
      ? planillaStatus.discount_mode
      : discountMode

  const expandedExcludedDays = expandExcludedDays(excludedDays)
  const previewExclusions = exclusionsEdited ? expandedExcludedDays : undefined

  const { data: detail, isLoading: detailLoading } = usePracticePlanillaDetailWithExclusions(
    month,
    year,
    true,
    startDate || undefined,
    endDate || undefined,
    effectiveDiscountMode,
    previewExclusions,
  )

  const isBillingPublished = publication?.status === 'published'

  const visibleTeacherRows = (() => {
    if (!detail?.rows) return []
    const byTeacher = new Map<string, { teacher_ci: string; teacher_name: string; total_gross: number; total_net: number; rows: typeof detail.rows }>()
    for (const row of detail.rows) {
      if (!byTeacher.has(row.teacher_ci)) {
        byTeacher.set(row.teacher_ci, { teacher_ci: row.teacher_ci, teacher_name: row.teacher_name, total_gross: 0, total_net: 0, rows: [] })
      }
      const entry = byTeacher.get(row.teacher_ci)!
      entry.total_gross += row.calculated_payment
      entry.total_net += row.final_payment
      entry.rows.push(row)
    }
    return Array.from(byTeacher.values())
      .filter(t => {
        if (!searchTerm) return true
        const term = searchTerm.toLowerCase()
        return t.teacher_name.toLowerCase().includes(term) || t.teacher_ci.includes(term)
      })
      .sort((a, b) => b.total_gross - a.total_gross)
  })()

  const allVisibleTeachersSelected = visibleTeacherRows.length > 0 && visibleTeacherRows.every(t => selectedTeachers.has(t.teacher_ci))

  useEffect(() => {
    if (!isBillingPublished) setSelectedTeachers(new Set())
  }, [isBillingPublished, month, year])

  const toggleTeacherSelection = (teacherCi: string) => {
    setSelectedTeachers(prev => {
      const next = new Set(prev)
      if (next.has(teacherCi)) next.delete(teacherCi)
      else next.add(teacherCi)
      return next
    })
  }

  const toggleAllVisibleTeachers = () => {
    setSelectedTeachers(prev => {
      const next = new Set(prev)
      if (allVisibleTeachersSelected) {
        visibleTeacherRows.forEach(t => next.delete(t.teacher_ci))
      } else {
        visibleTeacherRows.forEach(t => next.add(t.teacher_ci))
      }
      return next
    })
  }

  const handleSendSelectedBillingEmails = () => {
    if (selectedTeachers.size === 0) return
    setEmailSendResult(null)
    setEmailSendError(false)
    sendBillingEmails.mutate(
      { month, year, teacher_cis: Array.from(selectedTeachers) },
      {
        onSuccess: (result) => {
          setEmailSendResult(result)
          setEmailSendError(false)
          setSelectedTeachers(new Set())
        },
        onError: () => {
          setEmailSendError(true)
          setEmailSendResult(null)
        },
      },
    )
  }

  const handleGenerate = () => {
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
      { onSuccess: (data) => { setLastResult(data); setPaymentOverridesEdited(false) } },
    )
  }

  const resetNewExclusion = () => {
    setNewExclusion({ date: new Date().toISOString().slice(0, 10), scope: 'global' })
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
      if (patch.scope === 'global') return { date: updated.date, scope: 'global', reason: updated.reason }
      if (patch.scope === 'semester') return { date: updated.date, scope: 'semester', selectedSemesters: [], reason: updated.reason }
      if (patch.scope === 'subject') return { date: updated.date, scope: 'subject', selectedSubjects: [], subjectSelections: [], reason: updated.reason }
      return updated
    })
  }

  const canAddExclusion = Boolean(newExclusion.date) && (
    newExclusion.scope === 'global' ||
    (newExclusion.scope === 'semester' && Boolean(newExclusion.selectedSemesters?.length)) ||
    (newExclusion.scope === 'subject' && Boolean(newExclusion.subjectSelections?.length))
  )

  const practiceSubjects = designationOptions?.subjects ?? []
  const practiceSemesters = designationOptions?.semesters ?? []

  return (
    <div className="space-y-6">
      {/* Generator Card */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-6 py-5 border-b border-gray-100">
          <h2 className="text-lg font-semibold" style={{ color: '#003366' }}>Generar Planilla de Prácticas</h2>
          <p className="text-sm text-gray-500 mt-0.5">Seleccioná el período y generá la planilla de haberes docentes asistenciales</p>
        </div>
        <div className="px-6 py-5">
          <div className="flex flex-wrap items-end gap-4">
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

          {/* Cut-off period */}
          <div className="mt-4 bg-gray-50/50 rounded-lg p-4">
            <p className="text-sm text-gray-500 mb-2 font-medium">Período de corte</p>
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
          </div>

          {/* Discount Mode Switch */}
          <div className="mt-4 bg-gray-50/50 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-700">Modo de cálculo</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {effectiveDiscountMode === 'attendance'
                    ? 'Se aplican descuentos por ausencias registradas'
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
                effectiveDiscountMode === 'attendance' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'
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
                          ) : practiceSemesters.length === 0 ? (
                            <p className="text-xs text-gray-400 px-1 py-1">No hay semestres cargados para el período activo.</p>
                          ) : (
                            practiceSemesters.map((semester) => {
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
                                          : selectedSemesters.filter(s => s !== semester),
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
                          ) : practiceSubjects.length === 0 ? (
                            <p className="text-xs text-gray-400 px-1 py-1">No hay materias cargadas para el período activo.</p>
                          ) : (
                            getUniqueSubjects(practiceSubjects).map((subject) => {
                              const selectedSubjects = newExclusion.selectedSubjects ?? []
                              const subjectChecked = selectedSubjects.includes(subject)
                              const groups = getGroupsForSubject(practiceSubjects, subject)
                              return (
                                <div key={subject} className="rounded-md bg-white/60 px-2 py-1.5">
                                  <label className="flex items-center gap-2 text-sm font-medium text-gray-700 cursor-pointer">
                                    <input
                                      type="checkbox"
                                      checked={subjectChecked}
                                      onChange={(e) => {
                                        const currentSelections = (newExclusion.subjectSelections ?? []) as PracticeDesignationOption[]
                                        updateNewExclusion({
                                          selectedSubjects: e.target.checked
                                            ? [...selectedSubjects, subject]
                                            : selectedSubjects.filter(s => s !== subject),
                                          subjectSelections: e.target.checked
                                            ? currentSelections
                                            : currentSelections.filter(s => s.subject !== subject),
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
                                        const checked = ((newExclusion.subjectSelections ?? []) as PracticeDesignationOption[]).some(s => getSubjectOptionKey(s) === optionKey)
                                        return (
                                          <label key={optionKey} className="flex items-center gap-1.5 rounded px-1.5 py-0.5 text-xs text-gray-600 hover:bg-purple-50 cursor-pointer">
                                            <input
                                              type="checkbox"
                                              checked={checked}
                                              onChange={(e) => {
                                                const current = (newExclusion.subjectSelections ?? []) as PracticeDesignationOption[]
                                                updateNewExclusion({
                                                  subjectSelections: e.target.checked
                                                    ? [...current, option]
                                                    : current.filter(s => getSubjectOptionKey(s) !== optionKey),
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
                              row.scope === 'global' ? 'bg-purple-100 text-purple-700' : row.scope === 'semester' ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700'
                            }`}>
                              {row.scope === 'global' ? 'Global' : row.scope === 'semester' ? 'Semestre' : 'Materia'}
                            </span>
                          </div>
                          <div>
                            <p className="text-xs text-gray-400 font-medium">Detalle</p>
                            {row.scope === 'global' && <p className="text-gray-500">Todos los docentes</p>}
                            {row.scope === 'semester' && (
                              <div className="flex flex-wrap gap-1">
                                {(row.selectedSemesters ?? (row.semester_id ? [row.semester_id] : [])).map((s) => (
                                  <span key={s} className="inline-flex rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 border border-blue-100">{s}</span>
                                ))}
                              </div>
                            )}
                            {row.scope === 'subject' && (
                              <div className="flex flex-wrap gap-1">
                                {((row.subjectSelections ?? []) as PracticeDesignationOption[]).map((s) => (
                                  <span key={getSubjectOptionKey(s)} className="inline-flex rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 border border-amber-100">
                                    {s.subject} ({s.group_code})
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
                    <strong>Global</strong>: excluye el día para todos los docentes. <strong>Por semestre</strong>: solo el semestre indicado. <strong>Por materia</strong>: solo la materia y grupo exactos.
                  </p>
                </div>
              </div>
            )}
          </div>

          {generatePlanilla.isError && (
            <div className="mt-4 p-3 bg-red-50 rounded-lg border border-red-200">
              <p className="text-sm text-red-600">
                {getPlanillaErrorMessage(generatePlanilla.error)}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Result Card */}
      {lastResult && (
        <div className="card-3d-static overflow-hidden border-l-4" style={{ borderLeftColor: '#16a34a' }}>
          <div className="py-5 px-5">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <CheckCircle size={24} className="text-green-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-green-700">¡Planilla de prácticas generada exitosamente!</p>
                  <p className="text-sm text-gray-600 mt-1">
                    {MONTH_NAMES[lastResult.month]} {lastResult.year} · {lastResult.total_teachers} docentes · {lastResult.total_hours}h totales
                  </p>
                  <p className="text-lg font-bold mt-2" style={{ color: '#003366' }}>
                    Total: Bs {parseFloat(lastResult.total_payment).toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                  {lastResult.warnings.length > 0 && (
                    <p className="text-xs text-yellow-600 mt-1">{lastResult.warnings.length} advertencia(s) durante la generación</p>
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
                          discount_mode: effectiveDiscountMode,
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
            <div className="p-5"><LoadingPage /></div>
          ) : !history || history.length === 0 ? (
            <div className="text-center py-10 text-gray-400 text-sm">No hay planillas de prácticas generadas aún</div>
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
                        setDatesManuallySet(true)
                        setStartDate(item.start_date ?? '')
                        setEndDate(item.end_date ?? '')
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
                          : <span className="text-gray-300">—</span>}
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
                        <Badge className={
                          item.status?.toLowerCase() === 'approved' ? 'bg-green-100 text-green-700 text-xs'
                          : item.status?.toLowerCase() === 'rejected' ? 'bg-red-100 text-red-700 text-xs'
                          : 'bg-yellow-100 text-yellow-700 text-xs'
                        }>
                          {item.status?.toLowerCase() === 'approved' ? 'Aprobada'
                            : item.status?.toLowerCase() === 'rejected' ? 'Rechazada'
                            : 'Pend. Aprobación'}
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
                                  await downloadPracticeSalaryReport({ month: item.month, year: item.year, discount_mode: item.discount_mode })
                                } finally {
                                  setSalaryReportLoading(prev => ({ ...prev, [key]: false }))
                                }
                              }}
                              disabled={salaryReportLoading[`row-${item.id}`]}
                              className="inline-flex items-center gap-1 px-2 py-1 rounded text-green-700 hover:bg-green-50 border border-green-600/30 text-xs font-medium transition-colors disabled:opacity-50"
                            >
                              {salaryReportLoading[`row-${item.id}`] ? <Loader2 size={12} className="animate-spin" /> : <FileSpreadsheet size={12} />}
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

      {/* Approval Status */}
      {planillaStatus && (
        <div className="card-3d-static overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                planillaStatus.status === 'approved' ? 'bg-green-100' : planillaStatus.status === 'rejected' ? 'bg-red-100' : 'bg-yellow-100'
              }`}>
                {planillaStatus.status === 'approved'
                  ? <CheckCircle size={16} className="text-green-600" />
                  : planillaStatus.status === 'rejected'
                    ? <XCircle size={16} className="text-red-600" />
                    : <Clock size={16} className="text-yellow-600" />}
              </div>
              <div>
                <h3 className="text-base font-semibold" style={{ color: '#003366' }}>Estado de la Planilla</h3>
                <p className="text-xs text-gray-500">
                  {planillaStatus.status === 'approved' ? 'Aprobada — lista para publicar'
                    : planillaStatus.status === 'rejected' ? 'Rechazada — requiere regeneración'
                    : 'Pendiente de aprobación'}
                </p>
              </div>
            </div>
            {planillaStatus.status === 'generated' && (
              <div className="flex items-center gap-2">
                <Button size="sm" className="bg-green-600 hover:bg-green-700 text-white gap-1"
                  onClick={() => approvePlanilla.mutate(planillaStatus.id)}
                  disabled={approvePlanilla.isPending}
                >
                  <Check size={14} /> Aprobar
                </Button>
                <Button size="sm" variant="outline" className="border-red-300 text-red-600 hover:bg-red-50 gap-1"
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

      {/* Publication Status */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
              publication?.status === 'published' ? 'bg-green-100' : 'bg-gray-100'
            }`}>
              {publication?.status === 'published'
                ? <Send size={16} className="text-green-600" />
                : <EyeOff size={16} className="text-gray-400" />}
            </div>
            <div>
              <h3 className="text-base font-semibold" style={{ color: '#003366' }}>Publicación de Facturación</h3>
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
            <Button variant="outline" className="border-red-300 text-red-600 hover:bg-red-50 gap-2"
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
              <span className="text-green-600">({publication.total_teachers} docentes · Bs {publication.total_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })})</span>
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

      {/* Detail Section */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 flex items-center gap-3 border-b border-gray-100">
          <div className="w-8 h-8 rounded-lg gradient-stat-navy flex items-center justify-center">
            <Users size={16} className="text-white" />
          </div>
          <div>
            <h3 className="text-base font-semibold" style={{ color: '#003366' }}>Detalle por Docente</h3>
            <p className="text-xs text-gray-500">
              {detail ? `${detail.total_teachers} docentes` : 'Cargando...'} · {MONTH_NAMES[month]} {year}
            </p>
          </div>
        </div>

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
                    {detail.warnings.map((w, i) => <li key={i}>- {w}</li>)}
                  </ul>
                </div>
              )}

              {/* Selection bar + search */}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex gap-1 rounded-xl p-1 w-fit" style={{ backgroundColor: '#16a34a15' }}>
                  <span className="px-5 py-2 rounded-lg text-sm font-semibold bg-emerald-600 text-white shadow-md shadow-emerald-900/25">
                    Por Docente
                  </span>
                </div>
                <div className="relative flex-1 min-w-[200px] max-w-sm">
                  <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-emerald-600/50" />
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="Buscar docente por nombre o CI..."
                    className="w-full pl-10 pr-4 py-2.5 border-2 border-emerald-600/20 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-emerald-600/30 focus:border-emerald-600/40 bg-white shadow-sm placeholder:text-slate-400 transition-all duration-200"
                  />
                </div>
              </div>

              {/* Select-all + email controls */}
              {isBillingPublished && (
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#0066CC]/20 bg-blue-50/50 px-4 py-3">
                  <label className="flex items-center gap-2 text-sm font-medium text-gray-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={allVisibleTeachersSelected}
                      onChange={toggleAllVisibleTeachers}
                      disabled={visibleTeacherRows.length === 0}
                      className="h-4 w-4 rounded border-gray-300 text-[#0066CC] focus:ring-[#0066CC]"
                    />
                    Seleccionar todos
                  </label>
                  <Badge className="bg-[#003366] text-white">{selectedTeachers.size} seleccionado(s)</Badge>
                </div>
              )}

              {isBillingPublished && selectedTeachers.size > 0 && (
                <div className="rounded-xl border border-[#0066CC]/30 bg-[#003366] px-5 py-4 text-white shadow-lg">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center justify-center w-9 h-9 rounded-full bg-white/15">
                        <Mail size={18} className="text-white" />
                      </div>
                      <div>
                        <p className="text-sm font-bold">{selectedTeachers.size} docente(s) seleccionado(s)</p>
                        <p className="text-xs text-white/60">Seleccioná los docentes a quienes enviar el correo</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                      <Button
                        type="button"
                        onClick={handleSendSelectedBillingEmails}
                        disabled={sendBillingEmails.isPending}
                        className="gap-2 bg-white text-[#003366] font-semibold hover:bg-[#f4b400] hover:text-[#003366] transition-all duration-200 shadow-md hover:shadow-lg"
                      >
                        {sendBillingEmails.isPending ? <Loader2 size={16} className="animate-spin" /> : <Mail size={16} />}
                        Enviar correo
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => setSelectedTeachers(new Set())}
                        disabled={sendBillingEmails.isPending}
                        className="border-white/50 text-white bg-white/10 hover:bg-white/25 hover:text-white font-medium transition-all duration-200"
                      >
                        Limpiar selección
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {/* Email result banners */}
              {emailSendResult && (
                <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3">
                  <div className="flex items-start gap-3">
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-green-100 flex-shrink-0">
                      <CheckCircle size={18} className="text-green-600" />
                    </div>
                    <div className="flex-1">
                      <p className="font-semibold text-green-800 text-sm">Correos procesados exitosamente</p>
                      <div className="flex flex-wrap gap-4 mt-1.5">
                        {emailSendResult.sent > 0 && (
                          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green-700 bg-green-100 px-2.5 py-1 rounded-full">
                            <span className="w-2 h-2 rounded-full bg-green-500" />{emailSendResult.sent} enviado(s)
                          </span>
                        )}
                        {emailSendResult.failed > 0 && (
                          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-red-700 bg-red-100 px-2.5 py-1 rounded-full">
                            <span className="w-2 h-2 rounded-full bg-red-500" />{emailSendResult.failed} fallido(s)
                          </span>
                        )}
                        {emailSendResult.skipped > 0 && (
                          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-600 bg-gray-100 px-2.5 py-1 rounded-full">
                            <span className="w-2 h-2 rounded-full bg-gray-400" />{emailSendResult.skipped} omitido(s)
                          </span>
                        )}
                      </div>
                    </div>
                    <button onClick={() => setEmailSendResult(null)} className="p-1 rounded-md hover:bg-green-100 text-green-400 hover:text-green-600 transition-colors flex-shrink-0">
                      <X size={14} />
                    </button>
                  </div>
                </div>
              )}
              {emailSendError && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
                  <div className="flex items-start gap-3">
                    <AlertCircle size={18} className="text-red-500 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="font-semibold text-red-800 text-sm">No se pudieron enviar los correos</p>
                      <p className="text-xs text-red-600 mt-0.5">Verificá la configuración de email e intentá nuevamente.</p>
                    </div>
                    <button onClick={() => setEmailSendError(false)} className="p-1 rounded-md hover:bg-red-100 text-red-400 hover:text-red-600 transition-colors flex-shrink-0">
                      <X size={14} />
                    </button>
                  </div>
                </div>
              )}

              {/* Teacher cards */}
              <div className="space-y-3">
                {visibleTeacherRows.map(teacher => (
                  <div key={teacher.teacher_ci} className="border border-gray-200 rounded-lg overflow-hidden">
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
                          <p className="text-xs text-gray-500">CI: {teacher.teacher_ci} · {teacher.rows.length} materia(s)</p>
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
                                  setPaymentOverridesEdited(true)
                                }
                                setEditingOverride(null); setOverrideValue('')
                              }}
                              className="text-green-600 hover:text-green-800"
                            >
                              <Check size={14} />
                            </button>
                            <button onClick={() => { setEditingOverride(null); setOverrideValue('') }} className="text-gray-400 hover:text-gray-600">
                              <X size={14} />
                            </button>
                          </div>
                        ) : (
                          <div className="flex flex-col items-end gap-0.5">
                            <p className="text-xs text-gray-400">
                              Bruto: Bs {teacher.total_gross.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                            </p>
                            <div className="flex items-center gap-2">
                              <p
                                className={`text-lg font-bold ${paymentOverrides[teacher.teacher_ci] != null ? 'line-through text-red-700' : 'text-green-700'}`}
                              >
                                Neto: Bs {teacher.total_net.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                              </p>
                              {paymentOverrides[teacher.teacher_ci] != null && (
                                <p className="text-lg font-bold text-green-700">
                                  Bs {paymentOverrides[teacher.teacher_ci].toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                                </p>
                              )}
                              <button
                                onClick={() => {
                                  setEditingOverride(teacher.teacher_ci)
                                  setOverrideValue(String(paymentOverrides[teacher.teacher_ci] ?? teacher.total_net))
                                }}
                                className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-[#0066CC] transition-colors"
                                title="Ajustar monto"
                              >
                                <Pencil size={13} />
                              </button>
                            </div>
                            {paymentOverrides[teacher.teacher_ci] != null && (
                              <button
                                onClick={() => {
                                  setPaymentOverrides(prev => { const next = { ...prev }; delete next[teacher.teacher_ci]; return next })
                                  setPaymentOverridesEdited(true)
                                }}
                                className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-red-500 transition-colors"
                                title="Quitar ajuste"
                              >
                                <X size={13} />
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                    {/* Designations */}
                    <div className="divide-y divide-gray-100">
                      {teacher.rows.map(row => (
                        <div key={`${row.subject}-${row.group_code}`} className="flex items-center justify-between px-4 py-2 text-sm">
                          <div className="flex items-center gap-2">
                            <span className="text-gray-700">{row.subject}</span>
                            <Badge className="bg-gray-100 text-gray-600 text-xs">{row.group_code}</Badge>
                            <span className="text-gray-400 text-xs">{row.semester}</span>
                          </div>
                          <div className="flex items-center gap-4 text-xs">
                            <span className="text-gray-500">{row.base_monthly_hours}h base</span>
                            {row.absent_hours > 0 && <span className="text-red-500">-{row.absent_hours}h</span>}
                            <span className="font-semibold text-gray-800">{row.payable_hours}h</span>
                            <span className="font-bold min-w-[80px] text-right" style={{ color: '#003366' }}>
                              Bs {row.final_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                              {row.has_retention && <span className="ml-1 text-xs text-red-500 font-medium">(con retención)</span>}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              {/* Full detail table */}
              <details className="mt-2">
                <summary className="text-sm text-[#0066CC] cursor-pointer hover:underline font-medium">Ver tabla completa por designación</summary>
                <div className="mt-3 overflow-x-auto rounded-lg border border-gray-200">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)' }}>
                        {['Docente', 'Materia', 'Grupo', 'Sem.', 'Hrs Base', 'Ausencias', 'Hrs a Pagar', 'Monto (Bs)', 'Retención', 'Neto (Bs)', 'Observación'].map(h => (
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
                          <tr key={`${row.teacher_ci}-${row.subject}-${row.group_code}`} className={`border-b last:border-0 hover:bg-blue-50/70 transition-colors ${i % 2 === 1 ? 'bg-gray-50' : 'bg-white'}`}>
                            <td className="px-3 py-2.5 font-medium text-gray-800 max-w-[200px] truncate">{row.teacher_name}</td>
                            <td className="px-3 py-2.5 text-gray-700 max-w-[180px] truncate">{row.subject}</td>
                            <td className="px-3 py-2.5 text-gray-600">{row.group_code}</td>
                            <td className="px-3 py-2.5 text-gray-600">{row.semester}</td>
                            <td className="px-3 py-2.5 text-gray-700 font-medium">{row.base_monthly_hours}h</td>
                            <td className="px-3 py-2.5">{row.absent_hours > 0 ? <span className="text-red-600 font-medium">-{row.absent_hours}h</span> : <span className="text-green-600">0h</span>}</td>
                            <td className="px-3 py-2.5 text-gray-800 font-semibold">{row.payable_hours}h</td>
                            <td className="px-3 py-2.5 font-bold" style={{ color: '#003366' }}>{row.calculated_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })}</td>
                            <td className="px-3 py-2.5">{row.has_retention ? <span className="text-red-600 font-medium">-{row.retention_amount.toLocaleString('es-BO', { minimumFractionDigits: 2 })}</span> : <span className="text-gray-400">—</span>}</td>
                            <td className="px-3 py-2.5 font-bold text-green-700">{row.final_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })}</td>
                            <td className="px-3 py-2.5 text-gray-500 text-xs max-w-[150px] truncate" title={row.observation}>{row.observation || '—'}</td>
                          </tr>
                        ))}
                    </tbody>
                    <tfoot>
                      <tr className="bg-gray-100 font-semibold border-t-2 border-gray-300">
                        <td colSpan={7} className="px-3 py-2.5 text-right text-gray-700">Totales:</td>
                        <td className="px-3 py-2.5 font-bold" style={{ color: '#003366' }}>{detail.total_gross.toLocaleString('es-BO', { minimumFractionDigits: 2 })}</td>
                        <td className="px-3 py-2.5 font-bold text-red-600">-{detail.total_retention.toLocaleString('es-BO', { minimumFractionDigits: 2 })}</td>
                        <td className="px-3 py-2.5 font-bold text-green-700">{detail.total_net.toLocaleString('es-BO', { minimumFractionDigits: 2 })}</td>
                        <td />
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </details>
            </div>
          ) : (
            <div className="text-center py-10 text-gray-400 text-sm">
              No hay datos para {MONTH_NAMES[month]} {year}. Generá la planilla para ver el detalle.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
