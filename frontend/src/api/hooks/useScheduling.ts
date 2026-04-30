import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import type {
  AcademicPeriodResponse,
  CreateAcademicPeriodPayload,
  RoomType,
  Equipment,
  Room,
  CreateRoomTypePayload,
  CreateEquipmentPayload,
  CreateRoomPayload,
} from '@/api/types'

export function useAcademicPeriods() {
  return useQuery({
    queryKey: ['scheduling', 'academic-periods'],
    queryFn: async () => {
      const res = await api.get<AcademicPeriodResponse[]>('/scheduling/academic-periods')
      return res.data
    },
  })
}

export function useCreateAcademicPeriod() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: CreateAcademicPeriodPayload) => {
      const res = await api.post<AcademicPeriodResponse>('/scheduling/academic-periods', payload)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling', 'academic-periods'] })
    },
  })
}

export function useActivateAcademicPeriod() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (periodId: number) => {
      const res = await api.post<AcademicPeriodResponse>(`/scheduling/academic-periods/${periodId}/activate`)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling', 'academic-periods'] })
    },
  })
}

export function useRoomTypes() {
  return useQuery({
    queryKey: ['scheduling', 'room-types'],
    queryFn: async () => {
      const res = await api.get<RoomType[]>('/scheduling/rooms/types')
      return res.data
    },
  })
}

export function useCreateRoomType() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: CreateRoomTypePayload) => {
      const res = await api.post<RoomType>('/scheduling/rooms/types', payload)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling', 'room-types'] })
    },
  })
}

export function useEquipment() {
  return useQuery({
    queryKey: ['scheduling', 'equipment'],
    queryFn: async () => {
      const res = await api.get<Equipment[]>('/scheduling/rooms/equipment')
      return res.data
    },
  })
}

export function useCreateEquipment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: CreateEquipmentPayload) => {
      const res = await api.post<Equipment>('/scheduling/rooms/equipment', payload)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling', 'equipment'] })
    },
  })
}

export function useRooms() {
  return useQuery({
    queryKey: ['scheduling', 'rooms'],
    queryFn: async () => {
      const res = await api.get<Room[]>('/scheduling/rooms')
      return res.data
    },
  })
}

export function useCreateRoom() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: CreateRoomPayload) => {
      const res = await api.post<Room>('/scheduling/rooms', payload)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['scheduling', 'rooms'] })
    },
  })
}
