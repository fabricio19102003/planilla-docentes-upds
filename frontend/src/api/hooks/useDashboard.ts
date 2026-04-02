import { useQuery } from '@tanstack/react-query'

import { api } from '@/api/client'
import type { DashboardSummary } from '@/api/types'

async function fetchDashboardSummary() {
  const response = await api.get<DashboardSummary>('/dashboard/summary')

  return response.data
}

export function useDashboard() {
  return useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: fetchDashboardSummary,
  })
}
