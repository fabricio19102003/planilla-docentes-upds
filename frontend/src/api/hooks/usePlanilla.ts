import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type { GeneratePlanillaPayload, PlanillaDetailResponse, PlanillaGenerateResponse, PlanillaOutput, TeacherDesignationsResponse } from '@/api/types'

export function useApprovePlanilla() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (planillaId: number) => {
      const res = await api.post(`/planilla/${planillaId}/approve`)
      return res.data as { success: boolean; status: string; planilla_id: number }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['planilla'] })
      void qc.invalidateQueries({ queryKey: ['planilla-history'] })
      void qc.invalidateQueries({ queryKey: ['planilla-status'] })
    },
  })
}

export function useRejectPlanilla() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (planillaId: number) => {
      const res = await api.post(`/planilla/${planillaId}/reject`)
      return res.data as { success: boolean; status: string; planilla_id: number }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['planilla'] })
      void qc.invalidateQueries({ queryKey: ['planilla-history'] })
      void qc.invalidateQueries({ queryKey: ['planilla-status'] })
    },
  })
}

export function usePlanillaStatus(month: number, year: number) {
  return useQuery({
    queryKey: ['planilla-status', month, year],
    queryFn: async () => {
      const res = await api.get<PlanillaOutput[]>('/planilla/history')
      const match = res.data.find((p) => p.month === month && p.year === year)
      return match ?? null
    },
  })
}

async function fetchPlanillaHistory() {
  const response = await api.get<PlanillaOutput[]>('/planilla/history')

  return response.data
}

async function generatePlanilla(payload: GeneratePlanillaPayload) {
  const response = await api.post<PlanillaGenerateResponse>('/planilla/generate', payload)

  return response.data
}

export function usePlanillaHistory() {
  return useQuery({
    queryKey: ['planilla-history'],
    queryFn: fetchPlanillaHistory,
  })
}

export async function downloadPlanilla(planillaId: number, filename?: string) {
  const response = await api.get(`/planilla/${planillaId}/download`, {
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url
  link.download = filename ?? `planilla_${planillaId}.xlsx`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export async function downloadSalaryReport(params: {
  month: number
  year: number
  company_name?: string
  company_nit?: string
  discount_mode?: string
  start_date?: string
  end_date?: string
}) {
  const response = await api.post('/planilla/salary-report', params, {
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url
  const monthNames: Record<number, string> = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
  }
  link.download = `Planilla_Salario_${monthNames[params.month]}_${params.year}.xlsx`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

async function fetchPlanillaDetail(month: number, year: number, startDate?: string, endDate?: string, discountMode?: string) {
  const params = new URLSearchParams()
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  if (discountMode) params.set('discount_mode', discountMode)
  const qs = params.toString()
  const url = `/planilla/${month}/${year}/detail${qs ? '?' + qs : ''}`
  const response = await api.get<PlanillaDetailResponse>(url)
  return response.data
}

export function usePlanillaDetail(
  month: number,
  year: number,
  enabled: boolean = true,
  startDate?: string,
  endDate?: string,
  discountMode?: string,
) {
  return useQuery({
    queryKey: ['planilla-detail', month, year, startDate, endDate, discountMode],
    queryFn: () => fetchPlanillaDetail(month, year, startDate, endDate, discountMode),
    enabled,
  })
}

async function fetchTeacherDesignations(teacherCi: string) {
  const response = await api.get<TeacherDesignationsResponse>(`/teachers/${teacherCi}/designations`)
  return response.data
}

export function useTeacherDesignations(teacherCi: string, enabled: boolean = true) {
  return useQuery({
    queryKey: ['teacher-designations', teacherCi],
    queryFn: () => fetchTeacherDesignations(teacherCi),
    enabled: enabled && !!teacherCi,
  })
}

export function useGeneratePlanilla() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: generatePlanilla,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['planilla-history'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] })
    },
  })
}
