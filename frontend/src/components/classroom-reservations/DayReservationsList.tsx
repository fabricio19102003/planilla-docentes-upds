import type { ClassroomReservation } from '@/api/hooks/useClassroomReservations'
import { EmptyState } from '@/components/shared/EmptyState'
import { Badge } from '@/components/ui/badge'
import { sortDayReservations } from '@/lib/classroomReservationsGrid'

/** Text alternative to the grid: the day's reservations in start order. */
export function DayReservationsList({ reservations }: { reservations: ClassroomReservation[] }) {
  if (reservations.length === 0) {
    return <EmptyState title="Sin reservas este día" description="Ningún docente reservó un aula o laboratorio para esta fecha." />
  }

  return (
    <ol className="divide-y rounded-lg border" aria-label="Reservas del día">
      {sortDayReservations(reservations).map((reservation) => (
        <li key={reservation.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-sm">
          <span className="w-28 font-medium tabular-nums">{reservation.start_time} – {reservation.end_time}</span>
          <span className="min-w-0 flex-1">
            <span className="font-medium">{reservation.teacher_name}</span>
            <span className="text-muted-foreground"> · CI {reservation.teacher_ci}</span>
          </span>
          <span className="flex items-center gap-2">
            {reservation.classroom.name}
            {reservation.classroom.classroom_type === 'laboratory' && <Badge variant="info">Laboratorio</Badge>}
          </span>
          <span className="text-muted-foreground">{reservation.academic_periods} {reservation.academic_periods === 1 ? 'período' : 'períodos'}</span>
        </li>
      ))}
    </ol>
  )
}
