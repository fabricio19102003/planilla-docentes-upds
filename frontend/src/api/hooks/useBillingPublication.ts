import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'

export interface BillingPublication {
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
}

export function usePublicationStatus(month: number, year: number) {
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
