import { AlertTriangle } from 'lucide-react'

import { useCreateClassroomReservation, type ClassroomAvailability } from '@/api/hooks/useClassroomReservations'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toastManager } from '@/components/ui/toast'
import { formatDateInBolivia } from '@/lib/boliviaDates'
import { MAX_PERIODS, MIN_PERIODS, startTimeOptions } from '@/lib/classroomReservations'
import { apiErrorMessage } from '@/lib/userCredentials'

export interface ReservationDraft {
  start: string
  periods: number
}

interface ReservationFormProps {
  availability: ClassroomAvailability
  draft: ReservationDraft
  endTime: string | null
  problem: string | null
  onDraftChange: (draft: ReservationDraft) => void
}

export function ReservationForm({ availability, draft, endTime, problem, onDraftChange }: ReservationFormProps) {
  const create = useCreateClassroomReservation()
  const minutes = availability.academic_hour_minutes
  const startItems = startTimeOptions(availability.day_start, availability.day_end).map((time) => ({ value: time, label: time }))
  const periodItems = Array.from({ length: MAX_PERIODS - MIN_PERIODS + 1 }, (_, index) => {
    const periods = MIN_PERIODS + index
    return { value: String(periods), label: `${periods} ${periods === 1 ? 'período' : 'períodos'} (${periods * minutes} min)` }
  })
  const ready = draft.start !== '' && endTime !== null && problem === null

  const submit = () => {
    if (!ready) return
    create.mutate(
      { classroom_id: availability.classroom.id, date: availability.date, start_time: draft.start, periods: draft.periods },
      {
        onSuccess: (reservation) => {
          toastManager.add({
            type: 'success',
            title: 'Reserva confirmada',
            description: `${reservation.classroom.name} · ${formatDateInBolivia(reservation.date)} · ${reservation.start_time} – ${reservation.end_time}`,
          })
          onDraftChange({ ...draft, start: '' })
        },
      },
    )
  }

  return (
    <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); submit() }}>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="reservation-start">Hora de inicio</Label>
          <Select
            value={draft.start || null}
            items={startItems}
            onValueChange={(value) => { create.reset(); onDraftChange({ ...draft, start: value ?? '' }) }}
          >
            <SelectTrigger id="reservation-start"><SelectValue placeholder="Elegí la hora" /></SelectTrigger>
            <SelectPopup>
              {startItems.map((item) => <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>)}
            </SelectPopup>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="reservation-periods">Períodos académicos</Label>
          <Select
            value={String(draft.periods)}
            items={periodItems}
            onValueChange={(value) => { create.reset(); onDraftChange({ ...draft, periods: Number(value ?? draft.periods) }) }}
          >
            <SelectTrigger id="reservation-periods"><SelectValue /></SelectTrigger>
            <SelectPopup>
              {periodItems.map((item) => <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>)}
            </SelectPopup>
          </Select>
        </div>
      </div>

      <p className="text-sm text-muted-foreground" aria-live="polite">
        {draft.start && endTime
          ? <>Horario: <strong className="tabular-nums text-foreground">{draft.start} – {endTime}</strong> · cada período dura {minutes} min</>
          : draft.start
            ? 'La reserva se pasa del horario permitido.'
            : `Elegí la hora de inicio. Cada período dura ${minutes} min.`}
      </p>

      {problem && (
        <Alert variant="warning" role="alert">
          <AlertTriangle />
          <AlertDescription>{problem}</AlertDescription>
        </Alert>
      )}
      {create.isError && (
        <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(create.error, 'No se pudo crear la reserva.')}</AlertTitle></Alert>
      )}

      <Button type="submit" disabled={!ready || create.isPending} className="w-full sm:w-auto">
        {create.isPending ? 'Reservando…' : 'Reservar'}
      </Button>
    </form>
  )
}
