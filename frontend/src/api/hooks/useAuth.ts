import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import type {
  AuthUser,
  BillingInfo,
  DetailRequestCreate,
  DetailRequestInfo,
  DetailRequestAction,
  UserCreate,
  UserUpdate,
} from '@/api/types'

// ─── Users (admin) ────────────────────────────────────────────────────────────

export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const res = await api.get<AuthUser[]>('/users')
      return res.data
    },
  })
}

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: UserCreate) => {
      const res = await api.post<AuthUser>('/users', data)
      return res.data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useUpdateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, data }: { id: number; data: UserUpdate }) => {
      const res = await api.put<AuthUser>(`/users/${id}`, data)
      return res.data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useDeactivateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/users/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useResetUserPassword() {
  return useMutation({
    mutationFn: async ({ id, new_password }: { id: number; new_password: string }) => {
      await api.post(`/users/${id}/reset-password`, { new_password })
    },
  })
}

// ─── Billing (docente portal) ─────────────────────────────────────────────────

export function useCurrentBilling() {
  return useQuery({
    queryKey: ['billing', 'current'],
    queryFn: async () => {
      const res = await api.get<BillingInfo>('/portal/billing/current')
      return res.data
    },
  })
}

export function useBillingHistory() {
  return useQuery({
    queryKey: ['billing', 'history'],
    queryFn: async () => {
      const res = await api.get<BillingInfo[]>('/portal/billing/history')
      return res.data
    },
  })
}

export function useMyProfile() {
  return useQuery({
    queryKey: ['portal', 'profile'],
    queryFn: async () => {
      const res = await api.get('/portal/profile')
      return res.data
    },
  })
}

// ─── Detail Requests ──────────────────────────────────────────────────────────

export function useMyRequests() {
  return useQuery({
    queryKey: ['requests', 'my'],
    queryFn: async () => {
      const res = await api.get<DetailRequestInfo[]>('/detail-requests/my')
      return res.data
    },
  })
}

export function useCreateRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: DetailRequestCreate) => {
      const res = await api.post<DetailRequestInfo>('/detail-requests', data)
      return res.data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['requests'] }),
  })
}

export function useAllRequests() {
  return useQuery({
    queryKey: ['requests', 'all'],
    queryFn: async () => {
      const res = await api.get<DetailRequestInfo[]>('/detail-requests')
      return res.data
    },
  })
}

export function useRespondRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, data }: { id: number; data: DetailRequestAction }) => {
      const res = await api.put<DetailRequestInfo>(`/detail-requests/${id}/respond`, data)
      return res.data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['requests'] }),
  })
}

// ─── Change password ──────────────────────────────────────────────────────────

export function useChangePassword() {
  return useMutation({
    mutationFn: async ({
      current_password,
      new_password,
    }: {
      current_password: string
      new_password: string
    }) => {
      await api.put('/auth/change-password', { current_password, new_password })
    },
  })
}
