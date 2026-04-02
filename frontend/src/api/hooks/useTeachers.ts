import { useQuery } from '@tanstack/react-query'

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
