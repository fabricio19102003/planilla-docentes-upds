import { FlaskConical } from 'lucide-react'
import { useMemo, useState } from 'react'

import { useClassroomAvailability, useReservableClassrooms } from '@/api/hooks/useClassroomReservations'
import { AvailabilityTimeline } from '@/components/classroom-reservations/AvailabilityTimeline'
import { MyReservations } from '@/components/classroom-reservations/MyReservations'
import { ReservationForm, type ReservationDraft } from '@/components/classroom-reservations/ReservationForm'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { getTodayInBolivia } from '@/lib/boliviaDates'
import { computeEndTime, rangeProblem } from '@/lib/classroomReservations'
import { apiErrorMessage } from '@/lib/userCredentials'

export function ClassroomReservationPage() {
  const today = getTodayInBolivia()
  const classrooms = useReservableClassrooms()
  const [classroomId, setClassroomId] = useState<number | null>(null)
  const [date, setDate] = useState(today)
  const [draft, setDraft] = useState<ReservationDraft>({ start: '', periods: 2 })

  const validDate = date >= today ? date : ''
  const availability = useClassroomAvailability(classroomId, validDate)
  const data = availability.data

  const roomItems = (classrooms.data ?? []).map((room) => ({
    value: String(room.id),
    label: `${room.name} · capacidad ${room.capacity ?? '—'}${room.classroom_type === 'laboratory' ? ' · Laboratorio' : ''}`,
  }))
  const selectedRoom = classrooms.data?.find((room) => room.id === classroomId)

  const endTime = data ? computeEndTime(draft.start, draft.periods, data.academic_hour_minutes) : null
  const problem = useMemo(
    () => (data && draft.start
      ? rangeProblem({ busy: data.busy, dayStart: data.day_start, dayEnd: data.day_end, start: draft.start, end: endTime })
      : null),
    [data, draft.start, endTime],
  )
  const selection = data && draft.start && endTime ? { start: draft.start, end: endTime, conflict: problem !== null } : null

  return (
    <div>
      <PageHeader
        title="Reservar aula"
        description="Consultá la disponibilidad de un aula o laboratorio y reservalo por períodos académicos. La reserva queda confirmada al instante."
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Aula y fecha</CardTitle>
              <CardDescription>Elegí el espacio y el día que necesitás.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_14rem]">
              <div className="space-y-1.5">
                <Label htmlFor="reservation-classroom">Aula o laboratorio</Label>
                {classrooms.isLoading ? <Skeleton className="h-9 w-full" /> : (
                  <Select
                    value={classroomId === null ? null : String(classroomId)}
                    items={roomItems}
                    onValueChange={(value) => { setClassroomId(value ? Number(value) : null); setDraft((current) => ({ ...current, start: '' })) }}
                  >
                    <SelectTrigger id="reservation-classroom"><SelectValue placeholder="Seleccionar aula..." /></SelectTrigger>
                    <SelectPopup>
                      {roomItems.map((item) => <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>)}
                    </SelectPopup>
                  </Select>
                )}
                {classrooms.isError && <p className="text-sm text-destructive" role="alert">{apiErrorMessage(classrooms.error, 'No se pudieron cargar las aulas.')}</p>}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="reservation-date">Fecha</Label>
                <Input
                  id="reservation-date"
                  type="date"
                  min={today}
                  value={date}
                  aria-invalid={validDate === ''}
                  onChange={(event) => { setDate(event.target.value); setDraft((current) => ({ ...current, start: '' })) }}
                />
                {validDate === '' && <p className="text-sm text-destructive" role="alert">Elegí hoy o una fecha futura.</p>}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex flex-wrap items-center gap-2">
                Disponibilidad del día
                {selectedRoom?.classroom_type === 'laboratory' && <Badge variant="info"><FlaskConical className="size-3" />Laboratorio</Badge>}
              </CardTitle>
              <CardDescription>
                {data ? `${data.classroom.name} · capacidad ${data.classroom.capacity ?? '—'} · ${data.day_start} a ${data.day_end}` : 'Los tramos libres y ocupados del aula elegida.'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {classroomId === null && <EmptyState title="Elegí un aula" description="Seleccioná un aula o laboratorio para ver su disponibilidad." />}
              {classroomId !== null && availability.isLoading && <Skeleton className="h-96 w-full rounded-lg" />}
              {availability.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(availability.error, 'No se pudo cargar la disponibilidad.')}</AlertTitle></Alert>}
              {data && (
                <>
                  <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-label="Leyenda">
                    <li className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-success/60" />Disponible</li>
                    <li className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-destructive/60" />Ocupada (clase)</li>
                    <li className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-warning/60" />Reservada</li>
                    <li className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-info/60" />Tu reserva</li>
                  </ul>
                  <AvailabilityTimeline busy={data.busy} dayStart={data.day_start} dayEnd={data.day_end} selection={selection} />
                </>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Nueva reserva</CardTitle>
              <CardDescription>Reserva puntual para la fecha elegida.</CardDescription>
            </CardHeader>
            <CardContent>
              {data
                ? <ReservationForm availability={data} draft={draft} endTime={endTime} problem={problem} onDraftChange={setDraft} />
                : <p className="text-sm text-muted-foreground">Elegí un aula y una fecha para reservar.</p>}
            </CardContent>
          </Card>
          <MyReservations />
        </div>
      </div>
    </div>
  )
}
