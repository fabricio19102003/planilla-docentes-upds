import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import {
  courseQueryParams,
  type AdminIntensiveCourse,
  type AdminIntensiveCourseDetail,
  type CourseCreatePayload,
  type CourseFilters,
  type CourseUpdatePayload,
  type IntensiveSettings,
  type SettingsPayload,
} from '@/lib/intensiveCoursesState'

const root = '/admin/intensive-courses'
const key = ['intensive-courses'] as const

function useInvalidate() {
  const queryClient = useQueryClient()
  return () => void queryClient.invalidateQueries({ queryKey: key })
}

export function useIntensiveSettings() {
  return useQuery({
    queryKey: [...key, 'settings'],
    queryFn: async () => (await api.get<IntensiveSettings>(`${root}/settings`)).data,
  })
}

export function useSaveIntensiveSettings() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async (payload: SettingsPayload) => (await api.put<IntensiveSettings>(`${root}/settings`, payload)).data,
    onSuccess: invalidate,
  })
}

export function useIntensiveCourses(filters: CourseFilters) {
  return useQuery({
    queryKey: [...key, 'list', filters],
    queryFn: async () => (await api.get<AdminIntensiveCourse[]>(root, { params: courseQueryParams(filters) })).data,
  })
}

export function useIntensiveCourse(courseId: number | null) {
  return useQuery({
    queryKey: [...key, 'detail', courseId],
    queryFn: async () => (await api.get<AdminIntensiveCourseDetail>(`${root}/${courseId}`)).data,
    enabled: courseId !== null,
  })
}

export function useSaveIntensiveCourse() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async (input: { id: number; payload: CourseUpdatePayload } | { id?: undefined; payload: CourseCreatePayload }) =>
      input.id === undefined
        ? (await api.post<AdminIntensiveCourseDetail>(root, input.payload)).data
        : (await api.put<AdminIntensiveCourseDetail>(`${root}/${input.id}`, input.payload)).data,
    onSuccess: invalidate,
  })
}

export function useCloseIntensiveCourse() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async (courseId: number) => (await api.post<AdminIntensiveCourseDetail>(`${root}/${courseId}/close`)).data,
    onSuccess: invalidate,
  })
}
