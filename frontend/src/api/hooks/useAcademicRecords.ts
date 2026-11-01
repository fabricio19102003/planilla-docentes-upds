import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import {
  gzipCsv,
  studentQueryParams,
  type AcademicTerm,
  type CurriculumPlan,
  type CurriculumPlanSummary,
  type ImportPreview,
  type ImportReceipt,
  type ImportResult,
  type StudentDetail,
  type StudentFilters,
  type StudentList,
} from '@/lib/academicRecordsState'

const root = '/admin/academic-records'
const key = ['academic-records'] as const

export function useCurricula() {
  return useQuery({
    queryKey: [...key, 'curricula'],
    queryFn: async () => (await api.get<CurriculumPlanSummary[]>(`${root}/curricula`)).data,
  })
}

export function useCurriculum(planId: number | undefined) {
  return useQuery({
    queryKey: [...key, 'curricula', planId],
    queryFn: async () => (await api.get<CurriculumPlan>(`${root}/curricula/${planId}`)).data,
    enabled: planId !== undefined,
  })
}

export function useLoadDefaultCurriculum() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => (await api.post<CurriculumPlan>(`${root}/curricula/default/load`)).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: [...key, 'curricula'] }),
  })
}

export function useAcademicTerms() {
  return useQuery({
    queryKey: [...key, 'terms'],
    queryFn: async () => (await api.get<AcademicTerm[]>(`${root}/terms`)).data,
  })
}

export function useStudents(filters: StudentFilters) {
  return useQuery({
    queryKey: [...key, 'students', filters],
    queryFn: async () => (await api.get<StudentList>(`${root}/students`, { params: studentQueryParams(filters) })).data,
    placeholderData: (previous) => previous,
  })
}

export function useStudent(studentId: number) {
  return useQuery({
    queryKey: [...key, 'students', 'detail', studentId],
    queryFn: async () => (await api.get<StudentDetail>(`${root}/students/${studentId}`)).data,
    enabled: Number.isInteger(studentId) && studentId > 0,
  })
}

export function useImportReceipts() {
  return useQuery({
    queryKey: [...key, 'imports'],
    queryFn: async () => (await api.get<ImportReceipt[]>(`${root}/imports`)).data,
  })
}

async function uploadForm(file: File, expectedSha256?: string) {
  const formData = new FormData()
  formData.append('file', await gzipCsv(file))
  if (expectedSha256) formData.append('expected_sha256', expectedSha256)
  return formData
}

const multipart = { headers: { 'Content-Type': 'multipart/form-data' } }

export function usePreviewImport() {
  return useMutation({
    mutationFn: async (file: File) =>
      (await api.post<ImportPreview>(`${root}/imports/preview`, await uploadForm(file), multipart)).data,
  })
}

export function useApplyImport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ file, sha256 }: { file: File; sha256: string }) =>
      (await api.post<ImportResult>(`${root}/imports/apply`, await uploadForm(file, sha256), multipart)).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: key }),
  })
}
