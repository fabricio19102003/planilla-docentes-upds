import type { ScheduleResponse } from './api'

export const collidingMondaySchedule: ScheduleResponse = {
  teacher_name: 'E2E Teacher',
  designation_count: 2,
  subject_count: 2,
  group_count: 2,
  total_weekly_hours: 4,
  designations: [
    {
      subject: 'Anatomy I',
      semester: 'First semester',
      group_code: 'M1',
      weekly_hours: 2,
      monthly_hours: 8,
      schedule: [
        {
          dia: 'Lunes',
          hora_inicio: '08:00',
          hora_fin: '09:30',
          horas_academicas: 2,
        },
      ],
    },
    {
      subject: 'Physiology I',
      semester: 'First semester',
      group_code: 'M2',
      weekly_hours: 2,
      monthly_hours: 8,
      schedule: [
        {
          dia: 'Lunes',
          hora_inicio: '08:00',
          hora_fin: '09:30',
          horas_academicas: 2,
        },
      ],
    },
  ],
}
