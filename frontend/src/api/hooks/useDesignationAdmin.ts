import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type {
  DesignationAdminFilters,
  DesignationAdminList,
  DesignationAdminMutation,
  DesignationWritePayload,
} from '@/api/types'
import type { DesignationRoomApplyResult, DesignationRoomPreview } from '@/lib/designationRoomImport'

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

function roomForm(file: File, previewDigest?: string) {
  const form = new FormData()
  form.append('file', file)
  if (previewDigest) form.append('preview_digest', previewDigest)
  return form
}

const multipart = { headers: { 'Content-Type': 'multipart/form-data' } }

export function useDesignationRoomPreview() {
  return useMutation({
    mutationFn: async ({ file, onProgress }: { file: File; onProgress?: (percent: number) => void }) =>
      (await api.post<DesignationRoomPreview>(`${root}/rooms/preview`, roomForm(file), {
        ...multipart,
        onUploadProgress: (event) => onProgress?.(event.total ? Math.round((event.loaded / event.total) * 100) : 0),
      })).data,
  })
}

export function useApplyDesignationRooms() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ file, previewDigest }: { file: File; previewDigest: string }) =>
      (await api.post<DesignationRoomApplyResult>(`${root}/rooms/apply`, roomForm(file, previewDigest), multipart)).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['designations'] }),
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

/** Sets or clears only the classroom: it never touches payroll data, so paid designations accept it. */
export function useSetDesignationClassroom() {
  return useDesignationMutation(async ({ id, classroomId }: { id: number; classroomId: number | null }) =>
    (await api.put<DesignationAdminMutation>(`${root}/${id}/classroom`, { classroom_id: classroomId })).data)
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
