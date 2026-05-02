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

// ─── Academic Period types ────────────────────────────────────────────────────

export interface AcademicPeriod {
  id: number
  code: string
  name: string
  year: number
  semester_number: number
  start_date: string
  end_date: string
  is_active: boolean
  status: 'planning' | 'active' | 'closed'
  group_count: number
}

export interface Shift {
  id: number
  code: string
  name: string
  start_time: string
  end_time: string
  display_order: number
}

export interface Group {
  id: number
  academic_period_id: number
  semester_id: number
  semester_name: string
  shift_id: number
  shift_code: string
  shift_name: string
  number: number
  code: string
  is_special: boolean
  student_count: number | null
  is_active: boolean
}

// ─── Period hooks ─────────────────────────────────────────────────────────────

export function usePeriods(status?: string) {
  return useQuery<AcademicPeriod[]>({
    queryKey: ['scheduling', 'periods', status],
    queryFn: async () => {
      const params: Record<string, string> = {}
      if (status) params.status = status
      const res = await api.get('/scheduling/periods', { params })
      return res.data
    },
  })
}

export function useActivePeriod() {
  return useQuery<AcademicPeriod | null>({
    queryKey: ['scheduling', 'periods', 'active'],
    queryFn: async () => {
      try {
        const res = await api.get('/scheduling/periods/active')
        return res.data
      } catch (e: unknown) {
        const axiosErr = e as { response?: { status?: number } }
        if (axiosErr?.response?.status === 404) return null
        throw e
      }
    },
  })
}

export function useCreatePeriod() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      code: string
      name: string
      year: number
      semester_number: number
      start_date: string
      end_date: string
    }) => {
      const res = await api.post('/scheduling/periods', data)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling', 'periods'] })
    },
  })
}

export function useUpdatePeriod() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      ...data
    }: {
      id: number
      name?: string
      start_date?: string
      end_date?: string
    }) => {
      const res = await api.put(`/scheduling/periods/${id}`, data)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling'] })
    },
  })
}

export function useActivatePeriod() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await api.post(`/scheduling/periods/${id}/activate`)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling'] })
    },
  })
}

export function useClosePeriod() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await api.post(`/scheduling/periods/${id}/close`)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling'] })
    },
  })
}

// ─── Shift hooks ──────────────────────────────────────────────────────────────

export function useShifts() {
  return useQuery<Shift[]>({
    queryKey: ['scheduling', 'shifts'],
    queryFn: async () => {
      const res = await api.get('/scheduling/shifts')
      return res.data
    },
  })
}

// ─── Group hooks ──────────────────────────────────────────────────────────────

export function useGroups(periodId: number, semesterId?: number) {
  return useQuery<Group[]>({
    queryKey: ['scheduling', 'groups', periodId, semesterId],
    queryFn: async () => {
      const params: Record<string, number> = { period_id: periodId }
      if (semesterId) params.semester_id = semesterId
      const res = await api.get('/scheduling/groups', { params })
      return res.data
    },
    enabled: periodId > 0,
  })
}

export function useCreateGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      academic_period_id: number
      semester_id: number
      shift_id: number
      number: number
      is_special?: boolean
      student_count?: number
    }) => {
      const res = await api.post('/scheduling/groups', data)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling', 'groups'] })
    },
  })
}

export function useCreateGroupsBulk() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      academic_period_id: number
      semester_id: number
      groups: object[]
    }) => {
      const res = await api.post('/scheduling/groups/bulk', data)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling', 'groups'] })
    },
  })
}

export function useUpdateGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      ...data
    }: {
      id: number
      student_count?: number
      is_active?: boolean
    }) => {
      const res = await api.put(`/scheduling/groups/${id}`, data)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling', 'groups'] })
    },
  })
}

export function useDeleteGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/scheduling/groups/${id}`)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling', 'groups'] })
    },
  })
}
