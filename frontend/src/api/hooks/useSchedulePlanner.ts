import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import type {
  AcademicScheduleAssignment,
  AcademicScheduleBlock,
  AcademicScheduleDraft,
  AcademicSchedulePublication,
  CompatibleScheduleTeachersPage,
  SchedulePublicationPreview,
  ScheduleWorkloadResponse,
} from '@/api/types'

const root = '/admin/academic-management/schedule-drafts'
const publicationsRoot = '/admin/academic-management/schedule-publications'

export function useScheduleDrafts() {
  return useQuery({
    queryKey: ['academic-management', 'schedule-drafts'],
    queryFn: async () => (await api.get<AcademicScheduleDraft[]>(root)).data,
  })
}

export function useScheduleBlocks(draftId: number | null) {
  return useQuery({
    queryKey: ['academic-management', 'schedule-drafts', draftId, 'blocks'],
    queryFn: async () => (await api.get<AcademicScheduleBlock[]>(`${root}/${draftId}/blocks`)).data,
    enabled: draftId !== null,
  })
}

export function useSaveScheduleDraft() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, payload }: { id?: number; payload: Record<string, unknown> }) => (
      id ? await api.put<AcademicScheduleDraft>(`${root}/${id}`, payload) : await api.post<AcademicScheduleDraft>(root, payload)
    ).data,
    onSuccess: () => void client.invalidateQueries({ queryKey: ['academic-management', 'schedule-drafts'] }),
  })
}

export function useArchiveScheduleDraft() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => (await api.post<AcademicScheduleDraft>(`${root}/${id}/archive`)).data,
    onSuccess: () => void client.invalidateQueries({ queryKey: ['academic-management', 'schedule-drafts'] }),
  })
}

export function useSaveScheduleBlock(draftId: number | null) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, payload }: { id?: number; payload: Record<string, unknown> }) => {
      if (draftId === null) throw new Error('Debe seleccionar un borrador.')
      return (id
        ? await api.put<AcademicScheduleBlock>(`${root}/${draftId}/blocks/${id}`, payload)
        : await api.post<AcademicScheduleBlock>(`${root}/${draftId}/blocks`, payload)
      ).data
    },
    onSuccess: () => void client.invalidateQueries({
      queryKey: ['academic-management', 'schedule-drafts', draftId, 'blocks'],
    }),
  })
}

export function useDeleteScheduleBlock(draftId: number | null) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      if (draftId === null) throw new Error('Debe seleccionar un borrador.')
      await api.delete(`${root}/${draftId}/blocks/${id}`)
    },
    onSuccess: () => void client.invalidateQueries({
      queryKey: ['academic-management', 'schedule-drafts', draftId, 'blocks'],
    }),
  })
}

export function useScheduleAssignmentHistories(draftId: number | null, blockIds: number[]) {
  const results = useQueries({
    queries: blockIds.map((blockId) => ({
      queryKey: ['academic-management', 'schedule-drafts', draftId, 'blocks', blockId, 'assignments'],
      queryFn: async () => (await api.get<AcademicScheduleAssignment[]>(
        `${root}/${draftId}/blocks/${blockId}/assignments`,
      )).data,
      enabled: draftId !== null,
    })),
  })
  return {
    data: Object.fromEntries(blockIds.map((blockId, index) => [blockId, results[index]?.data ?? []])) as Record<number, AcademicScheduleAssignment[]>,
    isLoading: results.some((result) => result.isLoading),
    isError: results.some((result) => result.isError),
  }
}

export function useCompatibleScheduleTeachers(
  draftId: number | null,
  blockId: number | null,
  effectiveFrom: string,
  effectiveTo: string,
  search: string,
  page: number,
) {
  return useQuery({
    queryKey: ['academic-management', 'compatible-schedule-teachers', draftId, blockId, effectiveFrom, effectiveTo, search, page],
    queryFn: async () => (await api.get<CompatibleScheduleTeachersPage>(
      `${root}/${draftId}/blocks/${blockId}/compatible-teachers`,
      { params: { effective_from: effectiveFrom, effective_to: effectiveTo || undefined, search: search || undefined, page, per_page: 20 } },
    )).data,
    enabled: draftId !== null && blockId !== null && Boolean(effectiveFrom),
  })
}

