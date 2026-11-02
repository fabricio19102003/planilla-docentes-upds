import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type { StudentDetail } from '@/lib/academicRecordsState'
import {
  inboxQueryParams,
  type Inbox,
  type InboxFilters,
  type ObservationReason,
  type PortalAccount,
  type ReenrollmentRequest,
  type ReenrollmentWindow,
  type TemporaryCredential,
} from '@/lib/reenrollmentState'

const records = '/admin/academic-records'
const root = '/admin/reenrollment'
const key = ['reenrollment'] as const

function useInvalidate(...keys: readonly unknown[][]) {
  const queryClient = useQueryClient()
  return () => keys.forEach((queryKey) => void queryClient.invalidateQueries({ queryKey }))
}

export function useIssueTemporaryPassword() {
  const invalidate = useInvalidate(['academic-records', 'students'])
  return useMutation({
    mutationFn: async (studentId: number) =>
      (await api.post<TemporaryCredential>(`${records}/students/${studentId}/account/temporary-password`)).data,
    onSuccess: invalidate,
  })
}

export function useIssueTemporaryPasswords() {
  const invalidate = useInvalidate(['academic-records', 'students'])
  return useMutation({
    mutationFn: async (studentIds: number[]) =>
      (await api.post<{ credentials: TemporaryCredential[] }>(`${records}/student-accounts/temporary-passwords`,
        { student_ids: studentIds })).data.credentials,
    onSuccess: invalidate,
  })
}

export function useSetAccountActive() {
  const invalidate = useInvalidate(['academic-records', 'students'])
  return useMutation({
    mutationFn: async ({ studentId, active }: { studentId: number; active: boolean }) =>
      (await api.post<{ account: PortalAccount }>(
        `${records}/students/${studentId}/account/${active ? 'enable' : 'disable'}`)).data.account,
    onSuccess: invalidate,
  })
}

export function useReenrollmentWindows() {
  return useQuery({
    queryKey: [...key, 'windows'],
    queryFn: async () => (await api.get<ReenrollmentWindow[]>(`${root}/windows`)).data,
  })
}

export function useSaveWindow() {
  const invalidate = useInvalidate([...key])
  return useMutation({
    mutationFn: async (payload: { id?: number; term_code: string; starts_on: string; ends_on: string }) => {
      const { id, term_code, ...dates } = payload
      return id
        ? (await api.put<ReenrollmentWindow>(`${root}/windows/${id}`, dates)).data
        : (await api.post<ReenrollmentWindow>(`${root}/windows`, { term_code, ...dates })).data
    },
    onSuccess: invalidate,
  })
}

export function useInbox(windowId: number | undefined, filters: InboxFilters) {
  return useQuery({
    queryKey: [...key, 'requests', windowId, filters],
    queryFn: async () =>
      (await api.get<Inbox>(`${root}/requests`, { params: { ...inboxQueryParams(filters), window_id: windowId } })).data,
    enabled: windowId !== undefined,
    placeholderData: (previous) => previous,
  })
}

export type RequestDetail = ReenrollmentRequest & StudentDetail

export function useRequestDetail(requestId: number | null) {
  return useQuery({
    queryKey: [...key, 'requests', 'detail', requestId],
    queryFn: async () => (await api.get<RequestDetail>(`${root}/requests/${requestId}`)).data,
    enabled: requestId !== null,
  })
}

export function useHandleRequest() {
  const invalidate = useInvalidate([...key])
  return useMutation({
    mutationFn: async ({ id, action, reason, message }: {
      id: number; action: 'complete' | 'observe' | 'reopen'; reason?: ObservationReason; message?: string
    }) => (await api.post<ReenrollmentRequest>(`${root}/requests/${id}/${action}`,
      action === 'observe' ? { reason, message } : undefined)).data,
    onSuccess: invalidate,
  })
}
