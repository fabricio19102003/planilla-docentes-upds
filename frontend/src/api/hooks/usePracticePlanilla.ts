import { useEffect, useState } from 'react'
import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type { ExcludedDay } from '@/api/types'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface PracticePlanillaOutput {
  id: number
  month: number
  year: number
  generated_at: string
  file_path: string | null
  total_teachers: number
  total_hours: number
  total_payment: string
  status: string
  discount_mode: 'attendance' | 'full'
  start_date: string | null
  end_date: string | null
  payment_overrides_json?: Record<string, number> | null
  excluded_days_json?: ExcludedDay[] | null
}

export interface PracticeDesignationOption {
  subject: string
  group_code: string
  semester: string
}

export interface PracticeDesignationOptions {
  subjects: PracticeDesignationOption[]
  semesters: string[]
  groups: string[]
}

export interface PracticePublicationStatus {
  id: number
  month: number
  year: number
  status: 'published' | 'draft'
  total_teachers: number
  total_payment: number
  published_by: number | null
  published_at: string | null
  unpublished_at: string | null
  notes: string | null
  planilla_type: string
}

export interface PracticePlanillaGenerateResponse {
  planilla_id: number
  month: number
  year: number
  file_path: string | null
  total_teachers: number
  total_hours: number
  total_payment: string
  warnings: string[]
  discount_mode: string
}

export interface PracticePlanillaDetailRow {
  teacher_ci: string
  teacher_name: string
  subject: string
  group_code: string
  semester: string
  base_monthly_hours: number
  absent_hours: number
  payable_hours: number
  rate_per_hour: number
  calculated_payment: number
  retention_rate: number
  retention_amount: number
  final_payment: number
  has_retention: boolean
  observation: string
}

export interface PracticePlanillaDetailResponse {
  month: number
  year: number
  rows: PracticePlanillaDetailRow[]
  total_gross: number
  total_retention: number
  total_net: number
  total_teachers: number
  warnings: string[]
}

// ─── Generate ─────────────────────────────────────────────────────────────────

export function useGeneratePracticePlanilla() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (params: {
      month: number
      year: number
      payment_overrides?: Record<string, number>
      start_date?: string
      end_date?: string
      discount_mode?: string
      excluded_days?: ExcludedDay[]
    }) => {
      const res = await api.post<PracticePlanillaGenerateResponse>(
        '/practice-planilla/generate',
        params,
      )
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['practice-planilla'] })
      void qc.invalidateQueries({ queryKey: ['practice-planilla-history'] })
    },
  })
}

// ─── History ──────────────────────────────────────────────────────────────────

export function usePracticePlanillaHistory() {
  return useQuery<PracticePlanillaOutput[]>({
    queryKey: ['practice-planilla-history'],
    queryFn: async () => {
      const res = await api.get<PracticePlanillaOutput[]>('/practice-planilla/history')
      return res.data
    },
  })
}

// ─── Detail ───────────────────────────────────────────────────────────────────

export function usePracticePlanillaDetail(
  month: number,
  year: number,
  enabled: boolean = true,
  startDate?: string,
  endDate?: string,
  discountMode?: string,
) {
  return useQuery<PracticePlanillaDetailResponse>({
    queryKey: ['practice-planilla-detail', month, year, startDate, endDate, discountMode],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (startDate) params.set('start_date', startDate)
      if (endDate) params.set('end_date', endDate)
      if (discountMode) params.set('discount_mode', discountMode)
      const qs = params.toString()
      const res = await api.get<PracticePlanillaDetailResponse>(
        `/practice-planilla/${month}/${year}/detail${qs ? '?' + qs : ''}`,
      )
      return res.data
    },
    enabled,
  })
}

// ─── Download ─────────────────────────────────────────────────────────────────

