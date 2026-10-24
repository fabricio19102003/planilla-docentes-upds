import { useState, useEffect, useRef, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { FileSpreadsheet, Download, Users, Search, Send, EyeOff, Pencil, Check, X, History, Calendar, Info, AlertTriangle, AlertCircle, Plus, Trash2, CalendarOff, Mail, MessageCircle, CheckCircle, BookOpen, Wallet, Calculator, ChevronDown, ChevronUp } from 'lucide-react'
import { useGeneratePlanilla, usePlanillaHistory, downloadPlanilla, downloadSalaryReport, usePlanillaDetail, useApprovePlanilla, useRejectPlanilla, usePlanillaStatus } from '@/api/hooks/usePlanilla'
import { useBillingNotificationBatch, useBillingNotificationReadiness, useConfirmBillingNotifications, usePreviewBillingNotifications, usePublicationStatus, usePublishBilling, useUnpublishBilling, useSendBillingEmails, type BillingNotificationPreview } from '@/api/hooks/useBillingPublication'
import { useBiometricDateRange } from '@/api/hooks/useBiometric'
import { api } from '@/api/client'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardDescription, CardHeader, CardPanel, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsList, TabsTab } from '@/components/ui/tabs'
import { formatDateInBolivia as formatDate, formatShortDateInBolivia as formatShortDate, getTodayInBolivia } from '@/lib/boliviaDates'
import { formatHours } from '@/lib/displayFormat'
import { planillaRowNote } from '@/lib/closedDesignation'
import { getHistoricalPaymentState, getVisiblePlanillaDetail } from '@/lib/planillaHistory'
import { cn } from '@/lib/utils'
import type { DesignationOption, DesignationOptions, ExcludedDay, PlanillaGenerateResponse } from '@/api/types'
import { ConfirmActionDialog } from '@/components/shared/ConfirmActionDialog'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { TableCard } from '@/components/shared/TableCard'
import { TONE_CHIP, TONE_TEXT } from '@/components/shared/tones'
import {
  buildConfirmSummary,
  DISCOUNT_MODE_LABELS,
  formatGenerationSummary,
  getGenerationGuard,
  optionalDate,
  resolveDiscountMode,
  type DiscountMode,
  type PlanillaConfirmAction,
} from '@/lib/planillaGenerationGuard'
import { PracticaPlanillaContent } from './PracticaPlanillaContent'

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

const MONTH_ITEMS = Object.entries(MONTH_NAMES).map(([value, label]) => ({ value, label }))

/** Card header action: below the title on mobile, on the right from `sm`. */
const HEADER_ACTION = 'col-start-1 row-start-3 mt-2 flex-wrap items-center justify-self-start gap-2 sm:col-start-2 sm:row-span-2 sm:row-start-1 sm:mt-0 sm:justify-self-end'

const SCOPE_ITEMS = [
  { value: 'global', label: 'Global' },
  { value: 'semester', label: 'Por semestre' },
  { value: 'subject', label: 'Por materia' },
]

type ExclusionRow = ExcludedDay & {
  selectedSemesters?: string[]
  selectedSubjects?: string[]
  subjectSelections?: DesignationOption[]
}

function getSubjectOptionKey(option: DesignationOption): string {
  return `${option.subject}||${option.group_code}||${option.semester}`
}

function getUniqueSubjects(options: DesignationOption[]): string[] {
  return Array.from(new Set(options.map(option => option.subject))).sort((a, b) => a.localeCompare(b))
}

