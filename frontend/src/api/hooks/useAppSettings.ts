import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type { AppSettings, AppSettingsUpdate } from '@/api/types'

async function fetchSettings(): Promise<AppSettings> {
  const res = await api.get<AppSettings>('/admin/settings')
  return res.data
}

async function updateSettings(payload: AppSettingsUpdate): Promise<AppSettings> {
  const res = await api.put<AppSettings>('/admin/settings', payload)
  return res.data
}

export function useAppSettings() {
  return useQuery({
    queryKey: ['app-settings'],
    queryFn: fetchSettings,
  })
}

export function useUpdateAppSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateSettings,
    onSuccess: (data) => {
      // Overwrite the cached query with the fresh server response so the form
      // reflects the saved values immediately without a round-trip.
      qc.setQueryData(['app-settings'], data)
      void qc.invalidateQueries({ queryKey: ['app-settings'] })
    },
  })
}
