import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { STUDENT_TOKEN_KEY, studentApi } from '@/api/studentClient'
import type { StudentDetail } from '@/lib/academicRecordsState'
import type { Eligibility, GroupOption, ReenrollmentRequest, ReenrollmentWindow } from '@/lib/reenrollmentState'

const key = ['student-portal'] as const

interface Session { access_token: string; must_change_password: boolean }
export type StudentProfile = StudentDetail['student'] & { must_change_password: boolean }
export interface StudentReenrollment {
  window: ReenrollmentWindow | null
  eligibility: Eligibility
  main_groups: GroupOption[]
  groups_by_semester: Record<string, GroupOption[]>
  request: ReenrollmentRequest | null
}

function useSession() {
  const queryClient = useQueryClient()
  return (session: Session) => {
    localStorage.setItem(STUDENT_TOKEN_KEY, session.access_token)
    void queryClient.invalidateQueries({ queryKey: key })
  }
}

export function useStudentLogin() {
  const save = useSession()
  return useMutation({
    mutationFn: async (payload: { document_number: string; password: string }) =>
      (await studentApi.post<Session>('/auth/login', payload)).data,
    onSuccess: save,
  })
}

export function useStudentChangePassword() {
  const save = useSession()
  return useMutation({
    mutationFn: async (payload: { current_password: string; new_password: string }) =>
      (await studentApi.put<Session>('/auth/change-password', payload)).data,
    onSuccess: save,
  })
}

export function useStudentLogout() {
  const queryClient = useQueryClient()
  return () => {
    localStorage.removeItem(STUDENT_TOKEN_KEY)
    queryClient.removeQueries({ queryKey: key })
  }
}

export function useStudentMe() {
  return useQuery({
    queryKey: [...key, 'me'],
    queryFn: async () => (await studentApi.get<StudentProfile>('/me')).data,
    enabled: Boolean(localStorage.getItem(STUDENT_TOKEN_KEY)),
    retry: false,
  })
}

export function useStudentHistory() {
  return useQuery({
    queryKey: [...key, 'history'],
    queryFn: async () => (await studentApi.get<Pick<StudentDetail, 'history'>>('/history')).data.history,
  })
}

export function useStudentReenrollment() {
  return useQuery({
    queryKey: [...key, 'reenrollment'],
    queryFn: async () => (await studentApi.get<StudentReenrollment>('/reenrollment')).data,
  })
}

export function useSubmitReenrollment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: { main_group_id: number; items: { subject_code: string; group_id: number }[] }) =>
      (await studentApi.post<ReenrollmentRequest>('/reenrollment/request', payload)).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: [...key, 'reenrollment'] }),
  })
}
