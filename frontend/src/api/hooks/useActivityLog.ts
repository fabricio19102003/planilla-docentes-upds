import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'

export interface ActivityLogEntry {
  id: number
  user_id: number | null
  user_ci: string | null
  user_name: string | null
  user_role: string | null
  action: string
  category: string
  description: string
  details: Record<string, any> | null
  status: string
  ip_address: string | null
  created_at: string
}

export interface ActivityLogResponse {
  items: ActivityLogEntry[]
  total: number
  page: number
  per_page: number
}

export interface ActivityStats {
  total_logs: number
  logs_today: number
  most_active_users: { user_name: string; user_ci: string; count: number }[]
  actions_by_category: { category: string; count: number }[]
  recent_logins: ActivityLogEntry[]
}

export interface ActivityLogFilters {
  page?: number
  per_page?: number
  user_ci?: string
  category?: string
  action?: string
  start_date?: string
  end_date?: string
}

export function useActivityLogs(filters: ActivityLogFilters) {
  const params = new URLSearchParams()
  if (filters.page) params.set('page', String(filters.page))
  if (filters.per_page) params.set('per_page', String(filters.per_page))
  if (filters.user_ci) params.set('user_ci', filters.user_ci)
  if (filters.category) params.set('category', filters.category)
  if (filters.action) params.set('action', filters.action)
  if (filters.start_date) params.set('start_date', filters.start_date)
  if (filters.end_date) params.set('end_date', filters.end_date)

  return useQuery({
    queryKey: ['activity-logs', filters],
    queryFn: async () => {
      const res = await api.get<ActivityLogResponse>(`/activity/logs?${params.toString()}`)
      return res.data
    },
  })
}

export function useActivityStats() {
  return useQuery({
    queryKey: ['activity-stats'],
    queryFn: async () => {
      const res = await api.get<ActivityStats>('/activity/stats')
      return res.data
    },
  })
}
