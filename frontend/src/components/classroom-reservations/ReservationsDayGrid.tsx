import type { ClassroomReservation, ReservableClassroom } from '@/api/hooks/useClassroomReservations'
import {
  GRID_DAY_END,
  GRID_DAY_START,
  blockPosition,
  groupReservationsByRoom,
  gridHourMarks,
} from '@/lib/classroomReservationsGrid'
import { toMinutes } from '@/lib/classroomReservations'
import { cn } from '@/lib/utils'

const PIXELS_PER_MINUTE = 1.3
const COMPACT_MINUTES = 40
const GRID_HEIGHT = ((toMinutes(GRID_DAY_END) ?? 0) - (toMinutes(GRID_DAY_START) ?? 0)) * PIXELS_PER_MINUTE

function reservationTitle(reservation: ClassroomReservation): string {
  return [
    reservation.teacher_name,
    `${reservation.start_time}–${reservation.end_time} · ${reservation.academic_periods} ${reservation.academic_periods === 1 ? 'período' : 'períodos'}`,
    `Aula: ${reservation.classroom.name}`,
  ].join('\n')
}

function blockTone(reservation: ClassroomReservation): string {
  return reservation.classroom.classroom_type === 'laboratory'
    ? 'border-info/50 bg-info/12 text-info-foreground'
    : 'border-primary/40 bg-primary/10 text-foreground'
}

interface ReservationsDayGridProps {
  rooms: ReservableClassroom[]
  reservations: ClassroomReservation[]
  label: string
}

export function ReservationsDayGrid({ rooms, reservations, label }: ReservationsDayGridProps) {
  const byRoom = groupReservationsByRoom(reservations)
  const marks = gridHourMarks()

  return (
    <div className="overflow-x-auto rounded-xl border bg-card" role="region" aria-label={label} tabIndex={0}>
      <div className="grid" style={{ gridTemplateColumns: `4rem repeat(${rooms.length}, minmax(9rem, 1fr))`, minWidth: `${4 + rooms.length * 9}rem` }}>
        <div className="sticky left-0 z-20 border-b bg-muted" />
        {rooms.map((room) => (
          <div key={room.id} className="border-b border-l bg-muted/40 px-2 py-2 text-center" title={`${room.name} · capacidad ${room.capacity ?? '—'}`}>
            <p className="truncate text-xs font-semibold uppercase tracking-wide text-muted-foreground">{room.name}</p>
            {room.classroom_type === 'laboratory' && <p className="text-[11px] text-info-foreground">Laboratorio</p>}
          </div>
        ))}

        <div className="sticky left-0 z-10 border-r bg-card" style={{ height: GRID_HEIGHT }} aria-hidden="true">
          {marks.map((mark) => (
            <span key={mark.time} className="absolute right-2 -translate-y-1/2 text-[11px] tabular-nums text-muted-foreground" style={{ top: `${mark.top}%` }}>{mark.time}</span>
          ))}
        </div>
        {rooms.map((room) => (
          <div key={room.id} className="relative border-l" style={{ height: GRID_HEIGHT }}>
            {marks.map((mark) => (
              <div key={mark.time} aria-hidden="true" className="absolute inset-x-0 border-t border-border" style={{ top: `${mark.top}%` }} />
            ))}
            <ul aria-label={`Reservas de ${room.name}`}>
              {(byRoom.get(room.id) ?? []).map((reservation) => {
                const { top, height } = blockPosition(reservation.start_time, reservation.end_time)
                const minutes = (toMinutes(reservation.end_time) ?? 0) - (toMinutes(reservation.start_time) ?? 0)
                return (
                  <li
                    key={reservation.id}
                    title={reservationTitle(reservation)}
                    className={cn('absolute inset-x-1 overflow-hidden rounded-md border border-l-4 px-1.5 py-1 text-[11px] leading-tight shadow-sm', blockTone(reservation))}
                    style={{ top: `${top}%`, height: `calc(${height}% - 2px)` }}
                  >
                    <p className="truncate font-semibold">{reservation.teacher_name}</p>
                    <p className={cn('tabular-nums opacity-80', minutes < COMPACT_MINUTES && 'hidden')}>{reservation.start_time}–{reservation.end_time}</p>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
