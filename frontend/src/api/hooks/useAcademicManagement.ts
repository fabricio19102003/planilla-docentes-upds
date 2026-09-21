import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type {
  AcademicGroup,
  AcademicProgram,
  AcademicSubject,
  Classroom,
  PaginatedResponse,
  SubjectOffering,
  Teacher,
  TeacherAvailability,
} from '@/api/types'
import {
  academicCollectionRequest,
  teacherAvailabilityRequest,
  teacherSearchRequest,
} from '@/lib/academicManagementState'

export type AcademicResource = 'programs' | 'subjects' | 'offerings' | 'groups' | 'classrooms' | 'availability'

export interface AcademicResourceMap {
  programs: AcademicProgram
  subjects: AcademicSubject
  offerings: SubjectOffering
  groups: AcademicGroup
  classrooms: Classroom
  availability: TeacherAvailability
}

const root = '/admin/academic-management'

export function useAcademicCollection<R extends Exclude<AcademicResource, 'availability'>>(resource: R) {
  const request = academicCollectionRequest(resource)
  return useQuery({
    queryKey: request.queryKey,
    queryFn: async () => (await api.get<AcademicResourceMap[R][]>(request.url)).data,
  })
}

export function useTeacherAvailability(teacherCi: string, academicPeriod: string) {
  const request = teacherAvailabilityRequest(teacherCi, academicPeriod)
  return useQuery({
    queryKey: request.queryKey,
    queryFn: async () => (await api.get<TeacherAvailability[]>(request.url, {
      params: request.params,
    })).data,
    enabled: request.enabled,
  })
}

export function useAcademicTeacherSearch(search: string, page: number) {
  const request = teacherSearchRequest(search, page)
  return useQuery({
    queryKey: request.queryKey,
    queryFn: async () => (await api.get<PaginatedResponse<Teacher>>('/teachers', {
      params: request.params,
    })).data,
    placeholderData: (previous) => previous,
  })
}

export function useSaveAcademicResource<R extends AcademicResource>(resource: R) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, payload }: { id?: number; payload: Record<string, unknown> }) => {
      const response = id
        ? await api.put<AcademicResourceMap[R]>(`${root}/${resource}/${id}`, payload)
        : await api.post<AcademicResourceMap[R]>(`${root}/${resource}`, payload)
      return response.data
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['academic-management', resource] }),
  })
}

export function useDeactivateAcademicResource(resource: AcademicResource) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => (await api.post(`${root}/${resource}/${id}/deactivate`)).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['academic-management', resource] }),
  })
}