export function useSaveScheduleAssignment(draftId: number | null, blockId: number | null) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async ({ replace, payload }: { replace: boolean; payload: Record<string, unknown> }) => {
      if (draftId === null || blockId === null) throw new Error('Debe seleccionar un bloque.')
      const suffix = replace ? '/replace' : ''
      return (await api.post<AcademicScheduleAssignment>(
        `${root}/${draftId}/blocks/${blockId}/assignments${suffix}`, payload,
      )).data
    },
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: ['academic-management', 'schedule-drafts', draftId, 'blocks', blockId, 'assignments'],
      })
      void client.invalidateQueries({ queryKey: ['academic-management', 'schedule-workload', draftId] })
      void client.invalidateQueries({ queryKey: ['academic-management', 'compatible-schedule-teachers'] })
    },
  })
}

export function useCorrectScheduleAssignment(draftId: number | null, blockId: number | null) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Record<string, unknown> }) => {
      if (draftId === null || blockId === null) throw new Error('Debe seleccionar un bloque.')
      return (await api.put<AcademicScheduleAssignment>(
        `${root}/${draftId}/blocks/${blockId}/assignments/${id}`, payload,
      )).data
    },
    onSuccess: () => void client.invalidateQueries({
      queryKey: ['academic-management', 'schedule-drafts', draftId, 'blocks', blockId, 'assignments'],
    }),
  })
}

export function useDeleteScheduleAssignment(draftId: number | null, blockId: number | null) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      if (draftId === null || blockId === null) throw new Error('Debe seleccionar un bloque.')
      await api.delete(`${root}/${draftId}/blocks/${blockId}/assignments/${id}`)
    },
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: ['academic-management', 'schedule-drafts', draftId, 'blocks', blockId, 'assignments'],
      })
      void client.invalidateQueries({ queryKey: ['academic-management', 'schedule-workload', draftId] })
    },
  })
}

export function useScheduleWorkload(draftId: number | null, referenceDate: string) {
  return useQuery({
    queryKey: ['academic-management', 'schedule-workload', draftId, referenceDate],
    queryFn: async () => (await api.get<ScheduleWorkloadResponse>(
      `${root}/${draftId}/workload`, { params: { reference_date: referenceDate } },
    )).data,
    enabled: draftId !== null && Boolean(referenceDate),
  })
}

export function useSchedulePublications() {
  return useQuery({
    queryKey: ['academic-management', 'schedule-publications'],
    queryFn: async () => (await api.get<AcademicSchedulePublication[]>(publicationsRoot)).data,
  })
}

export function usePreviewSchedulePublication(draftId: number | null) {
  return useMutation({
    mutationFn: async (effectiveFrom: string) => {
      if (draftId === null) throw new Error('Debe seleccionar un borrador.')
      return (await api.post<SchedulePublicationPreview>(
        `${root}/${draftId}/publication-preview`, { effective_from: effectiveFrom },
      )).data
    },
  })
}

export function usePublishScheduleDraft(draftId: number | null) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async ({ effectiveFrom, digest }: { effectiveFrom: string; digest: string }) => {
      if (draftId === null) throw new Error('Debe seleccionar un borrador.')
      return (await api.post<AcademicSchedulePublication>(`${root}/${draftId}/publish`, {
        effective_from: effectiveFrom, preview_digest: digest,
      })).data
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['academic-management', 'schedule-drafts'] })
      void client.invalidateQueries({ queryKey: ['academic-management', 'schedule-publications'] })
    },
  })
}

export function useCloneSchedulePublication() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async ({ publicationId, name }: { publicationId: number; name: string }) => (
      await api.post<AcademicScheduleDraft>(`${publicationsRoot}/${publicationId}/clone`, { name })
    ).data,
    onSuccess: () => void client.invalidateQueries({
      queryKey: ['academic-management', 'schedule-drafts'],
    }),
  })
}
