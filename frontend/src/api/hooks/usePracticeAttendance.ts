import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'

// Types inline since they're specific to this module
export interface PracticeAttendanceEntry {
  id: number
  teacher_ci: string
  teacher_name: string | null
  designation_id: number
  subject: string | null
  group_code: string | null
  semester: string | null
  date: string
  scheduled_start: string
  scheduled_end: string
  actual_start: string | null
  actual_end: string | null
  academic_hours: number
  status: 'attended' | 'absent' | 'late' | 'justified'
  observation: string | null
  registered_by: string | null
}

export interface PracticeAttendanceSummary {
  teacher_ci: string
  teacher_name: string
  total_scheduled: number
  total_attended: number
  total_absent: number
  total_late: number
  total_justified: number
  total_hours_scheduled: number
  total_hours_attended: number
  attendance_rate: number
}

// Generate skeleton
export function useGeneratePracticeAttendance() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (params: { month: number; year: number; start_date?: string; end_date?: string }) => {
      const res = await api.post('/practice-attendance/generate', params)
      return res.data as { created: number; month: number; year: number }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['practice-attendance'] })
      void qc.invalidateQueries({ queryKey: ['practice-attendance-summary'] })
    },
  })
}

// List entries
export function usePracticeAttendance(
  month: number,
  year: number,
  teacherCi?: string,
  startDate?: string,
  endDate?: string,
) {
  const params = new URLSearchParams()
  if (teacherCi) params.set('teacher_ci', teacherCi)
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  const qs = params.toString()
  return useQuery<PracticeAttendanceEntry[]>({
    queryKey: ['practice-attendance', month, year, teacherCi, startDate, endDate],
    queryFn: async () => {
      const res = await api.get(`/practice-attendance/${month}/${year}${qs ? '?' + qs : ''}`)
      return res.data
    },
  })
}

// Summary
export function usePracticeAttendanceSummary(month: number, year: number, startDate?: string, endDate?: string) {
  const params = new URLSearchParams()
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  const qs = params.toString()
  return useQuery<PracticeAttendanceSummary[]>({
    queryKey: ['practice-attendance-summary', month, year, startDate, endDate],
    queryFn: async () => {
      const res = await api.get(`/practice-attendance/${month}/${year}/summary${qs ? '?' + qs : ''}`)
      return res.data
    },
  })
}

// Update entry
export function useUpdatePracticeAttendance() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      ...data
    }: {
      id: number
      status?: string
      actual_start?: string
      actual_end?: string
      observation?: string
    }) => {
      const res = await api.put(`/practice-attendance/${id}`, data)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['practice-attendance'] })
      void qc.invalidateQueries({ queryKey: ['practice-attendance-summary'] })
    },
  })
}

// Delete entry
export function useDeletePracticeAttendance() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/practice-attendance/${id}`)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['practice-attendance'] })
      void qc.invalidateQueries({ queryKey: ['practice-attendance-summary'] })
    },
  })
}

// Export PDF
export async function downloadPracticeAttendancePdf(params: {
  month: number; year: number;
  start_date?: string; end_date?: string;
  teacher_ci?: string;
}) {
  const qp = new URLSearchParams()
  if (params.start_date) qp.set('start_date', params.start_date)
  if (params.end_date) qp.set('end_date', params.end_date)
  if (params.teacher_ci) qp.set('teacher_ci', params.teacher_ci)
  const qs = qp.toString()
  const response = await api.get(
    `/practice-attendance/${params.month}/${params.year}/export/pdf${qs ? '?' + qs : ''}`,
    { responseType: 'blob' }
  )
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url
  link.download = `asistencia_practicas_${params.month}_${params.year}.pdf`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

// Export Excel
export async function downloadPracticeAttendanceExcel(params: {
  month: number; year: number;
  start_date?: string; end_date?: string;
  teacher_ci?: string;
}) {
  const qp = new URLSearchParams()
  if (params.start_date) qp.set('start_date', params.start_date)
  if (params.end_date) qp.set('end_date', params.end_date)
  if (params.teacher_ci) qp.set('teacher_ci', params.teacher_ci)
  const qs = qp.toString()
  const response = await api.get(
    `/practice-attendance/${params.month}/${params.year}/export/excel${qs ? '?' + qs : ''}`,
    { responseType: 'blob' }
  )
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url
  link.download = `asistencia_practicas_${params.month}_${params.year}.xlsx`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}
