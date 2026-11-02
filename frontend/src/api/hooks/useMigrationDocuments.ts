import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type { MigrationDocumentType, MigrationStatus } from '@/lib/migrationDocumentsState'

const root = '/admin/migration-documents'
const key = ['migration-documents'] as const

export interface TypeChanges {
  name?: string
  requires_expiry?: boolean
  active?: boolean
  position?: number
}

export interface DocumentInput {
  expires_on: string | null
  notes: string | null
}

// Recorded documents change the "regularizado" badge of the re-enrollment inbox too.
function useInvalidate() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: key })
    void queryClient.invalidateQueries({ queryKey: ['reenrollment'] })
  }
}

export function useMigrationDocumentTypes() {
  return useQuery({
    queryKey: [...key, 'types'],
    queryFn: async () => (await api.get<MigrationDocumentType[]>(`${root}/types`)).data,
  })
}

export function useSaveMigrationDocumentType() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async (input: { id?: number; changes: TypeChanges }) =>
      input.id === undefined
        ? (await api.post<MigrationDocumentType>(`${root}/types`, input.changes)).data
        : (await api.put<MigrationDocumentType>(`${root}/types/${input.id}`, input.changes)).data,
    onSuccess: invalidate,
  })
}

export function useDeactivateMigrationDocumentType() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async (id: number) => (await api.post<MigrationDocumentType>(`${root}/types/${id}/deactivate`)).data,
    onSuccess: invalidate,
  })
}

export function useStudentMigrationDocuments(studentId: number) {
  return useQuery({
    queryKey: [...key, 'student', studentId],
    queryFn: async () => (await api.get<MigrationStatus>(`${root}/students/${studentId}`)).data,
  })
}

export function useSaveStudentDocument(studentId: number) {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async ({ typeId, payload }: { typeId: number; payload: DocumentInput }) =>
      (await api.put<MigrationStatus>(`${root}/students/${studentId}/documents/${typeId}`, payload)).data,
    onSuccess: invalidate,
  })
}

export function useRemoveStudentDocument(studentId: number) {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async (typeId: number) =>
      (await api.delete<MigrationStatus>(`${root}/students/${studentId}/documents/${typeId}`)).data,
    onSuccess: invalidate,
  })
}