export async function downloadPracticePlanilla(planillaId: number) {
  const response = await api.get(`/practice-planilla/${planillaId}/download`, {
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url
  link.download = `planilla_practicas_${planillaId}.xlsx`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

// ─── Salary Report ────────────────────────────────────────────────────────────

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

export async function downloadPracticeSalaryReport(params: {
  month: number
  year: number
  discount_mode?: string
  start_date?: string
  end_date?: string
}) {
  const response = await api.post('/practice-planilla/salary-report', params, {
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url
  link.download = `Planilla_Salario_Practicas_${MONTH_NAMES[params.month]}_${params.year}.xlsx`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

// ─── Status ───────────────────────────────────────────────────────────────────

export function usePracticePlanillaStatus(month: number, year: number) {
  return useQuery({
    queryKey: ['practice-planilla-status', month, year],
    queryFn: async () => {
      const res = await api.get<PracticePlanillaOutput[]>('/practice-planilla/history')
      const match = res.data.find((p) => p.month === month && p.year === year)
      return match ?? null
    },
  })
}

// ─── Approve / Reject ─────────────────────────────────────────────────────────

export function useApprovePracticePlanilla() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (planillaId: number) => {
      const res = await api.post(`/practice-planilla/${planillaId}/approve`)
      return res.data as { success: boolean; status: string; planilla_id: number }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['practice-planilla'] })
      void qc.invalidateQueries({ queryKey: ['practice-planilla-history'] })
      void qc.invalidateQueries({ queryKey: ['practice-planilla-status'] })
    },
  })
}

export function useRejectPracticePlanilla() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (planillaId: number) => {
      const res = await api.post(`/practice-planilla/${planillaId}/reject`)
      return res.data as { success: boolean; status: string; planilla_id: number }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['practice-planilla'] })
      void qc.invalidateQueries({ queryKey: ['practice-planilla-history'] })
      void qc.invalidateQueries({ queryKey: ['practice-planilla-status'] })
    },
  })
}

// ─── Detail with excluded days debounce ───────────────────────────────────────

export function usePracticePlanillaDetailWithExclusions(
  month: number,
  year: number,
  enabled: boolean = true,
  startDate?: string,
  endDate?: string,
  discountMode?: string,
  excludedDays?: ExcludedDay[],
) {
  const excludedDaysJson = excludedDays ? JSON.stringify(excludedDays) : undefined
  const [debouncedParams, setDebouncedParams] = useState({
    startDate,
    endDate,
    discountMode,
    excludedDaysJson,
  })

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebouncedParams({ startDate, endDate, discountMode, excludedDaysJson })
    }, 300)
    return () => window.clearTimeout(timeout)
  }, [startDate, endDate, discountMode, excludedDaysJson])

  return useQuery<PracticePlanillaDetailResponse>({
    queryKey: ['practice-planilla-detail', month, year, debouncedParams.startDate, debouncedParams.endDate, debouncedParams.discountMode, debouncedParams.excludedDaysJson],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (debouncedParams.startDate) params.set('start_date', debouncedParams.startDate)
      if (debouncedParams.endDate) params.set('end_date', debouncedParams.endDate)
      if (debouncedParams.discountMode) params.set('discount_mode', debouncedParams.discountMode)
      if (debouncedParams.excludedDaysJson !== undefined) params.set('excluded_days_json', debouncedParams.excludedDaysJson)
      const qs = params.toString()
      const res = await api.get<PracticePlanillaDetailResponse>(
        `/practice-planilla/${month}/${year}/detail${qs ? '?' + qs : ''}`,
      )
      return res.data
    },
    enabled,
    placeholderData: keepPreviousData,
  })
}

// ─── Practice Publication ─────────────────────────────────────────────────────

export function usePracticePublicationStatus(month: number, year: number) {
  return useQuery({
    queryKey: ['practice-billing-publication', month, year],
    queryFn: async () => {
      try {
        const res = await api.get<PracticePublicationStatus>(`/billing/publication/${month}/${year}?planilla_type=practice`)
        return res.data
      } catch (e: unknown) {
        const status = (e as { response?: { status?: number } })?.response?.status
        if (status === 404) return null
        throw e
      }
    },
  })
}

export function usePublishPracticeBilling() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: { month: number; year: number; notes?: string }) => {
      const res = await api.post<PracticePublicationStatus>('/billing/practice/publish', data)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['practice-billing-publication'] })
      void qc.invalidateQueries({ queryKey: ['practice-planilla-status'] })
      void qc.invalidateQueries({ queryKey: ['practice-planilla-history'] })
    },
  })
}

export function useUnpublishPracticeBilling() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: { month: number; year: number }) => {
      const res = await api.post<PracticePublicationStatus>('/billing/practice/unpublish', data)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['practice-billing-publication'] })
    },
  })
}

export function useSendPracticeBillingEmails() {
  return useMutation({
    mutationFn: async (data: { month: number; year: number; teacher_cis: string[] }) => {
      const res = await api.post<{ sent: number; failed: number; skipped: number }>('/billing/practice/send-emails', data)
      return res.data
    },
  })
}

// ─── Practice Designation Options ─────────────────────────────────────────────

export function usePracticeDesignationOptions(enabled: boolean = false) {
  return useQuery<PracticeDesignationOptions>({
    queryKey: ['practice-designation-options'],
    queryFn: async () => {
      const res = await api.get<PracticeDesignationOptions>('/practice-planilla/designation-options')
      return res.data
    },
    enabled,
  })
}
