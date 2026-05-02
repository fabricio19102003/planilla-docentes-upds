import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface Career {
  id: number
  code: string
  name: string
  description: string | null
  is_active: boolean
  semester_count: number
  subject_count: number
}

export interface CareerWithSemesters extends Career {
  semesters: SemesterWithSubjects[]
}

export interface Semester {
  id: number
  career_id: number
  number: number
  name: string
  is_active: boolean
  subject_count: number
}

export interface SemesterWithSubjects extends Semester {
  subjects: Subject[]
}

export interface Subject {
  id: number
  semester_id: number
  code: string | null
  name: string
  theoretical_hours: number
  practical_hours: number
  credits: number
  is_elective: boolean
  is_active: boolean
}

export interface CurriculumImportResponse {
  career_id: number
  career_code: string
  semesters_created: number
  semesters_existing: number
  subjects_created: number
  subjects_updated: number
  warnings: string[]
}

// ─── Career hooks ─────────────────────────────────────────────────────────────

export function useCareers(activeOnly = true) {
  return useQuery<Career[]>({
    queryKey: ['scheduling', 'careers', activeOnly],
    queryFn: async () => {
      const res = await api.get<Career[]>('/scheduling/careers', {
        params: { active_only: activeOnly },
      })
      return res.data
    },
  })
}

export function useCareer(id: number, enabled = true) {
  return useQuery<CareerWithSemesters>({
    queryKey: ['scheduling', 'career', id],
    queryFn: async () => {
      const res = await api.get<CareerWithSemesters>(`/scheduling/careers/${id}`)
      return res.data
    },
    enabled,
  })
}

export function useCreateCareer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: { code: string; name: string; description?: string }) => {
      const res = await api.post('/scheduling/careers', data)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling', 'careers'] })
    },
  })
}

export function useUpdateCareer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      ...data
    }: {
      id: number
      name?: string
      description?: string
      is_active?: boolean
    }) => {
      const res = await api.put(`/scheduling/careers/${id}`, data)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling'] })
    },
  })
}

export function useDeleteCareer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/scheduling/careers/${id}`)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling'] })
    },
  })
}

export function useImportCurriculum() {
  const qc = useQueryClient()
  return useMutation<CurriculumImportResponse, Error, object>({
    mutationFn: async (data) => {
      const res = await api.post<CurriculumImportResponse>(
        '/scheduling/careers/import-curriculum',
        data,
      )
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling'] })
    },
  })
}

// ─── Semester hooks ───────────────────────────────────────────────────────────

export function useSemesters(careerId: number, enabled = true) {
  return useQuery<Semester[]>({
    queryKey: ['scheduling', 'semesters', careerId],
    queryFn: async () => {
      const res = await api.get<Semester[]>('/scheduling/semesters', {
        params: { career_id: careerId },
      })
      return res.data
    },
    enabled,
  })
}

export function useCreateSemester() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: { career_id: number; number: number; name: string }) => {
      const res = await api.post('/scheduling/semesters', data)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling'] })
    },
  })
}

export function useUpdateSemester() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...data }: { id: number; name?: string; is_active?: boolean }) => {
      const res = await api.put(`/scheduling/semesters/${id}`, data)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling'] })
    },
  })
}

export function useDeleteSemester() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/scheduling/semesters/${id}`)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling'] })
    },
  })
}

// ─── Subject hooks ────────────────────────────────────────────────────────────

export function useSubjects(semesterId: number, enabled = true) {
  return useQuery<Subject[]>({
    queryKey: ['scheduling', 'subjects', semesterId],
    queryFn: async () => {
      const res = await api.get<Subject[]>('/scheduling/subjects', {
        params: { semester_id: semesterId },
      })
      return res.data
    },
    enabled,
  })
}

export function useCreateSubject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      semester_id: number
      code?: string
      name: string
      theoretical_hours?: number
      practical_hours?: number
      credits?: number
      is_elective?: boolean
    }) => {
      const res = await api.post('/scheduling/subjects', data)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling'] })
    },
  })
}

export function useUpdateSubject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      ...data
    }: {
      id: number
      code?: string
      name?: string
      theoretical_hours?: number
      practical_hours?: number
      credits?: number
      is_elective?: boolean
      is_active?: boolean
    }) => {
      const res = await api.put(`/scheduling/subjects/${id}`, data)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling'] })
    },
  })
}

export function useDeleteSubject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/scheduling/subjects/${id}`)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling'] })
    },
  })
}

export function useSearchSubjects(query: string, careerId?: number) {
  return useQuery<Subject[]>({
    queryKey: ['scheduling', 'subjects-search', query, careerId],
    queryFn: async () => {
      const params: Record<string, string | number> = { q: query }
      if (careerId) params.career_id = careerId
      const res = await api.get<Subject[]>('/scheduling/subjects/search', { params })
      return res.data
    },
    enabled: query.length >= 2,
  })
}
