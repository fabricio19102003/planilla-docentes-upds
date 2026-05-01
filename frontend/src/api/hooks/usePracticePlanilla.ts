import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'

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
