import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type {
  DesignationAdminFilters,
  DesignationAdminList,
  DesignationAdminMutation,
  DesignationWritePayload,
} from '@/api/types'

const root = '/admin/designations'
const listKey = ['designations', 'admin'] as const

export function useDesignationList(filters: DesignationAdminFilters) {
  return useQuery({
    queryKey: [...listKey, filters],
    queryFn: async () => (await api.get<DesignationAdminList>(root, { params: filters })).data,
    placeholderData: (previous) => previous,
  })
}

/** Every write refreshes the list and whatever else reads designations (teacher detail, contracts). */
function useDesignationMutation<TVariables>(request: (variables: TVariables) => Promise<DesignationAdminMutation | null>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: request,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['designations'] })
      void queryClient.invalidateQueries({ queryKey: ['teachers'] })
      void queryClient.invalidateQueries({ queryKey: ['teacher-designations'] })
    },
  })
}

export function useCreateDesignation() {
  return useDesignationMutation(async (body: DesignationWritePayload) =>
    (await api.post<DesignationAdminMutation>(root, body)).data)
}

export function useUpdateDesignation() {
  return useDesignationMutation(async ({ id, body }: { id: number; body: DesignationWritePayload }) =>
    (await api.put<DesignationAdminMutation>(`${root}/${id}`, body)).data)
}

export function useFinalizeDesignation() {
  return useDesignationMutation(async ({ id, endDate }: { id: number; endDate: string }) =>
    (await api.post<DesignationAdminMutation>(`${root}/${id}/finalize`, { end_date: endDate })).data)
}

export function useDeleteDesignation() {
  return useDesignationMutation(async (id: number) => {
    await api.delete(`${root}/${id}`)
    return null
  })
}