function getGroupsForSubject(options: DesignationOption[], subject: string): DesignationOption[] {
  const seen = new Set<string>()
  return options.filter((option) => {
    if (option.subject !== subject) return false
    const key = getSubjectOptionKey(option)
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
        semester_id: selection.semester || undefined,
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
    const semester = excluded.semester_id ?? ''
    const hasSelection = subjectSelections.some(selection => (
      selection.subject === subject
      && selection.group_code === group
      && selection.semester === semester
    ))

    rows.set(key, {
      date: excluded.date,
      scope: 'subject',
      reason: excluded.reason,
      selectedSubjects: subject && !selectedSubjects.includes(subject)
        ? [...selectedSubjects, subject]
        : selectedSubjects,
      subjectSelections: subject && group && !hasSelection
        ? [...subjectSelections, { subject, group_code: group, semester }]
        : subjectSelections,
    })
  }

  return Array.from(rows.values())
}

export function PlanillaPage() {
  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1

  const [searchParams, setSearchParams] = useSearchParams()
  const planillaTab: 'teoricas' | 'practicas' = searchParams.get('tab') === 'practicas' ? 'practicas' : 'teoricas'
  const setPlanillaTab = (next: 'teoricas' | 'practicas') => {
    setSearchParams((current) => {
      const params = new URLSearchParams(current)
      params.set('tab', next)
      return params
    }, { replace: true })
  }
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
  const [discountMode, setDiscountMode] = useState<DiscountMode | null>(null)
  const [discountModeManuallySet, setDiscountModeManuallySet] = useState(false)
  const [pendingConfirm, setPendingConfirm] = useState<PlanillaConfirmAction | null>(null)

  // Payment override state
  const [paymentOverrides, setPaymentOverrides] = useState<Record<string, number>>({})
  const [editingOverride, setEditingOverride] = useState<string | null>(null)
  const [overrideValue, setOverrideValue] = useState('')

  // Exclusion days state
  const [excludedDays, setExcludedDays] = useState<ExclusionRow[]>([])
  const [exclusionsEdited, setExclusionsEdited] = useState(false)
  const [newExclusion, setNewExclusion] = useState<ExclusionRow>(() => ({ date: getTodayInBolivia(), scope: 'global' }))
  const [exclusionPanelOpen, setExclusionPanelOpen] = useState(false)
  const [designationOptions, setDesignationOptions] = useState<DesignationOptions>({ subjects: [], semesters: [], groups: [] })
  const [designationOptionsLoading, setDesignationOptionsLoading] = useState(false)
  const restoringHistoryRef = useRef(false)

  // Salary report download loading state (keyed by planilla id for history rows,
  // "current" for the main action bar). Using a map lets multiple rows spin
  // independently without one blocking the others.
  const [salaryReportLoading, setSalaryReportLoading] = useState<Record<string, boolean>>({})

  const { data: bioRange } = useBiometricDateRange(month, year)
  const { data: planillaStatus, isLoading: planillaStatusLoading } = usePlanillaStatus(month, year)

  // Reset manual flags when month/year changes so auto-fill can run again
  useEffect(() => {
    if (restoringHistoryRef.current) {
      restoringHistoryRef.current = false
      return
    }

    setDatesManuallySet(false)
    setDiscountModeManuallySet(false)
    setDiscountMode(null)
    setPendingConfirm(null)
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

  // Derive the effective discount mode: the admin's explicit choice for this
  // period, else the stored planilla's mode, else none (Generate stays blocked
  // until a mode is chosen). It never carries over from another period.
  const effectiveDiscountMode: DiscountMode | null = resolveDiscountMode({
    manualMode: discountModeManuallySet ? discountMode : null,
    storedMode: planillaStatus?.discount_mode,
  })

  const expandedExcludedDays = expandExcludedDays(excludedDays)
  // Pass exclusions to detail preview only when the user has actively edited them.
  // undefined = inherit stored exclusions; [] = explicit clear (no exclusions).
  const previewExclusions = exclusionsEdited ? expandedExcludedDays : undefined
  const selectedHistoryState = planillaStatus ? getHistoricalPaymentState(planillaStatus) : null
  const canUseSelectedSnapshot = !planillaStatusLoading && (!selectedHistoryState || selectedHistoryState.snapshotAvailable)
  const detailQuery = usePlanillaDetail(month, year, showDetail && canUseSelectedSnapshot && effectiveDiscountMode !== null, optionalDate(startDate), optionalDate(endDate), effectiveDiscountMode ?? undefined, previewExclusions)
  const detail = getVisiblePlanillaDetail(detailQuery.data, detailQuery.isPlaceholderData, canUseSelectedSnapshot)
  const detailLoading = detailQuery.isLoading
  const detailError = detailQuery.isError
  // Generate must wait until the preview reflects the current form, so the
  // confirmation never shows totals computed for other dates or another mode.
  const previewPending = showDetail && canUseSelectedSnapshot && effectiveDiscountMode !== null
    && (detailQuery.isFetching || detailQuery.isDebouncing)
  const publishBilling = usePublishBilling()
  const unpublishBilling = useUnpublishBilling()
  const sendBillingEmails = useSendBillingEmails()
  const whatsAppReadiness = useBillingNotificationReadiness(publication?.status === 'published')
  const previewBillingNotifications = usePreviewBillingNotifications()
  const confirmBillingNotifications = useConfirmBillingNotifications()
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

  const [emailSendResult, setEmailSendResult] = useState<{ sent: number; failed: number; skipped: number } | null>(null)
  const [emailSendError, setEmailSendError] = useState(false)
  const [whatsAppPreview, setWhatsAppPreview] = useState<BillingNotificationPreview | null>(null)
  const [whatsAppBatchId, setWhatsAppBatchId] = useState<number | null>(null)
  const [whatsAppError, setWhatsAppError] = useState<string | null>(null)
  const whatsAppBatch = useBillingNotificationBatch(whatsAppBatchId)

  const hasSafeWhatsAppPreview = Boolean(
    whatsAppPreview?.readiness.ready
    && whatsAppPreview.readiness.capacity?.available
    && !whatsAppPreview.readiness.capacity?.exceeded,
  )

  const handlePreviewWhatsAppNotifications = () => {
    if (selectedTeachers.size === 0) return
    setWhatsAppError(null)
    setWhatsAppBatchId(null)
    previewBillingNotifications.mutate(
      { month, year, teacher_cis: Array.from(selectedTeachers) },
      {
        onSuccess: setWhatsAppPreview,
        onError: () => setWhatsAppError('No se pudo generar una vista previa segura. No se creó ningún envío.'),
      },
    )
  }

  const handleConfirmWhatsAppNotifications = () => {
    if (!whatsAppPreview || !hasSafeWhatsAppPreview) return
    confirmBillingNotifications.mutate(
      { month, year, teacher_cis: Array.from(selectedTeachers), digest: whatsAppPreview.digest },
      {
        onSuccess: ({ batch_id }) => {
          setWhatsAppBatchId(batch_id)
          setWhatsAppPreview(null)
          setSelectedTeachers(new Set())
        },
        onError: (error: unknown) => {
          const code = (error as { response?: { data?: { detail?: { code?: string } } } })?.response?.data?.detail?.code
          setWhatsAppError(
            code === 'stale_notification_plan'
              ? 'La vista previa cambió. Generá una nueva antes de confirmar.'
              : code === 'notification_capacity_exceeded'
                ? 'La capacidad actual no alcanza para este grupo. No se creó ningún envío.'
                : code === 'notification_readiness_unavailable'
                  ? 'WhatsApp no está listo para enviar. No se creó ningún envío.'
                  : 'No se pudo confirmar el envío. No se creó ningún envío.',
          )
          setWhatsAppPreview(null)
        },
      },
    )
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

  const generationGuard = getGenerationGuard({
    startDate,
    endDate,
    mode: effectiveDiscountMode,
    statusLoading: planillaStatusLoading,
    previewPending,
  })

  const validateExclusions = () => {
    for (let i = 0; i < excludedDays.length; i++) {
      const row = excludedDays[i]
      if (row.scope === 'semester' && (!row.selectedSemesters || row.selectedSemesters.length === 0)) {
        alert(`Exclusión #${i + 1}: seleccioná al menos un semestre o cambiá el alcance.`)
        return false
      }
      if (row.scope === 'subject' && (!row.subjectSelections || row.subjectSelections.length === 0)) {
        alert(`Exclusión #${i + 1}: seleccioná al menos una materia/grupo o cambiá el alcance.`)
        return false
      }
    }
    return true
  }

  const runGenerate = () => {
    // Guard guarantees both dates and a mode; never send undefined cutoffs.
    if (!generationGuard.canGenerate || !effectiveDiscountMode) return

    setLastResult(null)

    generatePlanilla.mutate(
      {
        month,
        year,
        payment_overrides: paymentOverrides,
        start_date: startDate,
        end_date: endDate,
        discount_mode: effectiveDiscountMode,
        excluded_days: expandedExcludedDays.length > 0 ? expandedExcludedDays : undefined,
      },
      {
        onSuccess: (data) => setLastResult(data),
      },
    )
  }

  const requestConfirm = (action: PlanillaConfirmAction) => {
    if (action === 'generate' && (!generationGuard.canGenerate || !validateExclusions())) return
    setPendingConfirm(action)
  }

  const confirmSummary = (() => {
    if (!pendingConfirm) return null
    const stored = pendingConfirm === 'generate' ? null : planillaStatus
    const storedState = stored ? getHistoricalPaymentState(stored) : null
    const live = pendingConfirm === 'unpublish' && publication?.status === 'published' ? publication : null
    const summary = buildConfirmSummary({
      action: pendingConfirm,
      kind: 'teoricas',
      month,
      year,
      startDate: stored ? stored.start_date : startDate,
      endDate: stored ? stored.end_date : endDate,
      mode: stored ? (stored.discount_mode ?? null) : effectiveDiscountMode,
      docentes: live ? live.total_teachers : stored ? stored.total_teachers : detail?.total_teachers,
      totalPayment: live ? live.total_payment : stored ? storedState?.amount : detail?.total_payment,
      totalsAreEstimate: pendingConfirm === 'generate',
      hasStoredPlanilla: Boolean(planillaStatus),
    })
    // Generating over an approved planilla replaces it and sends it back to approval: confirm in the destructive tone.
    if (pendingConfirm === 'generate' && planillaStatus?.status === 'approved') {
      return {
        ...summary,
        tone: 'destructive' as const,
        warning: `La planilla de ${MONTH_NAMES[month]} ${year} ya está aprobada. Al generar se va a reemplazar y vuelve a quedar pendiente de aprobación.`,
      }
    }
    return summary
  })()

  const runConfirmedAction = () => {
    const action = pendingConfirm
    setPendingConfirm(null)
    if (action === 'generate') runGenerate()
    else if (action === 'approve' && planillaStatus) approvePlanilla.mutate(planillaStatus.id)
    else if (action === 'reject' && planillaStatus) rejectPlanilla.mutate(planillaStatus.id)
    else if (action === 'publish') publishBilling.mutate({ month, year })
    else if (action === 'unpublish') unpublishBilling.mutate({ month, year })
  }

  const resetNewExclusion = () => {
    const today = getTodayInBolivia()
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

  const restoreFromHistory = (item: NonNullable<typeof history>[number]) => {
    restoringHistoryRef.current = item.month !== month || item.year !== year
    setMonth(item.month)
    setYear(item.year)
    setStartDate(item.start_date ?? '')
    setEndDate(item.end_date ?? '')
    setDatesManuallySet(true)
    setDiscountMode(item.discount_mode)
    setDiscountModeManuallySet(true)
    setExclusionsEdited(false)
  }

  const publicationNotices: Array<{ key: string; variant: 'success' | 'warning'; content: ReactNode }> = []
  if (publication?.status === 'published') {
    publicationNotices.push({
      key: 'published',
      variant: 'success',
      content: (
        <>
          Los docentes pueden ver sus montos a facturar para {MONTH_NAMES[month]} {year}.
          {publication.total_teachers > 0 && (
            <span className="ml-1 tabular-nums">
              ({publication.total_teachers} docentes · Bs {publication.total_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })})
            </span>
          )}
        </>
      ),
    })
  } else {
    if (!planillaStatus) {
      publicationNotices.push({ key: 'missing', variant: 'warning', content: 'Generá y aprobá la planilla antes de publicar.' })
    } else if (planillaStatus.status !== 'approved') {
      publicationNotices.push({
        key: 'not-approved',
        variant: 'warning',
        content: planillaStatus.status === 'rejected'
          ? 'La planilla fue rechazada. Regenerá con los ajustes necesarios.'
          : 'Aprobá la planilla antes de publicar para docentes.',
      })
    }
    if (exclusionsEdited) {
      publicationNotices.push({
        key: 'exclusions',
        variant: 'warning',
        content: 'Regenerá la planilla para aplicar los cambios de exclusiones antes de publicar.',
      })
    }
  }

  const bioExtendsRange = Boolean(
    bioRange?.has_data && startDate && endDate
    && (startDate < (bioRange.suggested_start ?? '') || endDate > (bioRange.suggested_end ?? '')),
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Planilla de Pagos"
        description="Generá, aprobá y publicá la planilla de haberes docentes."
        actions={(
          <div className="flex items-end gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="planilla-month">Mes</Label>
              <Select
                value={String(month)}
                items={MONTH_ITEMS}
                onValueChange={(value) => setMonth(Number(value))}
              >
                <SelectTrigger id="planilla-month" className="min-w-36"><SelectValue /></SelectTrigger>
                <SelectPopup>
                  {MONTH_ITEMS.map(({ value, label }) => (
                    <SelectItem key={value} value={value}>{label}</SelectItem>
                  ))}
                </SelectPopup>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="planilla-year">Año</Label>
              <Input
                id="planilla-year"
                type="number"
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                min={2020}
                max={2030}
                className="w-24"
                inputClassName="tabular-nums"
              />
            </div>
          </div>
        )}
      />

      {/* Teóricas / Prácticas switch */}
      <Tabs value={planillaTab} onValueChange={(value) => setPlanillaTab(value as 'teoricas' | 'practicas')}>
        <TabsList>
          <TabsTab value="teoricas">Teóricas</TabsTab>
          <TabsTab value="practicas">Prácticas</TabsTab>
        </TabsList>
      </Tabs>

      {/* Prácticas tab content */}
      {planillaTab === 'practicas' && (
        <PracticaPlanillaContent month={month} year={year} setMonth={setMonth} setYear={setYear} />
      )}

      {/* Teóricas tab content */}
      {planillaTab === 'teoricas' && (
      <div className="space-y-6">
      {/* Generator Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Generar Planilla de Pagos</CardTitle>
          <CardDescription>Seleccioná el período y generá la planilla de haberes docentes</CardDescription>
        </CardHeader>
        <CardPanel className="space-y-5">
          <div className="flex flex-wrap items-center gap-4">
            <Button
              size="lg"
              onClick={() => requestConfirm('generate')}
              disabled={generatePlanilla.isPending || !generationGuard.canGenerate}
              loading={generatePlanilla.isPending}
            >
              <FileSpreadsheet />
              {generatePlanilla.isPending ? 'Generando...' : 'Generar Planilla'}
            </Button>
            <div className="text-sm" aria-live="polite">
              {generationGuard.canGenerate && effectiveDiscountMode ? (
                <p className="text-muted-foreground">
                  {formatGenerationSummary({ kind: 'teoricas', month, year, startDate, endDate, mode: effectiveDiscountMode })}
                </p>
              ) : (
                generationGuard.reasons.map((reason) => (
                  <p key={reason} className={cn('font-medium', TONE_TEXT.warning)}>{reason}</p>
                ))
              )}
            </div>
          </div>

          {Object.keys(paymentOverrides).length > 0 && (
            <Alert variant="warning">
              <AlertTriangle />
              <AlertTitle>{Object.keys(paymentOverrides).length} ajuste(s) de monto pendiente(s)</AlertTitle>
              <AlertDescription>Estos ajustes se aplicarán al generar la planilla</AlertDescription>
            </Alert>
          )}

          {/* Cut-off period */}
          <section className="space-y-3 border-t pt-5">
            <h3 className="text-sm font-semibold text-foreground">Período de corte</h3>

            {/* Biometric coverage */}
            {bioRange && (
              bioRange.has_data ? (
                <Alert variant="info">
                  <Info />
                  <AlertTitle>Rango biométrico detectado</AlertTitle>
                  <AlertDescription>
                    <p>{bioRange.message}</p>
                    <p>
                      Las fechas de inicio y fin se han ajustado automáticamente al rango del biométrico.
                      Puede modificarlas si lo necesita.
                    </p>
                  </AlertDescription>
                </Alert>
              ) : (
                <Alert variant="warning">
                  <AlertTriangle />
                  <AlertTitle>Sin datos biométricos</AlertTitle>
                  <AlertDescription>{bioRange.message}</AlertDescription>
                </Alert>
              )
            )}

            <div className="flex flex-wrap items-end gap-4">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="cutoff-start">Fecha inicio</Label>
                <Input
                  id="cutoff-start"
                  type="date"
                  value={startDate}
                  onChange={(e) => { setStartDate(e.target.value); setDatesManuallySet(true) }}
                  className="w-44"
                  inputClassName="tabular-nums"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="cutoff-end">Fecha fin</Label>
                <Input
                  id="cutoff-end"
                  type="date"
                  value={endDate}
                  onChange={(e) => { setEndDate(e.target.value); setDatesManuallySet(true) }}
                  className="w-44"
                  inputClassName="tabular-nums"
                />
              </div>
              <p className="pb-2 text-xs text-muted-foreground">
                Estándar: del 21 del mes anterior al 20 del mes actual
              </p>
            </div>

            {/* Warning: dates extend beyond biometric coverage */}
            {bioExtendsRange && bioRange && (
              <Alert variant="warning">
                <AlertTriangle />
                <AlertTitle>Rango extendido más allá del biométrico</AlertTitle>
                <AlertDescription>
                  El rango seleccionado ({startDate} — {endDate}) excede la cobertura del biométrico
                  ({bioRange.suggested_start} — {bioRange.suggested_end}). Los días sin cobertura generarán
                  ausencias para todos los docentes con biométrico.
                </AlertDescription>
              </Alert>
            )}
          </section>

          {/* Discount Mode Selector */}
          <section className="space-y-3 border-t pt-5">
            <h3 id="discount-mode-label" className="text-sm font-semibold text-foreground">Modo de cálculo</h3>
            <div role="radiogroup" aria-labelledby="discount-mode-label" className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {(['attendance', 'full'] as const).map((option) => {
                const selected = effectiveDiscountMode === option
                return (
                  <button
                    key={option}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => { setDiscountModeManuallySet(true); setDiscountMode(option) }}
                    className={cn(
                      'rounded-xl border px-4 py-3 text-left text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring',
                      selected
                        ? 'border-primary bg-primary text-primary-foreground shadow-xs'
                        : 'border-input bg-background text-foreground hover:bg-accent/50',
                    )}
                  >
                    {DISCOUNT_MODE_LABELS[option]}
                  </button>
                )
              })}
            </div>
            <p className="text-xs text-muted-foreground">
              {effectiveDiscountMode === 'attendance'
                ? 'Se aplican descuentos por ausencias registradas en el biométrico'
                : effectiveDiscountMode === 'full'
                  ? 'Todos los docentes cobran el 100% de sus horas asignadas (sin descuentos)'
                  : 'Elegí el modo de cálculo para este período.'}
            </p>
            {effectiveDiscountMode === 'full' && (
              <Alert variant="warning">
                <AlertTriangle />
                <AlertDescription>
                  <strong>Atención:</strong> En este modo no se aplicarán descuentos por ausencias.
                  Todos los docentes recibirán el monto total correspondiente a sus horas asignadas.
                </AlertDescription>
              </Alert>
            )}
          </section>

          {/* Exclusion Days Section */}
          <section className="border-t pt-5">
            <button
              type="button"
              onClick={() => setExclusionPanelOpen(prev => !prev)}
              aria-expanded={exclusionPanelOpen}
              className="flex w-full items-center justify-between gap-3 rounded-lg text-left outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="flex items-center gap-3">
                <span className={cn('flex size-9 shrink-0 items-center justify-center rounded-lg', TONE_CHIP.neutral)}>
                  <CalendarOff className="size-4" aria-hidden="true" />
                </span>
                <span>
                  <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    Días excluidos del cálculo
                    {excludedDays.length > 0 && <StatusBadge tone="primary" className="tabular-nums">{excludedDays.length}</StatusBadge>}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {excludedDays.length === 0
                      ? 'Sin exclusiones — todos los días se calculan normalmente'
                      : `${excludedDays.length} día(s) excluido(s) de la planilla`}
                  </span>
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-1 text-xs font-medium text-muted-foreground">
                {exclusionPanelOpen ? 'Cerrar' : 'Abrir'}
                {exclusionPanelOpen ? <ChevronUp className="size-4" aria-hidden="true" /> : <ChevronDown className="size-4" aria-hidden="true" />}
              </span>
            </button>

            {exclusionPanelOpen && (
              <div className="mt-4 space-y-4">
                {/* Add exclusion form */}
                <form
                  onSubmit={(e) => { e.preventDefault(); addExclusionRow() }}
                  className="space-y-3 rounded-xl border border-dashed p-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-foreground">Agregar exclusión</p>
                      <p className="text-xs text-muted-foreground">Completá los datos y confirmá para enviarla a la lista.</p>
                    </div>
                    <Button type="submit" size="sm" disabled={!canAddExclusion}>
                      <Plus />
                      Agregar
                    </Button>
                  </div>

                  <div className="flex flex-wrap items-start gap-3">
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="exclusion-date">Fecha <span aria-hidden="true" className={TONE_TEXT.destructive}>*</span></Label>
                      <Input
                        id="exclusion-date"
                        type="date"
                        value={newExclusion.date}
                        onChange={e => updateNewExclusion({ date: e.target.value })}
                        className="w-44"
                        inputClassName="tabular-nums"
                        required
                      />
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="exclusion-scope">Alcance</Label>
                      <Select
                        value={newExclusion.scope}
                        items={SCOPE_ITEMS}
                        onValueChange={(value) => updateNewExclusion({ scope: value as ExcludedDay['scope'] })}
                      >
                        <SelectTrigger id="exclusion-scope" className="min-w-36"><SelectValue /></SelectTrigger>
                        <SelectPopup>
                          {SCOPE_ITEMS.map(({ value, label }) => (
                            <SelectItem key={value} value={value}>{label}</SelectItem>
                          ))}
                        </SelectPopup>
                      </Select>
                    </div>

                    {newExclusion.scope === 'semester' && (
                      <div className="min-w-[220px] max-w-sm flex-1 flex flex-col gap-1.5">
                        <Label>Semestres <span aria-hidden="true" className={TONE_TEXT.destructive}>*</span></Label>
                        <div className="max-h-44 space-y-1 overflow-y-auto rounded-lg border bg-muted/40 p-2">
                          {designationOptionsLoading ? (
                            <Skeleton className="h-6 w-full" />
                          ) : designationOptions.semesters.length === 0 ? (
                            <p className="px-1 py-1 text-xs text-muted-foreground">No hay semestres cargados para el período activo.</p>
                          ) : (
                            designationOptions.semesters.map((semester) => {
                              const selectedSemesters = newExclusion.selectedSemesters ?? []
                              const checked = selectedSemesters.includes(semester)

                              return (
                                <label key={semester} className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm text-foreground hover:bg-accent/50">
                                  <Checkbox
                                    checked={checked}
                                    onCheckedChange={(next) => {
                                      updateNewExclusion({
                                        selectedSemesters: next
                                          ? [...selectedSemesters, semester]
                                          : selectedSemesters.filter(selected => selected !== semester),
                                      })
                                    }}
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
                      <div className="min-w-[260px] max-w-xl flex-1 flex flex-col gap-1.5">
                        <Label>Materias y grupos <span aria-hidden="true" className={TONE_TEXT.destructive}>*</span></Label>
                        <div className="max-h-44 space-y-2 overflow-y-auto rounded-lg border bg-muted/40 p-2">
                          {designationOptionsLoading ? (
                            <Skeleton className="h-6 w-full" />
                          ) : designationOptions.subjects.length === 0 ? (
                            <p className="px-1 py-1 text-xs text-muted-foreground">No hay materias cargadas para el período activo.</p>
                          ) : (
                            getUniqueSubjects(designationOptions.subjects).map((subject) => {
                              const selectedSubjects = newExclusion.selectedSubjects ?? []
                              const subjectChecked = selectedSubjects.includes(subject)
                              const groups = getGroupsForSubject(designationOptions.subjects, subject)

                              return (
                                <div key={subject} className="rounded-md px-2 py-1.5">
                                  <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-foreground">
                                    <Checkbox
                                      checked={subjectChecked}
                                      onCheckedChange={(next) => {
                                        const currentSelections = newExclusion.subjectSelections ?? []
                                        updateNewExclusion({
                                          selectedSubjects: next
                                            ? [...selectedSubjects, subject]
                                            : selectedSubjects.filter(selected => selected !== subject),
                                          subjectSelections: next
                                            ? currentSelections
                                            : currentSelections.filter(selection => selection.subject !== subject),
                                        })
                                      }}
                                    />
                                    <span>{subject}</span>
                                  </label>

                                  {subjectChecked && (
                                    <div className="ml-6 mt-1.5 grid grid-cols-2 gap-1">
                                      {groups.map((option) => {
                                        const optionKey = getSubjectOptionKey(option)
                                        const checked = (newExclusion.subjectSelections ?? []).some(selection => getSubjectOptionKey(selection) === optionKey)

                                        return (
                                          <label key={optionKey} className="flex cursor-pointer items-center gap-1.5 rounded px-1.5 py-0.5 text-xs text-muted-foreground hover:bg-accent/50">
                                            <Checkbox
                                              checked={checked}
                                              onCheckedChange={(next) => {
                                                const current = newExclusion.subjectSelections ?? []
                                                updateNewExclusion({
                                                  subjectSelections: next
                                                    ? [...current, option]
                                                    : current.filter(selection => getSubjectOptionKey(selection) !== optionKey),
                                                })
                                              }}
                                            />
                                            <span>{option.group_code} · Sem. {option.semester}</span>
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

                    <div className="min-w-[180px] flex-1 flex flex-col gap-1.5">
                      <Label htmlFor="exclusion-reason">Motivo <span className="font-normal text-muted-foreground">(opcional)</span></Label>
                      <Input
                        id="exclusion-reason"
                        type="text"
                        value={newExclusion.reason ?? ''}
                        onChange={e => updateNewExclusion({ reason: e.target.value || undefined })}
                        placeholder="ej: Feriado institucional"
                      />
                    </div>
                  </div>
                </form>

                {/* Confirmed exclusion list */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-foreground">Exclusiones configuradas</p>
                    <span className="text-xs tabular-nums text-muted-foreground">{excludedDays.length} confirmada(s)</span>
                  </div>

                  {excludedDays.length === 0 ? (
                    <p className="rounded-lg border py-4 text-center text-xs text-muted-foreground">
                      No hay exclusiones configuradas
                    </p>
                  ) : (
                    <div className="divide-y overflow-hidden rounded-lg border">
                      {excludedDays.map((row, index) => (
                        <div key={index} className="grid grid-cols-1 gap-3 px-3 py-3 text-sm md:grid-cols-[110px_120px_1fr_1fr_36px]">
                          <div>
                            <p className="text-xs font-medium text-muted-foreground">Fecha</p>
                            <p className="font-medium tabular-nums text-foreground">{formatDate(row.date)}</p>
                          </div>
                          <div>
                            <p className="mb-0.5 text-xs font-medium text-muted-foreground">Alcance</p>
                            <StatusBadge tone={row.scope === 'global' ? 'primary' : row.scope === 'semester' ? 'info' : 'warning'}>
                              {row.scope === 'global' ? 'Global' : row.scope === 'semester' ? 'Semestre' : 'Materia'}
                            </StatusBadge>
                          </div>
                          <div>
                            <p className="mb-0.5 text-xs font-medium text-muted-foreground">Detalle</p>
                            {row.scope === 'global' && <p className="text-muted-foreground">Todos los docentes</p>}
                            {row.scope === 'semester' && (
                              <div className="flex flex-wrap gap-1">
                                {(row.selectedSemesters ?? (row.semester_id ? [row.semester_id] : [])).map((semester) => (
                                  <Badge key={semester} variant="info">{semester}</Badge>
                                ))}
                              </div>
                            )}
                            {row.scope === 'subject' && (
                              <div className="flex flex-wrap gap-1">
                                {(row.subjectSelections ?? []).map((selection) => (
                                  <Badge key={getSubjectOptionKey(selection)} variant="warning">
                                    {selection.subject} ({selection.group_code}, Sem. {selection.semester || 'legacy'})
                                  </Badge>
                                ))}
                              </div>
                            )}
                          </div>
                          <div>
                            <p className="text-xs font-medium text-muted-foreground">Motivo</p>
                            <p className="text-foreground">{row.reason || 'Sin motivo'}</p>
                          </div>
                          <div className="flex items-start md:justify-end">
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon-sm"
                              onClick={() => removeExclusionRow(index)}
                              title="Quitar exclusión"
                              aria-label="Quitar exclusión"
                            >
                              <Trash2 />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <Alert variant="info">
                  <Info />
                  <AlertDescription>
                    <strong>Global</strong>: excluye el día para todos los docentes. <strong>Por semestre</strong>: solo el semestre indicado. <strong>Por materia</strong>: solo la materia y grupo exactos. Las celdas excluidas aparecen en rojo en el Excel.
                  </AlertDescription>
                </Alert>
              </div>
            )}
          </section>

          {generatePlanilla.isError && (
            <Alert variant="error">
              <AlertCircle />
              <AlertDescription>
                Error al generar la planilla. Verificá que la asistencia esté procesada para el período seleccionado.
              </AlertDescription>
            </Alert>
          )}
        </CardPanel>
      </Card>

      {/* Result Card */}
      {lastResult && (
        <Alert variant="success" className="items-center">
          <CheckCircle />
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-1">
              <AlertTitle>¡Planilla generada exitosamente!</AlertTitle>
              <AlertDescription>
                <p className="tabular-nums">
                  {MONTH_NAMES[lastResult.month]} {lastResult.year} · {lastResult.total_teachers} docentes · {formatHours(lastResult.total_hours)} totales
                </p>
                <p className="mt-1 text-lg font-semibold tabular-nums text-foreground">
                  Total: Bs {parseFloat(lastResult.total_payment).toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
                {lastResult.warnings.length > 0 && (
                  <p className={cn('text-xs', TONE_TEXT.warning)}>
                    {lastResult.warnings.length} advertencia(s) durante la generación
                  </p>
                )}
              </AlertDescription>
            </div>
            {lastResult.file_path && (
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  onClick={() => void downloadPlanilla(lastResult.planilla_id, `planilla_${MONTH_NAMES[lastResult.month]}_${lastResult.year}.xlsx`)}
                >
                  <Download />
                  Descargar Excel
                </Button>
                <Button
                  variant="secondary"
                  loading={salaryReportLoading.current}
                  disabled={salaryReportLoading.current}
                  onClick={async () => {
                    setSalaryReportLoading((prev) => ({ ...prev, current: true }))
                    try {
                      await downloadSalaryReport({
                        month: lastResult.month,
                        year: lastResult.year,
                        discount_mode: effectiveDiscountMode ?? lastResult.discount_mode,
                        start_date: optionalDate(startDate),
                        end_date: optionalDate(endDate),
                      })
                    } finally {
                      setSalaryReportLoading((prev) => ({ ...prev, current: false }))
                    }
                  }}
                >
                  <FileSpreadsheet />
                  Planilla Salarios
                </Button>
              </div>
            )}
          </div>
        </Alert>
      )}

      {/* History */}
      {historyLoading ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Historial de Planillas</CardTitle>
            <CardDescription>Cargando...</CardDescription>
          </CardHeader>
          <CardPanel className="space-y-2" role="status" aria-label="Cargando historial">
            {[0, 1, 2, 3].map((n) => <Skeleton key={n} className="h-8 w-full" />)}
          </CardPanel>
        </Card>
      ) : !history || history.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Historial de Planillas</CardTitle>
            <CardDescription>0 planilla(s) generada(s)</CardDescription>
          </CardHeader>
          <EmptyState icon={History} title="No hay planillas generadas aún" />
        </Card>
      ) : (
        <TableCard
          title="Historial de Planillas"
          description={`${history.length} planilla(s) generada(s)`}
        >
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Período</TableHead>
              <TableHead>Corte</TableHead>
              <TableHead>Generada el</TableHead>
              <TableHead className="text-right">Docentes</TableHead>
              <TableHead className="text-right">Horas</TableHead>
              <TableHead className="text-right">Total (Bs)</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Descarga</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {history.map((item) => {
              const paymentState = getHistoricalPaymentState(item)
              const itemStatus = item.status?.toLowerCase()
              return (
                <TableRow
                  key={item.id}
                  className="cursor-pointer"
                  tabIndex={0}
                  onClick={() => restoreFromHistory(item)}
                  onKeyDown={(e) => {
                    if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) {
                      e.preventDefault()
                      restoreFromHistory(item)
                    }
                  }}
                >
                  <TableCell>
                    <span className="inline-flex items-center gap-2 font-medium text-foreground">
                      <Calendar className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                      {MONTH_NAMES[item.month]} {item.year}
                    </span>
                  </TableCell>
                  <TableCell className="tabular-nums text-muted-foreground">
                    {item.start_date && item.end_date
                      ? `${formatShortDate(item.start_date)} — ${formatShortDate(item.end_date)}`
                      : '—'}
                  </TableCell>
                  <TableCell className="tabular-nums text-muted-foreground">{formatDate(item.generated_at)}</TableCell>
                  <TableCell className="text-right tabular-nums">{item.total_teachers}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatHours(item.total_hours)}</TableCell>
                  <TableCell className="text-right font-semibold tabular-nums text-foreground">{paymentState.display}</TableCell>
                  <TableCell>
                    <StatusBadge tone={itemStatus === 'approved' ? 'success' : itemStatus === 'rejected' ? 'destructive' : 'warning'}>
                      {itemStatus === 'approved' ? 'Aprobada' : itemStatus === 'rejected' ? 'Rechazada' : 'Pend. Aprobación'}
                    </StatusBadge>
                  </TableCell>
                  <TableCell>
                    {paymentState.snapshotAvailable && item.file_path ? (
                      <div className="flex items-center gap-1.5">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation()
                            void downloadPlanilla(item.id, `planilla_${MONTH_NAMES[item.month]}_${item.year}.xlsx`)
                          }}
                        >
                          <Download />
                          Excel
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          loading={salaryReportLoading[`row-${item.id}`]}
                          disabled={salaryReportLoading[`row-${item.id}`]}
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
                        >
                          <FileSpreadsheet />
                          Salarios
                        </Button>
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">No disponible</span>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </TableCard>
      )}

      {/* Approval Status — show when there is a planilla for this period */}
      {selectedHistoryState && !selectedHistoryState.snapshotAvailable && (
        <Alert variant="warning">
          <AlertTriangle />
          <AlertDescription>
            Regeneración requerida: el historial legacy no permite aprobar, publicar, exportar ni abrir el detalle.
          </AlertDescription>
        </Alert>
      )}

      {planillaStatus && (
        <Card>
          <CardHeader>
            <CardTitle className="col-start-1 text-base">Estado de la Planilla</CardTitle>
            <CardDescription className="col-start-1">
              {planillaStatus.status === 'approved'
                ? 'Aprobada — lista para publicar'
                : planillaStatus.status === 'rejected'
                  ? 'Rechazada — requiere regeneración'
                  : 'Pendiente de aprobación'}
            </CardDescription>
            <CardAction className={HEADER_ACTION}>
              {planillaStatus.status === 'generated' && (
                <>
                  <Button
                    size="sm"
                    onClick={() => requestConfirm('approve')}
                    disabled={approvePlanilla.isPending || !canUseSelectedSnapshot || detailError}
                    title={!canUseSelectedSnapshot ? 'Regeneración requerida antes de aprobar' : detailError ? 'No se pudo cargar el detalle de la planilla' : undefined}
                  >
                    <Check /> Aprobar
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive-outline"
                    onClick={() => requestConfirm('reject')}
                    disabled={rejectPlanilla.isPending}
                  >
                    <X /> Rechazar
                  </Button>
                </>
              )}
              {planillaStatus.status === 'approved' && <StatusBadge tone="success">Lista para publicar</StatusBadge>}
              {planillaStatus.status === 'rejected' && <StatusBadge tone="destructive">Regenerá la planilla</StatusBadge>}
            </CardAction>
          </CardHeader>
        </Card>
      )}

      {/* Publication Status — at the top so admin doesn't need to scroll */}
      <Card>
        <CardHeader>
          <CardTitle className="col-start-1 text-base">Publicación de Facturación</CardTitle>
          <CardDescription className="col-start-1">
            {MONTH_NAMES[month]} {year} — {
              publication?.status === 'published'
                ? `Publicado el ${new Date(publication.published_at!).toLocaleDateString('es-BO')}`
                : 'No publicado para docentes'
            }
          </CardDescription>
          <CardAction className={HEADER_ACTION}>
            {publication?.status === 'published' ? (
              <Button
                variant="destructive-outline"
                onClick={() => requestConfirm('unpublish')}
                disabled={unpublishBilling.isPending}
              >
                <EyeOff />
                {unpublishBilling.isPending ? 'Despublicando...' : 'Despublicar'}
              </Button>
            ) : (
              <Button
                onClick={() => requestConfirm('publish')}
                disabled={publishBilling.isPending || planillaStatus?.status !== 'approved' || exclusionsEdited || !canUseSelectedSnapshot || detailError}
                title={!canUseSelectedSnapshot ? 'Regeneración requerida antes de publicar' : detailError ? 'No se pudo cargar el detalle de la planilla' : exclusionsEdited ? 'Regenerá la planilla para aplicar los cambios de exclusiones antes de publicar' : planillaStatus?.status !== 'approved' ? 'La planilla debe estar aprobada antes de publicar' : undefined}
              >
                <Send />
                {publishBilling.isPending ? 'Publicando...' : 'Publicar para Docentes'}
              </Button>
            )}
          </CardAction>
        </CardHeader>

        {publicationNotices.length > 0 && (
          <CardPanel className="space-y-2">
            {publicationNotices.map(({ key, variant, content }) => (
              <Alert key={key} variant={variant}>
                {variant === 'success' ? <CheckCircle /> : <AlertTriangle />}
                <AlertDescription>{content}</AlertDescription>
              </Alert>
            ))}
          </CardPanel>
        )}
      </Card>

      {/* Planilla Detail Section — ALWAYS visible */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Detalle por Docente</CardTitle>
          <CardDescription>
            {detailError ? 'No se pudo cargar' : detail ? `${detail.total_teachers} docentes` : effectiveDiscountMode === null ? 'Sin vista previa' : 'Cargando...'} · {MONTH_NAMES[month]} {year}
          </CardDescription>
        </CardHeader>

        <CardPanel className="space-y-4">
          {detailLoading ? (
            <div className="space-y-4" role="status" aria-label="Cargando detalle">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                {[0, 1, 2].map((n) => <Skeleton key={n} className="h-20 rounded-2xl" />)}
              </div>
              <Skeleton className="h-40 w-full rounded-xl" />
            </div>
          ) : detailError ? (
            <Alert variant="error">
              <AlertCircle />
              <div className="flex flex-wrap items-center justify-between gap-3">
                <AlertDescription>No se pudo cargar el detalle de la planilla.</AlertDescription>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void detailQuery.refetch()}
                  disabled={detailQuery.isFetching}
                  loading={detailQuery.isFetching}
                >
                  Reintentar
                </Button>
              </div>
            </Alert>
          ) : detail ? (
            <div className="space-y-4">
              {/* Summary stats */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <StatCard icon={Users} title="Docentes" value={detail.total_teachers} />
                <StatCard icon={BookOpen} title="Designaciones" value={detail.total_designations} tone="info" />
                <StatCard icon={Wallet} title="Total a Pagar" value={`Bs ${detail.total_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })}`} tone="success" />
              </div>

              {/* Tabs + Search row */}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <Tabs value={detailTab} onValueChange={(value) => setDetailTab(value as 'designations' | 'teachers')}>
                  <TabsList>
                    <TabsTab value="teachers">Por Docente</TabsTab>
                    <TabsTab value="designations">Por Designación</TabsTab>
                  </TabsList>
                </Tabs>

                <div className="relative min-w-[200px] max-w-sm flex-1">
                  <Search aria-hidden="true" size={16} className="pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    type="search"
                    aria-label="Buscar docente por nombre o CI"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="Buscar docente por nombre o CI..."
                    inputClassName="pl-9"
                  />
                </div>
              </div>

              {/* Tab: Por Docente */}
              {detailTab === 'teachers' && (
                <div className="space-y-3">
                  {isBillingPublished && selectedTeachers.size > 0 && (
                    <Alert variant="info" className="items-center">
                      <Mail />
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <AlertTitle className="tabular-nums">{selectedTeachers.size} docente(s) seleccionado(s)</AlertTitle>
                          <AlertDescription>Seleccioná los docentes a quienes enviar el correo</AlertDescription>
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          <Button
                            type="button"
                            onClick={handlePreviewWhatsAppNotifications}
                            disabled={previewBillingNotifications.isPending || confirmBillingNotifications.isPending}
                            loading={previewBillingNotifications.isPending}
                          >
                            <MessageCircle />
                            Generar vista previa WhatsApp
                          </Button>
                          <Button
                            type="button"
                            onClick={handleSendSelectedBillingEmails}
                            disabled={sendBillingEmails.isPending}
                            loading={sendBillingEmails.isPending}
                          >
                            <Mail />
                            Enviar correo
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => setSelectedTeachers(new Set())}
                            disabled={sendBillingEmails.isPending}
                          >
                            Limpiar selección
                          </Button>
                        </div>
                      </div>
                    </Alert>
                  )}

                  {(whatsAppReadiness.data || whatsAppReadiness.isError) && (
                    <Alert variant={whatsAppReadiness.data?.ready ? 'success' : 'warning'}>
                      <MessageCircle />
                      <AlertDescription>
                        <strong>WhatsApp oficial:</strong>{' '}
                        {whatsAppReadiness.data?.ready
                          ? 'listo para una vista previa; la confirmación volverá a validar la capacidad.'
                          : 'no está listo para enviar. La confirmación queda bloqueada hasta que la verificación en vivo sea válida.'}
                      </AlertDescription>
                    </Alert>
                  )}

                  {whatsAppPreview && (
                    <Alert variant="success">
                      <MessageCircle />
                      <div className="space-y-3">
                        <div>
                          <AlertTitle>Vista previa de WhatsApp oficial</AlertTitle>
                          <AlertDescription>El resumen muestra solo teléfonos enmascarados. La confirmación usa este digest y se rechaza si cambia la preparación, la capacidad o el consentimiento.</AlertDescription>
                        </div>
                        <div className="grid gap-2 text-sm tabular-nums sm:grid-cols-3">
                          <span>WhatsApp: {whatsAppPreview.recipients.filter(item => item.channel === 'whatsapp').length}</span>
                          <span>Correo alternativo: {whatsAppPreview.recipients.filter(item => item.channel === 'email').length}</span>
                          <span>Bloqueados: {whatsAppPreview.recipients.filter(item => item.channel === 'blocked').length}</span>
                        </div>
                        <ul className="max-h-36 divide-y overflow-y-auto rounded-lg border bg-background px-3 text-xs text-muted-foreground">
                          {whatsAppPreview.recipients.map(item => (
                            <li key={item.teacher_ci} className="py-1.5 tabular-nums">{item.teacher_ci} · {item.phone_masked ?? 'sin número verificado'} · {item.channel}</li>
                          ))}
                        </ul>
                        {!hasSafeWhatsAppPreview && <p className={cn('text-sm font-medium', TONE_TEXT.warning)}>La preparación o la capacidad cambió/no está disponible. No podés confirmar este envío.</p>}
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            onClick={handleConfirmWhatsAppNotifications}
                            disabled={!hasSafeWhatsAppPreview || confirmBillingNotifications.isPending}
                            loading={confirmBillingNotifications.isPending}
                          >
                            <CheckCircle />
                            Confirmar envío
                          </Button>
                          <Button type="button" variant="outline" onClick={() => setWhatsAppPreview(null)} disabled={confirmBillingNotifications.isPending}>Cancelar</Button>
                        </div>
                      </div>
                    </Alert>
                  )}

                  {whatsAppError && (
                    <Alert variant="error">
                      <AlertCircle />
                      <AlertDescription>{whatsAppError}</AlertDescription>
                    </Alert>
                  )}

                  {whatsAppBatch.data && (
                    <Alert variant="info">
                      <Info />
                      <div className="space-y-2">
                        <AlertTitle>Estado durable de WhatsApp · lote #{whatsAppBatch.data.batch_id}</AlertTitle>
                        <AlertDescription>Estado: {whatsAppBatch.data.status}. {whatsAppBatch.data.jobs.length} intento(s) registrado(s).</AlertDescription>
                        <div className="flex flex-wrap gap-2 text-xs">
                          {Object.entries(whatsAppBatch.data.jobs.reduce<Record<string, number>>((counts, job) => {
                            const label = `${job.channel}: ${job.status}`
                            counts[label] = (counts[label] ?? 0) + 1
                            return counts
                          }, {})).map(([label, count]) => (
                            <StatusBadge key={label} tone="info" className="tabular-nums">{label} · {count}</StatusBadge>
                          ))}
                        </div>
                      </div>
                    </Alert>
                  )}

                  {/* Email send result banner */}
                  {emailSendResult && (
                    <Alert variant="success">
                      <CheckCircle />
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex flex-col gap-1.5">
                          <AlertTitle>Correos procesados exitosamente</AlertTitle>
                          <div className="flex flex-wrap gap-2">
                            {emailSendResult.sent > 0 && <StatusBadge tone="success" className="tabular-nums">{emailSendResult.sent} enviado(s)</StatusBadge>}
                            {emailSendResult.failed > 0 && <StatusBadge tone="destructive" className="tabular-nums">{emailSendResult.failed} fallido(s)</StatusBadge>}
                            {emailSendResult.skipped > 0 && <StatusBadge tone="neutral" className="tabular-nums">{emailSendResult.skipped} omitido(s)</StatusBadge>}
                          </div>
                        </div>
                        <Button variant="ghost" size="icon-xs" aria-label="Cerrar resultado de correos" onClick={() => setEmailSendResult(null)}>
                          <X />
                        </Button>
                      </div>
                    </Alert>
                  )}
                  {emailSendError && (
                    <Alert variant="error">
                      <AlertCircle />
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <AlertTitle>No se pudieron enviar los correos</AlertTitle>
                          <AlertDescription>Verificá la configuración de email e intentá nuevamente.</AlertDescription>
                        </div>
                        <Button variant="ghost" size="icon-xs" aria-label="Cerrar error de correos" onClick={() => setEmailSendError(false)}>
                          <X />
                        </Button>
                      </div>
                    </Alert>
                  )}

                  {visibleTeacherTotals.length === 0 ? (
                    <EmptyState
                      icon={Search}
                      title="Sin docentes para mostrar"
                      description={searchTerm ? 'Ningún docente coincide con la búsqueda.' : 'La planilla no tiene docentes.'}
                    />
                  ) : (
                    <TableCard
                      toolbar={isBillingPublished ? (
                        <>
                          <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-foreground">
                            <Checkbox
                              checked={allVisibleTeachersSelected}
                              onCheckedChange={toggleAllVisibleTeachers}
                              disabled={visibleTeacherTotals.length === 0}
                            />
                            Seleccionar todos
                          </label>
                          <StatusBadge tone="primary" className="tabular-nums">{selectedTeachers.size} seleccionado(s)</StatusBadge>
                        </>
                      ) : undefined}
                    >
                      <TableHeader>
                        <TableRow className="hover:bg-transparent">
                          <TableHead>Docente / Materia</TableHead>
                          <TableHead>Grupo</TableHead>
                          <TableHead>Sem.</TableHead>
                          <TableHead className="text-right">Hrs base</TableHead>
                          <TableHead className="text-right">Ausencias</TableHead>
                          <TableHead className="text-right">Hrs a pagar</TableHead>
                          <TableHead className="text-right">Monto (Bs)</TableHead>
                        </TableRow>
                      </TableHeader>
                      {visibleTeacherTotals.map(teacher => (
                        <TableBody key={teacher.teacher_ci}>
                          {/* Teacher header row */}
                          <TableRow className="bg-muted/40 hover:bg-muted/40">
                            <TableCell>
                              <div className="flex items-center gap-3">
                                {isBillingPublished && (
                                  <Checkbox
                                    checked={selectedTeachers.has(teacher.teacher_ci)}
                                    onCheckedChange={() => toggleTeacherSelection(teacher.teacher_ci)}
                                    aria-label={`Seleccionar ${teacher.teacher_name}`}
                                  />
                                )}
                                <div>
                                  <p className="font-medium text-foreground">{teacher.teacher_name}</p>
                                  <p className="text-xs tabular-nums text-muted-foreground">CI: {teacher.teacher_ci} · {teacher.designation_count} materia(s)</p>
                                </div>
                              </div>
                            </TableCell>
                            <TableCell colSpan={2}>
                              {!teacher.has_biometric && <StatusBadge tone="warning">Sin Bio</StatusBadge>}
                            </TableCell>
                            <TableCell className="text-right tabular-nums text-muted-foreground">{teacher.total_base_hours}h</TableCell>
                            <TableCell />
                            <TableCell className="text-right font-medium tabular-nums text-foreground">{teacher.total_payable_hours}h</TableCell>
                            <TableCell className="text-right">
                              {editingOverride === teacher.teacher_ci ? (
                                <div className="flex items-center justify-end gap-1.5">
                                  <span className="text-xs text-muted-foreground">Bs</span>
                                  <Input
                                    type="number"
                                    aria-label={`Ajustar monto de ${teacher.teacher_name}`}
                                    value={overrideValue}
                                    onChange={e => setOverrideValue(e.target.value)}
                                    className="w-28"
                                    inputClassName="text-right tabular-nums"
                                    size="sm"
                                    autoFocus
                                  />
                                  <Button
                                    variant="ghost"
                                    size="icon-xs"
                                    title="Confirmar ajuste"
                                    aria-label="Confirmar ajuste"
                                    onClick={() => {
                                      if (overrideValue) {
                                        setPaymentOverrides(prev => ({ ...prev, [teacher.teacher_ci]: Number(overrideValue) }))
                                      }
                                      setEditingOverride(null)
                                      setOverrideValue('')
                                    }}
                                  >
                                    <Check />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon-xs"
                                    title="Cancelar"
                                    aria-label="Cancelar ajuste"
                                    onClick={() => { setEditingOverride(null); setOverrideValue('') }}
                                  >
                                    <X />
                                  </Button>
                                </div>
                              ) : (
                                <div className="flex flex-col items-end gap-0.5">
                                  {teacher.has_retention && (
                                    <>
                                      <p className="text-xs tabular-nums text-muted-foreground line-through">
                                        Bruto: Bs {teacher.total_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                                      </p>
                                      <p className={cn('text-xs tabular-nums', TONE_TEXT.destructive)}>
                                        Retención 13%: -Bs {(teacher.retention_amount ?? 0).toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                                      </p>
                                    </>
                                  )}
                                  <div className="flex items-center gap-1.5">
                                    <p
                                      className={cn(
                                        'text-base font-semibold tabular-nums',
                                        paymentOverrides[teacher.teacher_ci] != null ? cn('line-through', TONE_TEXT.destructive) : 'text-foreground',
                                      )}
                                    >
                                      {teacher.has_retention ? 'Neto: ' : ''}Bs {(teacher.has_retention ? (teacher.final_payment ?? teacher.total_payment) : teacher.total_payment).toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                                    </p>
                                    {paymentOverrides[teacher.teacher_ci] != null && (
                                      <p className={cn('text-base font-semibold tabular-nums', TONE_TEXT.success)}>
                                        Bs {paymentOverrides[teacher.teacher_ci].toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                                      </p>
                                    )}
                                    <Button
                                      variant="ghost"
                                      size="icon-xs"
                                      title="Ajustar monto"
                                      aria-label={`Ajustar monto de ${teacher.teacher_name}`}
                                      onClick={() => {
                                        setEditingOverride(teacher.teacher_ci)
                                        setOverrideValue(String(paymentOverrides[teacher.teacher_ci] ?? (teacher.has_retention ? (teacher.final_payment ?? teacher.total_payment) : teacher.total_payment)))
                                      }}
                                    >
                                      <Pencil />
                                    </Button>
                                    {paymentOverrides[teacher.teacher_ci] != null && (
                                      <Button
                                        variant="ghost"
                                        size="icon-xs"
                                        title="Quitar ajuste"
                                        aria-label={`Quitar ajuste de ${teacher.teacher_name}`}
                                        onClick={() => {
                                          setPaymentOverrides(prev => {
                                            const next = { ...prev }
                                            delete next[teacher.teacher_ci]
                                            return next
                                          })
                                        }}
                                      >
                                        <X />
                                      </Button>
                                    )}
                                  </div>
                                </div>
                              )}
                            </TableCell>
                          </TableRow>

                          {/* Teacher designations */}
                          {detail.detail
                            .filter(d => d.teacher_ci === teacher.teacher_ci)
                            .map(d => (
                              <TableRow key={`${d.subject}-${d.group_code}`}>
                                <TableCell className="max-w-[260px] truncate pl-8 text-foreground">{d.subject}</TableCell>
                                <TableCell><Badge variant="outline">{d.group_code}</Badge></TableCell>
                                <TableCell className="text-muted-foreground">{d.semester}</TableCell>
                                <TableCell className="text-right tabular-nums text-muted-foreground">{d.base_monthly_hours}h</TableCell>
                                <TableCell className={cn('text-right tabular-nums', d.absent_hours > 0 ? TONE_TEXT.destructive : 'text-muted-foreground')}>
                                  {d.absent_hours > 0 ? `-${d.absent_hours}h` : '0h'}
                                </TableCell>
                                <TableCell className="text-right font-medium tabular-nums text-foreground">{d.payable_hours}h</TableCell>
                                {planillaRowNote(d) ? (
                                  <TableCell className="text-right text-muted-foreground">{planillaRowNote(d)}</TableCell>
                                ) : (
                                  <TableCell className="text-right font-medium tabular-nums text-foreground">
                                    Bs {(d.final_payment ?? d.calculated_payment).toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                                    {(d.retention_amount ?? 0) > 0 && <span className={cn('ml-1 text-xs', TONE_TEXT.destructive)}>(con retención)</span>}
                                  </TableCell>
                                )}
                              </TableRow>
                            ))}
                        </TableBody>
                      ))}
                    </TableCard>
                  )}
                </div>
              )}

              {/* Tab: Por Designación */}
              {detailTab === 'designations' && (
                <TableCard>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent">
                      {['Docente', 'Materia', 'Grupo', 'Sem.'].map(h => <TableHead key={h}>{h}</TableHead>)}
                      {['Hrs Base', 'Ausencias', 'Hrs a Pagar', 'Monto (Bs)'].map(h => <TableHead key={h} className="text-right">{h}</TableHead>)}
                      <TableHead>Estado</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {detail.detail
                      .filter(row => {
                        if (!searchTerm) return true
                        const term = searchTerm.toLowerCase()
                        return row.teacher_name.toLowerCase().includes(term) || row.teacher_ci.includes(term)
                      })
                      .map((row) => (
                        <TableRow key={`${row.teacher_ci}-${row.subject}-${row.group_code}`}>
                          <TableCell className="max-w-[200px] truncate font-medium text-foreground">{row.teacher_name}</TableCell>
                          <TableCell className="max-w-[180px] truncate">{row.subject}</TableCell>
                          <TableCell className="text-muted-foreground">{row.group_code}</TableCell>
                          <TableCell className="text-muted-foreground">{row.semester}</TableCell>
                          <TableCell className="text-right tabular-nums">{row.base_monthly_hours}h</TableCell>
                          <TableCell className={cn('text-right tabular-nums', row.absent_hours > 0 ? cn('font-medium', TONE_TEXT.destructive) : 'text-muted-foreground')}>
                            {row.absent_hours > 0 ? `-${row.absent_hours}h` : '0h'}
                          </TableCell>
                          <TableCell className="text-right font-semibold tabular-nums text-foreground">{row.payable_hours}h</TableCell>
                          {planillaRowNote(row) ? (
                            <TableCell className="text-right text-muted-foreground">{planillaRowNote(row)}</TableCell>
                          ) : (
                            <TableCell className="text-right font-semibold tabular-nums text-foreground">
                              {(row.final_payment ?? row.calculated_payment).toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                              {(row.retention_amount ?? 0) > 0 && <span className={cn('ml-1 text-xs font-medium', TONE_TEXT.destructive)}>(con retención)</span>}
                            </TableCell>
                          )}
                          <TableCell>
                            {!row.has_biometric ? (
                              <StatusBadge tone="warning">Sin Bio</StatusBadge>
                            ) : row.absent_count > 0 ? (
                              <StatusBadge tone="destructive">{row.absent_count} falta(s)</StatusBadge>
                            ) : (
                              <StatusBadge tone="success">Completo</StatusBadge>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </TableCard>
              )}
            </div>
          ) : effectiveDiscountMode === null ? (
            <EmptyState
              icon={Calculator}
              title="Elegí el modo de cálculo para ver la vista previa."
            />
          ) : (
            <EmptyState
              icon={FileSpreadsheet}
              title={`No hay datos para ${MONTH_NAMES[month]} ${year}.`}
              description="Generá la planilla para ver el detalle."
            />
          )}
        </CardPanel>
      </Card>

      </div>
      )}

      <ConfirmActionDialog
        summary={confirmSummary}
        onConfirm={runConfirmedAction}
        onCancel={() => setPendingConfirm(null)}
      />
    </div>
  )
}
