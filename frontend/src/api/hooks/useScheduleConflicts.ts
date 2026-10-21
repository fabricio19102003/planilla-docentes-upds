import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type { ClassroomCatalogPlan, DesignationLoadPreview, DesignationLoadResult, ScheduleConflictsReport } from '@/api/types'
import { conflictsParams, loadFormData } from '@/lib/scheduleConflictsState'
import type { ConflictsFilters, DesignationLoadForm } from '@/lib/scheduleConflictsState'

const root = '/admin/academic-management'
const multipart = { headers: { 'Content-Type': 'multipart/form-data' } }

export function useScheduleConflicts(filters: ConflictsFilters) {
  const params = conflictsParams(filters)
  return useQuery({
    queryKey: ['academic-management', 'schedule-conflicts', params],
    queryFn: async () => (await api.get<ScheduleConflictsReport>(`${root}/schedule-conflicts`, { params })).data,
    enabled: params !== null,
  })
}

export function usePreviewClassroomCatalog() {
  return useMutation({
    mutationFn: async () => (await api.post<ClassroomCatalogPlan>(`${root}/classroom-catalog/preview`)).data,
  })
}

export function useApplyClassroomCatalog() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => (await api.post<ClassroomCatalogPlan>(`${root}/classroom-catalog/apply`)).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['academic-management'] }),
  })
}

export function usePreviewDesignationLoad() {
  return useMutation({
    mutationFn: async (form: DesignationLoadForm) =>
      (await api.post<DesignationLoadPreview>(`${root}/designation-load/preview`, loadFormData(form), multipart)).data,
  })
}

export function useApplyDesignationLoad() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ form, digest }: { form: DesignationLoadForm; digest: string }) =>
      (await api.post<DesignationLoadResult>(`${root}/designation-load/apply`, loadFormData(form, digest), multipart)).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['academic-management'] }),
  })
}
