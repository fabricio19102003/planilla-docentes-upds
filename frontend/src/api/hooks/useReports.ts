import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'

export interface ReportFilters {
  report_type: string
  month?: number
  year?: number
  teacher_ci?: string
  semester?: string
  group_code?: string
  subject?: string
}

export interface ReportInfo {
  id: number
  report_type: string
  title: string
  description: string
  file_size: number
  generated_at: string
  status: string
}

export function useReportPreview(filters: ReportFilters, enabled: boolean) {
  const params = new URLSearchParams()
  params.set('report_type', filters.report_type)
  if (filters.month) params.set('month', String(filters.month))
  if (filters.year) params.set('year', String(filters.year))
  if (filters.teacher_ci) params.set('teacher_ci', filters.teacher_ci)
  if (filters.semester) params.set('semester', filters.semester)
  if (filters.group_code) params.set('group_code', filters.group_code)
  if (filters.subject) params.set('subject', filters.subject)

  return useQuery({
    queryKey: ['report-preview', filters],
    queryFn: async () => {
      const response = await api.get(`/reports/preview?${params.toString()}`)
      return response.data
    },
    enabled,
  })
}

export function useGenerateReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (filters: ReportFilters) => {
      const params = new URLSearchParams()
      params.set('report_type', filters.report_type)
      if (filters.month) params.set('month', String(filters.month))
      if (filters.year) params.set('year', String(filters.year))
      if (filters.teacher_ci) params.set('teacher_ci', filters.teacher_ci)
      if (filters.semester) params.set('semester', filters.semester)
      if (filters.group_code) params.set('group_code', filters.group_code)
      if (filters.subject) params.set('subject', filters.subject)
      const response = await api.post<ReportInfo>(`/reports/generate?${params.toString()}`)
      return response.data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['report-history'] })
    },
  })
}

export async function downloadReport(reportId: number, filename?: string) {
  const response = await api.get(`/reports/${reportId}/download`, { responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url
  link.download = filename ?? `reporte_${reportId}.pdf`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export function useReportHistory() {
  return useQuery({
    queryKey: ['report-history'],
    queryFn: async () => {
      const response = await api.get<ReportInfo[]>('/reports/history')
      return response.data
    },
  })
}
