import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'

export interface BackupEntry {
  filename: string
  file_size: number
  created_at: string
}

export interface CreateBackupResponse {
  success: boolean
  filename: string
  file_size: number
  created_at: string
}

export function useCreateBackup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const res = await api.post<CreateBackupResponse>('/admin/backup')
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['backups'] })
    },
  })
}

export function useBackups() {
  return useQuery({
    queryKey: ['backups'],
    queryFn: async () => {
      const res = await api.get<BackupEntry[]>('/admin/backups')
      return res.data
    },
  })
}

export async function downloadBackup(filename: string) {
  const response = await api.get(`/admin/backups/${encodeURIComponent(filename)}/download`, {
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export function useDeleteBackup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (filename: string) => {
      const res = await api.delete(`/admin/backups/${encodeURIComponent(filename)}`)
      return res.data as { success: boolean }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['backups'] })
    },
  })
}
