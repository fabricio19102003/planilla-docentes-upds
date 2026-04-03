import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type { GeneratePlanillaPayload, PlanillaDetailResponse, PlanillaGenerateResponse, PlanillaOutput } from '@/api/types'

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

async function fetchPlanillaDetail(month: number, year: number) {
  const response = await api.get<PlanillaDetailResponse>(`/planilla/${month}/${year}/detail`)
  return response.data
}

export function usePlanillaDetail(month: number, year: number, enabled: boolean = true) {
  return useQuery({
    queryKey: ['planilla-detail', month, year],
    queryFn: () => fetchPlanillaDetail(month, year),
    enabled,
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
