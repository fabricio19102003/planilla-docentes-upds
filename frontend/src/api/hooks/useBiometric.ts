import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type {
  BiometricUpload,
  BiometricUploadResult,
  DesignationUploadResponse,
  UploadBiometricPayload,
  UploadDesignationsPayload,
} from '@/api/types'

async function fetchUploadHistory() {
  const response = await api.get<BiometricUpload[]>('/uploads/history')

  return response.data
}

async function uploadBiometric(payload: UploadBiometricPayload) {
  const formData = new FormData()
  formData.append('file', payload.file)
  formData.append('month', String(payload.month))
  formData.append('year', String(payload.year))

  const response = await api.post<BiometricUploadResult>('/uploads/biometric', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (event) => {
      if (!event.total) {
        return
      }

      payload.onProgress?.(Math.round((event.loaded * 100) / event.total))
    },
  })

  return response.data
}

async function uploadDesignations(payload: UploadDesignationsPayload) {
  const formData = new FormData()
  formData.append('file', payload.file)

  const response = await api.post<DesignationUploadResponse>('/uploads/designations', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (event) => {
      if (!event.total) {
        return
      }

      payload.onProgress?.(Math.round((event.loaded * 100) / event.total))
    },
  })

  return response.data
}

export function useUploadHistory() {
  return useQuery({
    queryKey: ['upload-history'],
    queryFn: fetchUploadHistory,
  })
}

export function useUploadBiometric() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: uploadBiometric,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['upload-history'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] })
    },
  })
}

export function useUploadDesignations() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: uploadDesignations,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['teachers'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] })
    },
  })
}
