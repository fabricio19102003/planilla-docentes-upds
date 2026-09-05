import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type {
  BiometricUpload,
  BiometricUploadResult,
  DesignationImportPreview,
  DesignationUploadResponse,
  TeacherProfileImportPreview,
  TeacherProfileImportResult,
  UploadBiometricPayload,
  UploadDesignationsPayload,
} from '@/api/types'

export interface BiometricDateRange {
  has_data: boolean
  start_date: string | null
  end_date: string | null
  record_count: number
  teacher_count: number
  days_with_data: number
  upload_filename: string
  upload_date: string
  suggested_start: string | null
  suggested_end: string | null
  message: string
}

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

function designationForm(payload: UploadDesignationsPayload) {
  const formData = new FormData()
  formData.append('file', payload.file)

  return formData
}

async function previewDesignations(payload: UploadDesignationsPayload) {
  const url = `/uploads/designations/preview?academic_period=${encodeURIComponent(payload.academic_period)}`
  const response = await api.post<DesignationImportPreview>(url, designationForm(payload), {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (event.total) payload.onProgress?.(Math.round((event.loaded * 100) / event.total))
    },
  })
  return response.data
}

async function uploadDesignations(payload: UploadDesignationsPayload) {
  if (!payload.confirmation_digest) throw new Error('La confirmación de la vista previa es obligatoria.')
  const url = `/uploads/designations?academic_period=${encodeURIComponent(payload.academic_period)}&confirmation_digest=${encodeURIComponent(payload.confirmation_digest)}`

  const response = await api.post<DesignationUploadResponse>(url, designationForm(payload), {
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

export function usePreviewDesignations() {
  return useMutation({ mutationFn: previewDesignations })
}

interface TeacherProfileImportPayload {
  file: File
  academic_period: string
  confirmation_digest?: string
}

function teacherProfileForm(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return formData
}

async function previewTeacherProfiles(payload: TeacherProfileImportPayload) {
  const response = await api.post<TeacherProfileImportPreview>(
    `/teachers/import/preview?academic_period=${encodeURIComponent(payload.academic_period)}`,
    teacherProfileForm(payload.file),
    { headers: { 'Content-Type': 'multipart/form-data' } },
  )
  return response.data
}

async function importTeacherProfiles(payload: TeacherProfileImportPayload) {
  if (!payload.confirmation_digest) throw new Error('La confirmación de la vista previa es obligatoria.')
  const response = await api.post<TeacherProfileImportResult>(
    `/teachers/import?academic_period=${encodeURIComponent(payload.academic_period)}&confirmation_digest=${encodeURIComponent(payload.confirmation_digest)}`,
    teacherProfileForm(payload.file),
    {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    },
  )

  return response.data
}

export function usePreviewTeacherProfiles() {
  return useMutation({ mutationFn: previewTeacherProfiles })
}

export function useImportTeacherProfiles() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: importTeacherProfiles,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['teachers'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] })
    },
  })
}

export function useBiometricDateRange(month: number, year: number) {
  return useQuery({
    queryKey: ['biometric-date-range', month, year],
    queryFn: async () => {
      const res = await api.get<BiometricDateRange>(`/uploads/biometric/date-range?month=${month}&year=${year}`)
      return res.data
    },
    enabled: month > 0 && year > 0,
  })
}
