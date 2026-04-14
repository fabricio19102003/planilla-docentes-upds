import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type {
  AttendanceFilters,
  AttendanceProcessResponse,
  AttendanceSummary,
  AttendanceWithDetails,
  Observation,
  PaginatedResponse,
  ProcessAttendancePayload,
} from '@/api/types'

async function fetchAttendanceSummary(month: number, year: number) {
  const response = await api.get<AttendanceSummary>(`/attendance/${month}/${year}/summary`)

  return response.data
}

async function fetchAttendanceRecords(filters: AttendanceFilters) {
  const response = await api.get<PaginatedResponse<AttendanceWithDetails>>(
    `/attendance/${filters.month}/${filters.year}`,
    {
      params: {
        teacher_ci: filters.teacherCi || undefined,
        status: filters.status || undefined,
        page: filters.page ?? 1,
        per_page: filters.perPage ?? 10,
      },
    },
  )

  return response.data
}

async function fetchObservations(month: number, year: number, type?: string, teacherCi?: string) {
  const response = await api.get<Observation[]>(`/observations/${month}/${year}`, {
    params: {
      type: type || undefined,
      teacher_ci: teacherCi || undefined,
    },
  })

  return response.data
}

async function processAttendance(payload: ProcessAttendancePayload) {
  const response = await api.post<AttendanceProcessResponse>('/attendance/process', payload)

  return response.data
}

export function useAttendanceSummary(month: number, year: number) {
  return useQuery({
    queryKey: ['attendance-summary', month, year],
    queryFn: () => fetchAttendanceSummary(month, year),
  })
}

export function useAttendance(filters: AttendanceFilters) {
  return useQuery({
    queryKey: ['attendance-records', filters],
    queryFn: () => fetchAttendanceRecords(filters),
  })
}

export function useObservations(month: number, year: number, type?: string, teacherCi?: string) {
  return useQuery({
    queryKey: ['observations', month, year, type, teacherCi],
    queryFn: () => fetchObservations(month, year, type, teacherCi),
  })
}

export function useAttendanceAudit(teacherCi: string, month: number, year: number, enabled: boolean = true) {
  return useQuery({
    queryKey: ['attendance-audit', teacherCi, month, year],
    queryFn: async () => {
      const res = await api.get(`/attendance/audit/${teacherCi}?month=${month}&year=${year}`)
      return res.data
    },
    enabled: enabled && !!teacherCi,
  })
}

export function useProcessAttendance() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: processAttendance,
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['attendance-summary', variables.month, variables.year] })
      void queryClient.invalidateQueries({ queryKey: ['attendance-records'] })
      void queryClient.invalidateQueries({ queryKey: ['observations', variables.month, variables.year] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] })
    },
  })
}
