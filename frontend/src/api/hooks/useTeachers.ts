import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type { PaginatedResponse, Teacher, TeacherDetail } from '@/api/types'

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
      external_permanent?: string
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
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['teachers'] })
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
