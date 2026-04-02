import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type { GeneratePlanillaPayload, PlanillaGenerateResponse, PlanillaOutput } from '@/api/types'

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
