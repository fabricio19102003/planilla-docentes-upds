import { useMutation, useQuery } from '@tanstack/react-query'

import { api } from '@/api/client'
import {
  exportFilename,
  scheduleExportRequest,
  scheduleViewRequest,
} from '@/lib/academicScheduleGrid'
import type { ScheduleFilters, ScheduleViewResponse } from '@/lib/academicScheduleGrid'

export function useScheduleView(filters: ScheduleFilters) {
  const request = scheduleViewRequest(filters)
  return useQuery({
    queryKey: request.queryKey,
    queryFn: async () => (await api.get<ScheduleViewResponse>(request.url, { params: request.params })).data,
    enabled: request.enabled,
    placeholderData: (previous) => previous,
  })
}

export function useDownloadScheduleExcel() {
  return useMutation({
    mutationFn: async (filters: ScheduleFilters) => {
      const request = scheduleExportRequest(filters)
      const response = await api.get(request.url, { params: request.params, responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([response.data as BlobPart]))
      const link = document.createElement('a')
      link.href = url
      link.download = exportFilename(response.headers['content-disposition'] as string | undefined)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    },
  })
}
