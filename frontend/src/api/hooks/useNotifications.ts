import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'

export interface NotificationItem {
  id: number
  title: string
  message: string
  notification_type: string
  is_read: boolean
  reference_month: number | null
  reference_year: number | null
  created_at: string
}

export function useNotifications() {
  return useQuery({
    queryKey: ['notifications'],
    queryFn: async () => {
      const res = await api.get<NotificationItem[]>('/portal/notifications')
      return res.data
    },
  })
}

export function useUnreadCount(enabled: boolean = true) {
  return useQuery({
    queryKey: ['notifications-unread'],
    queryFn: async () => {
      const res = await api.get<{ count: number }>('/portal/notifications/unread-count')
      return res.data.count
    },
    enabled,
    refetchInterval: 30000,
  })
}

export function useMarkRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/portal/notifications/${id}/read`)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['notifications'] })
      void qc.invalidateQueries({ queryKey: ['notifications-unread'] })
    },
  })
}

export function useMarkAllRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      await api.post('/portal/notifications/read-all')
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['notifications'] })
      void qc.invalidateQueries({ queryKey: ['notifications-unread'] })
    },
  })
}
