import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type {
  DesignationChangePreview,
  DesignationChangeRequest,
  DesignationChangeResult,
  PublicationPayrollSimulation,
  TeacherDesignationSummary,
} from '@/api/types'

const root = '/admin/academic-management'

export function useTeacherDesignations(academicPeriod: string, teacherCi: string) {
  return useQuery({
    queryKey: ['academic-management', 'designation-changes', 'designations', academicPeriod, teacherCi],
    queryFn: async () => (await api.get<TeacherDesignationSummary[]>(`${root}/designation-changes/designations`, {
      params: { academic_period: academicPeriod, teacher_ci: teacherCi },
    })).data,
    enabled: Boolean(academicPeriod && teacherCi),
  })
}

export function usePreviewTeacherChange() {
  return useMutation({
    mutationFn: async (body: DesignationChangeRequest) =>
      (await api.post<DesignationChangePreview>(`${root}/designation-changes/preview`, body)).data,
  })
}

export function useApplyTeacherChange() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: DesignationChangeRequest) =>
      (await api.post<DesignationChangeResult>(`${root}/designation-changes/apply`, body)).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['academic-management', 'designation-changes'] })
      void queryClient.invalidateQueries({ queryKey: ['designations'] })
    },
  })
}

export function useSimulatePublicationPayroll(draftId: number | null) {
  return useMutation({
    mutationFn: async (body: { effective_from: string; month: number; year: number }) =>
      (await api.post<PublicationPayrollSimulation>(`${root}/schedule-drafts/${draftId}/payroll-simulation`, body)).data,
  })
}
