import { useState } from 'react'

import {
  useCancelClassroomReservation,
  useMyClassroomReservations,
  type ClassroomReservation,
} from '@/api/hooks/useClassroomReservations'
import { ConfirmAlertDialog } from '@/components/shared/ConfirmAlertDialog'
import { EmptyState } from '@/components/shared/EmptyState'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { toastManager } from '@/components/ui/toast'
import { formatDateInBolivia } from '@/lib/boliviaDates'
import { apiErrorMessage } from '@/lib/userCredentials'

function reservationSummary(reservation: ClassroomReservation) {
  return [
    { label: 'Aula', value: reservation.classroom.name },
    { label: 'Fecha', value: formatDateInBolivia(reservation.date) },
    { label: 'Horario', value: `${reservation.start_time} – ${reservation.end_time}` },
  ]
}

export function MyReservations() {
  const mine = useMyClassroomReservations()
  const cancel = useCancelClassroomReservation()
  const [target, setTarget] = useState<ClassroomReservation | null>(null)

  const close = () => { setTarget(null); cancel.reset() }
  const confirm = () => {
    if (!target) return
    cancel.mutate(target.id, {
      onSuccess: () => {
        toastManager.add({ type: 'success', title: 'Reserva cancelada', description: `${target.classroom.name} · ${formatDateInBolivia(target.date)}` })
        close()
      },
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Mis reservas</CardTitle>
        <CardDescription>Reservas confirmadas desde hoy en adelante.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {mine.isLoading && <Skeleton className="h-16 w-full rounded-lg" />}
        {mine.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(mine.error, 'No se pudieron cargar tus reservas.')}</AlertTitle></Alert>}
        {mine.data?.length === 0 && <EmptyState title="Sin reservas" description="Cuando reserves un aula aparecerá acá." />}
        {mine.data && mine.data.length > 0 && (
          <ul className="divide-y rounded-lg border">
            {mine.data.map((reservation) => (
              <li key={reservation.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0 space-y-1">
                  <p className="font-medium">{reservation.classroom.name}</p>
                  <p className="text-sm text-muted-foreground tabular-nums">
                    {formatDateInBolivia(reservation.date)} · {reservation.start_time} – {reservation.end_time}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    <Badge variant="outline">{reservation.academic_periods} {reservation.academic_periods === 1 ? 'período' : 'períodos'}</Badge>
                    {reservation.classroom.classroom_type === 'laboratory' && <Badge variant="info">Laboratorio</Badge>}
                  </div>
                </div>
                <Button size="sm" variant="outline" onClick={() => setTarget(reservation)}>Cancelar</Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>

      <ConfirmAlertDialog
        summary={target ? {
          title: 'Cancelar reserva',
          confirmLabel: 'Sí, cancelar reserva',
          tone: 'destructive',
          rows: reservationSummary(target),
          consequence: 'El aula quedará libre para otros docentes.',
          warning: cancel.isError ? apiErrorMessage(cancel.error, 'No se pudo cancelar la reserva.') : null,
        } : null}
        description="Confirmá que querés cancelar esta reserva."
        cancelLabel="Conservar reserva"
        pending={cancel.isPending}
        onConfirm={confirm}
        onCancel={close}
      />
    </Card>
  )
}
