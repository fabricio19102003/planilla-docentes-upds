import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'

import { useAdminClassroomReservations } from '@/api/hooks/useClassroomReservations'
import { DayReservationsList } from '@/components/classroom-reservations/DayReservationsList'
import { ReservationsDayGrid } from '@/components/classroom-reservations/ReservationsDayGrid'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { SegmentedControl, SegmentedControlItem } from '@/components/ui/segmented-control'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateInBolivia, getTodayInBolivia } from '@/lib/boliviaDates'
import { filterRoomsByType, shiftDate, weekdayName, type RoomTypeFilter } from '@/lib/classroomReservationsGrid'
import { apiErrorMessage } from '@/lib/userCredentials'

const TYPE_FILTERS: { value: RoomTypeFilter; label: string }[] = [
  { value: 'all', label: 'Todas' },
  { value: 'classroom', label: 'Aulas' },
  { value: 'laboratory', label: 'Laboratorios' },
]

export function ClassroomReservationsAdminPage() {
  const [date, setDate] = useState(getTodayInBolivia())
  const [typeFilter, setTypeFilter] = useState<RoomTypeFilter>('all')
  const day = useAdminClassroomReservations(date, date)

  const rooms = filterRoomsByType(day.data?.classrooms ?? [], typeFilter)
  const visibleIds = new Set(rooms.map((room) => room.id))
  const reservations = (day.data?.reservations ?? []).filter((reservation) => visibleIds.has(reservation.classroom.id))
  const heading = `${weekdayName(date)} ${formatDateInBolivia(date)}`

  return (
    <div>
      <PageHeader
        title="Reservas de aulas"
        description="Reservas que los docentes hacen de aulas y laboratorios, por día y espacio."
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" size="icon" aria-label="Día anterior" onClick={() => setDate(shiftDate(date, -1))}><ChevronLeft aria-hidden="true" /></Button>
          <Button type="button" variant="outline" onClick={() => setDate(getTodayInBolivia())}>Hoy</Button>
          <Button type="button" variant="outline" size="icon" aria-label="Día siguiente" onClick={() => setDate(shiftDate(date, 1))}><ChevronRight aria-hidden="true" /></Button>
          <Input
            type="date"
            aria-label="Fecha"
            className="w-40"
            value={date}
            onChange={(event) => { if (event.target.value) setDate(event.target.value) }}
          />
        </div>
        <SegmentedControl aria-label="Tipo de espacio">
          {TYPE_FILTERS.map((filter) => (
            <SegmentedControlItem
              key={filter.value}
              aria-pressed={typeFilter === filter.value}
              data-pressed={typeFilter === filter.value ? '' : undefined}
              onClick={() => setTypeFilter(filter.value)}
            >
              {filter.label}
            </SegmentedControlItem>
          ))}
        </SegmentedControl>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="capitalize">{heading}</CardTitle>
          <CardDescription>
            {day.data ? `${reservations.length} ${reservations.length === 1 ? 'reserva' : 'reservas'} en ${rooms.length} ${rooms.length === 1 ? 'espacio' : 'espacios'}` : 'Cargando reservas...'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {day.isLoading && <Skeleton className="h-96 w-full rounded-lg" />}
          {day.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(day.error, 'No se pudieron cargar las reservas.')}</AlertTitle></Alert>}
          {day.data && rooms.length === 0 && (
            <EmptyState title="Sin espacios para mostrar" description="No hay aulas ni laboratorios activos para el filtro elegido." />
          )}
          {day.data && rooms.length > 0 && (
            <>
              <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-label="Leyenda">
                <li className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-primary/40" />Aula</li>
                <li className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-info/60" />Laboratorio</li>
              </ul>
              <ReservationsDayGrid rooms={rooms} reservations={reservations} label={`Reservas del ${heading}`} />
              <section aria-labelledby="day-reservations-heading" className="space-y-3">
                <h3 id="day-reservations-heading" className="text-sm font-semibold">Lista del día</h3>
                <DayReservationsList reservations={reservations} />
              </section>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
