import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'

export interface BillingPublication {
  id: number
  month: number
  year: number
  status: 'published' | 'draft'
  version: number
  total_teachers: number
  total_payment: number
  published_by: number | null
  published_at: string | null
  unpublished_at: string | null
  notes: string | null
}

export function usePublicationStatus(month: number, year: number, enabled: boolean = true) {
  return useQuery({
    queryKey: ['billing-publication', month, year],
    queryFn: async () => {
      try {
        const res = await api.get<BillingPublication>(`/billing/publication/${month}/${year}`)
        return res.data
      } catch (e: unknown) {
        const status = (e as { response?: { status?: number } })?.response?.status
        if (status === 404) return null
        throw e
      }
    },
    enabled,
  })
}

export function usePublishBilling() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: { month: number; year: number; notes?: string }) => {
      const res = await api.post<BillingPublication>('/billing/publish', data)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['billing-publication'] })
      void qc.invalidateQueries({ queryKey: ['planilla-status'] })
      void qc.invalidateQueries({ queryKey: ['planilla-history'] })
    },
  })
}

export function useUnpublishBilling() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: { month: number; year: number }) => {
      const res = await api.post<BillingPublication>('/billing/unpublish', data)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['billing-publication'] })
    },
  })
}

export function useSendBillingEmails() {
  return useMutation({
    mutationFn: async (data: { month: number; year: number; teacher_cis: string[] }) => {
      const res = await api.post<{ sent: number; failed: number; skipped: number }>('/billing/send-emails', data)
      return res.data
    },
  })
}

export interface BillingNotificationReadiness {
  ready: boolean
  reason?: string
  capacity?: { available: boolean; requested?: number; remaining?: number | null; exceeded?: boolean | null }
}

export interface BillingNotificationRecipient {
  teacher_ci: string
  phone_masked: string | null
  channel: 'whatsapp' | 'email' | 'blocked' | 'skipped'
  reason: string
}

export interface BillingNotificationPreview {
  digest: string
  recipients: BillingNotificationRecipient[]
  readiness: BillingNotificationReadiness
}

export interface BillingNotificationBatchStatus {
  batch_id: number
  digest: string
  status: string
  created_at: string
  jobs: Array<{ channel: string; status: string }>
}

export function useBillingNotificationReadiness(enabled: boolean) {
  return useQuery({
    queryKey: ['billing-notification-readiness'],
    queryFn: async () => (await api.get<BillingNotificationReadiness>('/billing/notifications/readiness')).data,
    enabled,
    refetchInterval: 30000,
  })
}

export function usePreviewBillingNotifications() {
  return useMutation({
    mutationFn: async (data: { month: number; year: number; teacher_cis: string[] }) => (
      await api.post<BillingNotificationPreview>('/billing/notifications/preview', data)
    ).data,
  })
}

export function useConfirmBillingNotifications() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: { month: number; year: number; teacher_cis: string[]; digest: string }) => (
      await api.post<{ batch_id: number; digest: string; status: string }>('/billing/notifications/confirm', data)
    ).data,
    onSuccess: (result) => void qc.invalidateQueries({ queryKey: ['billing-notification-batch', result.batch_id] }),
  })
}

export function useBillingNotificationBatch(batchId: number | null) {
  return useQuery({
    queryKey: ['billing-notification-batch', batchId],
    queryFn: async () => (await api.get<BillingNotificationBatchStatus>('/billing/notifications/batches/' + batchId)).data,
    enabled: batchId !== null,
    refetchInterval: 15000,
  })
}
