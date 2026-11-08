import { es } from '@daypicker/react/locale'
import { useMemo, useState } from 'react'

import {
  useClassroomDay,
  useCreateClassroomReservation,
  useMyClassroomReservations,
} from '@/api/hooks/useClassroomReservations'
import { DayAgenda } from '@/components/classroom-reservations/DayAgenda'
import { DurationStepper } from '@/components/classroom-reservations/DurationStepper'
import { MyReservations } from '@/components/classroom-reservations/MyReservations'
import { ReservationSummary } from '@/components/classroom-reservations/ReservationSummary'
import { RoomPicker } from '@/components/classroom-reservations/RoomPicker'
import { StartTimeGrid } from '@/components/classroom-reservations/StartTimeGrid'
import { PageHeader } from '@/components/shared/PageHeader'
import { Calendar } from '@/components/ui/calendar'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { toastManager } from '@/components/ui/toast'
import { getTodayInBolivia } from '@/lib/boliviaDates'
import {
  formatDuration,
  formatLongDate,
  getBoliviaMinutes,
  nextBookableDate,
  parseDateKey,
  startOptions,
  toDateKey,
} from '@/lib/classroomReservationDay'
import { computeEndTime, rangeProblem } from '@/lib/classroomReservations'
import { apiErrorMessage } from '@/lib/userCredentials'

const DEFAULT_PERIODS = 2

