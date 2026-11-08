import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { BusyRange } from '@/lib/classroomReservations'

export type ClassroomType = 'classroom' | 'laboratory'

export interface ReservableClassroom {
  id: number
  code: string
  name: string
  capacity: number | null
  classroom_type: ClassroomType
}

export interface ClassroomAvailability {
  classroom: ReservableClassroom
  date: string
  academic_hour_minutes: number
  day_start: string
  day_end: string
  busy: BusyRange[]
}

export interface ClassroomDayRoom {
  classroom: ReservableClassroom
  busy: BusyRange[]
  free_minutes: number
}

export interface ClassroomDay {
  date: string
  academic_hour_minutes: number
  day_start: string
  day_end: string
  rooms: ClassroomDayRoom[]
}

export interface ClassroomReservation {
  id: number
  classroom: ReservableClassroom
  date: string
  start_time: string
  end_time: string
  academic_periods: number
  status: 'confirmed' | 'cancelled'
  teacher_ci: string
  teacher_name: string
}

export interface CreateReservationInput {
  classroom_id: number
  date: string
  start_time: string
  periods: number
}

export interface AdminClassroomReservations {
  classrooms: ReservableClassroom[]
  reservations: ClassroomReservation[]
}

const PORTAL_KEY = 'classroom-reservations'
const ADMIN_KEY = 'admin-classroom-reservations'
const PORTAL_PATH = '/portal/classroom-reservations'

export function useReservableClassrooms() {
  return useQuery({
    queryKey: [PORTAL_KEY, 'classrooms'],
    queryFn: async () => {
      const res = await api.get<ReservableClassroom[]>(`${PORTAL_PATH}/classrooms`)
      return res.data
    },
  })
}

export function useClassroomAvailability(classroomId: number | null, date: string) {
  return useQuery({
    queryKey: [PORTAL_KEY, 'availability', classroomId, date],
    queryFn: async () => {
      const res = await api.get<ClassroomAvailability>(`${PORTAL_PATH}/availability`, {
        params: { classroom_id: classroomId, date },
      })
      return res.data
    },
    enabled: classroomId !== null && date !== '',
  })
}

export function useClassroomDay(date: string) {
  return useQuery({
    queryKey: [PORTAL_KEY, 'day', date],
    queryFn: async () => {
      const res = await api.get<ClassroomDay>(`${PORTAL_PATH}/day`, { params: { date } })
      return res.data
    },
    enabled: date !== '',
  })
}

export function useMyClassroomReservations() {
  return useQuery({
    queryKey: [PORTAL_KEY, 'mine'],
    queryFn: async () => {
      const res = await api.get<ClassroomReservation[]>(`${PORTAL_PATH}/mine`)
      return res.data
    },
  })
}

export function useCreateClassroomReservation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (input: CreateReservationInput) => {
      const res = await api.post<ClassroomReservation>(PORTAL_PATH, input)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [PORTAL_KEY] })
      void qc.invalidateQueries({ queryKey: [ADMIN_KEY] })
    },
    // A 409/422 may mean the day changed under the teacher: show fresh ranges next to the message.
    onError: () => {
      void qc.invalidateQueries({ queryKey: [PORTAL_KEY, 'availability'] })
      void qc.invalidateQueries({ queryKey: [PORTAL_KEY, 'day'] })
    },
  })
}

export function useCancelClassroomReservation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await api.post<ClassroomReservation>(`${PORTAL_PATH}/${id}/cancel`)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [PORTAL_KEY] })
      void qc.invalidateQueries({ queryKey: [ADMIN_KEY] })
    },
  })
}

export function useAdminClassroomReservations(dateFrom: string, dateTo: string) {
  return useQuery({
    queryKey: [ADMIN_KEY, dateFrom, dateTo],
    queryFn: async () => {
      const res = await api.get<AdminClassroomReservations>('/admin/classroom-reservations', {
        params: { date_from: dateFrom, date_to: dateTo },
      })
      return res.data
    },
    enabled: dateFrom !== '' && dateTo !== '',
  })
}
