import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import { groupOpeningQueryParams, groupSizePayload, type GroupOpening } from '@/lib/groupOpeningState'

const root = '/admin/group-opening'
const key = ['group-opening'] as const

export function useGroupOpening(windowId: number | undefined) {
  return useQuery({
    queryKey: [...key, windowId],
    queryFn: async () => (await api.get<GroupOpening>(root, { params: groupOpeningQueryParams(windowId) })).data,
    placeholderData: (previous) => previous,
  })
}

export function useSaveGroupSize() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (raw: string) => (await api.put<{ group_size: number }>(`${root}/settings`, groupSizePayload(raw))).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: key }),
  })
}