export function ClassroomReservationPage() {
  const today = getTodayInBolivia()
  const [date, setDate] = useState(() => nextBookableDate(today))
  const [classroomId, setClassroomId] = useState<number | null>(null)
  const [periods, setPeriods] = useState(DEFAULT_PERIODS)
  const [start, setStart] = useState('')
  const [hint, setHint] = useState<string | null>(null)

  const day = useClassroomDay(date)
  const mine = useMyClassroomReservations()
  const create = useCreateClassroomReservation()

  const data = day.data
  const entry = data?.rooms.find((room) => room.classroom.id === classroomId) ?? null
  const periodMinutes = data?.academic_hour_minutes ?? 45
  const endTime = computeEndTime(start, periods, periodMinutes)
  const options = useMemo(
    () => (data && entry
      ? startOptions({
        busy: entry.busy,
        dayStart: data.day_start,
        dayEnd: data.day_end,
        durationMinutes: periods * data.academic_hour_minutes,
        after: date === today ? getBoliviaMinutes() : null,
      })
      : []),
    [data, entry, periods, date, today],
  )
  const problem = data && entry && start
    ? rangeProblem({ busy: entry.busy, dayStart: data.day_start, dayEnd: data.day_end, start, end: endTime })
    : null
  const startFits = options.find((option) => option.time === start)?.available ?? false
  const ready = entry !== null && endTime !== null && problem === null && startFits

  const mineDates = useMemo(() => (mine.data ?? []).map((reservation) => parseDateKey(reservation.date)), [mine.data])
  const todayDate = parseDateKey(today)

  const resetFeedback = () => { create.reset(); setHint(null) }
  const changeDate = (next: Date) => { setDate(toDateKey(next)); setStart(''); resetFeedback() }
  const changeRoom = (id: number) => { setClassroomId(id); setStart(''); resetFeedback() }
  const changePeriods = (next: number) => { setPeriods(next); resetFeedback() }
  const pickStart = (time: string) => {
    resetFeedback()
    if (options.find((option) => option.time === time)?.available) {
      setStart(time)
      return
    }
    setHint(`A las ${time} no hay lugar para ${periods} ${periods === 1 ? 'período' : 'períodos'}. Probá otra hora o reducí la duración.`)
  }

  const submit = () => {
    if (!ready || !entry) return
    create.mutate(
      { classroom_id: entry.classroom.id, date, start_time: start, periods },
      {
        onSuccess: (reservation) => {
          toastManager.add({
            type: 'success',
            title: 'Reserva confirmada',
            description: `${reservation.classroom.name} · ${formatLongDate(reservation.date)} · ${reservation.start_time} – ${reservation.end_time}`,
          })
          setStart('')
        },
      },
    )
  }

  return (
    <div>
      <PageHeader
        title="Reservar aula"
        description="Elegí el espacio, el día y el horario. La reserva queda confirmada al instante."
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,24rem)_minmax(0,1fr)_19rem] xl:grid-rows-[auto_1fr] xl:items-start">
        <Card className="xl:col-start-3 xl:row-start-1">
          <CardHeader>
            <CardTitle>Día</CardTitle>
            <CardDescription>No se reserva en días pasados ni domingos.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Calendar
              className="mx-auto"
              mode="single"
              required
              locale={es}
              weekStartsOn={1}
              selected={parseDateKey(date)}
              defaultMonth={parseDateKey(date)}
              startMonth={todayDate}
              onSelect={changeDate}
              disabled={[{ before: todayDate }, { dayOfWeek: [0] }]}
              modifiers={{ mine: mineDates }}
              modifiersClassNames={{
                mine: '*:before:pointer-events-none *:before:absolute *:before:end-1 *:before:top-1 *:before:size-1.5 *:before:rounded-full *:before:bg-warning',
              }}
              classNames={{ caption_label: 'capitalize' }}
              labels={{
                labelDayButton: (day, modifiers) =>
                  `${formatLongDate(toDateKey(day))}${modifiers.mine ? ' (tenés una reserva)' : ''}${modifiers.today ? ' (hoy)' : ''}`,
              }}
            />
            <p className="flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
              <span className="size-1.5 rounded-full bg-warning" aria-hidden="true" />Día con una reserva tuya
            </p>
          </CardContent>
        </Card>

        <Card className="xl:col-start-1 xl:row-span-2 xl:row-start-1">
          <CardHeader>
            <CardTitle>Espacio</CardTitle>
            <CardDescription>{data ? `La barra de cada tarjeta cubre de ${data.day_start} a ${data.day_end}: lo ocupado va en color.` : 'La barra de cada tarjeta muestra lo ocupado del día.'}</CardDescription>
          </CardHeader>
          <CardContent>
            <RoomPicker
              rooms={data?.rooms}
              dayStart={data?.day_start ?? '06:30'}
              dayEnd={data?.day_end ?? '23:05'}
              selectedId={entry?.classroom.id ?? null}
              loading={day.isLoading}
              error={day.isError ? apiErrorMessage(day.error, 'No se pudo cargar la disponibilidad.') : null}
              onSelect={changeRoom}
            />
          </CardContent>
        </Card>

        <Card className="xl:col-start-2 xl:row-span-2 xl:row-start-1">
          <CardHeader>
            <CardTitle>{entry ? `${entry.classroom.name} · ${formatLongDate(date)}` : 'Agenda del día'}</CardTitle>
            <CardDescription>
              Tocá una hora libre en la agenda para empezar ahí, o elegila en «Hora de inicio». Ajustá la duración en el panel.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {day.isLoading && <Skeleton className="h-96 w-full rounded-lg" />}
            {!day.isLoading && !entry && <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">Elegí un aula o laboratorio para ver su agenda.</p>}
            {data && entry && (
              <DayAgenda
                busy={entry.busy}
                dayStart={data.day_start}
                dayEnd={data.day_end}
                selection={start && endTime ? { start, end: endTime, conflict: problem !== null || !startFits } : null}
                hint={hint}
                onPick={pickStart}
              />
            )}
          </CardContent>
        </Card>

        <Card className="xl:col-start-3 xl:row-start-2">
          <CardHeader>
            <CardTitle>Duración y hora</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <DurationStepper periods={periods} periodMinutes={periodMinutes} onChange={changePeriods} />
            <div className="space-y-1.5">
              <p className="text-sm font-medium">Hora de inicio</p>
              {entry
                ? <StartTimeGrid options={options} start={start} end={endTime} onSelect={pickStart} />
                : <p className="text-sm text-muted-foreground">Elegí un aula para ver las horas.</p>}
            </div>
            <ReservationSummary
              rows={[
                { label: 'Espacio', value: entry?.classroom.name ?? '—' },
                { label: 'Día', value: formatLongDate(date) },
                { label: 'Horario', value: start && endTime ? `${start} – ${endTime}` : '—' },
                { label: 'Períodos', value: `${periods} × ${periodMinutes} min · ${formatDuration(periods * periodMinutes)}` },
              ]}
              problem={problem}
              submitError={create.isError ? apiErrorMessage(create.error, 'No se pudo crear la reserva.') : null}
              ready={ready}
              pending={create.isPending}
              onSubmit={submit}
            />
          </CardContent>
        </Card>
      </div>

      <div className="mt-4">
        <MyReservations />
      </div>
    </div>
  )
}
