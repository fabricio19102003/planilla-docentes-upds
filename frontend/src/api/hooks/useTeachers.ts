import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type {
  Designation,
  PaginatedResponse,
  Teacher,
  TeacherDetail,
  TeacherPhotoPayload,
  WhatsAppPreferenceAdminResponse,
  WhatsAppPreferenceOptOutRequest,
  WhatsAppPreferencePutRequest,
} from '@/api/types'
import type { TeacherType } from '@/domain/teacherTypes'
import { downloadApiBlob, safeDownloadSegment } from '@/lib/download'

interface TeachersParams {
  search?: string
  page?: number
  perPage?: number
}

async function fetchTeachers(params: TeachersParams) {
  const response = await api.get<PaginatedResponse<Teacher>>('/teachers', {
    params: {
      search: params.search || undefined,
      page: params.page ?? 1,
      per_page: params.perPage ?? 10,
    },
  })

  return response.data
}

async function fetchTeacherDetail(ci: string) {
  const response = await api.get<TeacherDetail>(`/teachers/${ci}`)

  return response.data
}

export function useTeachers(params: TeachersParams) {
  return useQuery({
    queryKey: ['teachers', params],
    queryFn: () => fetchTeachers(params),
  })
}

export function useTeacherDetail(ci?: string) {
  return useQuery({
    queryKey: ['teacher-detail', ci],
    queryFn: () => fetchTeacherDetail(ci ?? ''),
    enabled: Boolean(ci),
  })
}

export function useCreateTeacher() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      ci: string
      full_name: string
      email?: string
      phone?: string
      gender?: string
      external_permanent?: TeacherType
      academic_level?: string
      profession?: string
      specialty?: string
      bank?: string
      account_number?: string
      sap_code?: string
      invoice_retention?: string
    }) => {
      const res = await api.post<Teacher>('/teachers', data)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['teachers'] })
    },
  })
}

export function useUpdateTeacher() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ ci, data }: { ci: string; data: Record<string, unknown> }) => {
      const res = await api.put<Teacher>(`/teachers/${ci}`, data)
      return res.data
    },
    onSuccess: (teacher, variables) => {
      void qc.invalidateQueries({ queryKey: ['teachers'] })
      void qc.invalidateQueries({ queryKey: ['teacher-detail'] })
      void qc.invalidateQueries({ queryKey: ['whatsapp-preference', variables.ci] })
      void qc.invalidateQueries({ queryKey: ['whatsapp-preference', teacher.ci] })
    },
  })
}

export function useWhatsAppPreference(ci?: string) {
  return useQuery({
    queryKey: ['whatsapp-preference', ci],
    queryFn: async () => {
      const response = await api.get<WhatsAppPreferenceAdminResponse>(`/teachers/${encodeURIComponent(ci ?? '')}/whatsapp-preference`)
      return response.data
    },
    enabled: Boolean(ci),
  })
}

function invalidateWhatsAppPreference(qc: ReturnType<typeof useQueryClient>, ci: string) {
  void qc.invalidateQueries({ queryKey: ['whatsapp-preference', ci] })
}

export function useSaveWhatsAppPreference() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ ci, data }: { ci: string; data: WhatsAppPreferencePutRequest }) => {
      const response = await api.put<WhatsAppPreferenceAdminResponse>(`/teachers/${encodeURIComponent(ci)}/whatsapp-preference`, data)
      return response.data
    },
    onSuccess: (preference, { ci }) => invalidateWhatsAppPreference(qc, preference.teacher_ci || ci),
  })
}

export function useOptOutWhatsAppPreference() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ ci, data }: { ci: string; data: WhatsAppPreferenceOptOutRequest }) => {
      const response = await api.post<WhatsAppPreferenceAdminResponse>(`/teachers/${encodeURIComponent(ci)}/whatsapp-preference/opt-out`, data)
      return response.data
    },
    onSuccess: (preference, { ci }) => invalidateWhatsAppPreference(qc, preference.teacher_ci || ci),
  })
}

export function useUploadTeacherPhoto() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ ci, file }: TeacherPhotoPayload) => {
      const formData = new FormData()
      formData.append('file', file)
      const res = await api.put<Teacher>(`/teachers/${ci}/photo`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return res.data
    },
    onSuccess: (teacher) => {
      void qc.invalidateQueries({ queryKey: ['teachers'] })
      void qc.invalidateQueries({ queryKey: ['teacher-detail', teacher.ci] })
      void qc.invalidateQueries({ queryKey: ['teacher-detail'] })
    },
  })
}

export function useDeleteTeacherPhoto() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (ci: string) => {
      const res = await api.delete<Teacher>(`/teachers/${ci}/photo`)
      return res.data
    },
    onSuccess: (teacher) => {
      void qc.invalidateQueries({ queryKey: ['teachers'] })
      void qc.invalidateQueries({ queryKey: ['teacher-detail', teacher.ci] })
      void qc.invalidateQueries({ queryKey: ['teacher-detail'] })
    },
  })
}

export async function downloadTeacherPhoto(ci: string): Promise<void> {
  await downloadApiBlob(`/teachers/${encodeURIComponent(ci)}/photo/download`)
}

export async function downloadTeacherSchedule(ci: string, teacherName?: string): Promise<void> {
  const safeName = safeDownloadSegment(teacherName, 'docente')
  const year = new Date().getFullYear()
  await downloadApiBlob(`/teachers/${encodeURIComponent(ci)}/schedule/pdf`, `Horario_de_${safeName}_Gestion_${year}.pdf`)
}

export function useUpdateDesignationContractDates() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      designationId,
      contract_start_date,
      contract_end_date,
    }: {
      designationId: number
      contract_start_date: string | null
      contract_end_date: string | null
    }) => {
      const res = await api.put<Designation>(`/teachers/designations/${designationId}/contract-dates`, {
        contract_start_date,
        contract_end_date,
      })
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['teacher-detail'] })
    },
  })
}

export function useDeleteTeacher() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (ci: string) => {
      await api.delete(`/teachers/${ci}`)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['teachers'] })
    },
  })
}

export function useBulkDeleteTeachers() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (teacherCis: string[]) => {
      const res = await api.post<{ deleted: number; errors: string[] }>('/teachers/bulk-delete', { teacher_cis: teacherCis })
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['teachers'] })
    },
  })
}
