import { useState } from 'react'

import { useCloseIntensiveCourse, useIntensiveCourse } from '@/api/hooks/useIntensiveCourses'
import { ConfirmAlertDialog } from '@/components/shared/ConfirmAlertDialog'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Sheet, SheetDescription, SheetFooter, SheetHeader, SheetPanel, SheetPopup, SheetTitle } from '@/components/ui/sheet'
import { formatDateInBolivia, getTodayInBolivia } from '@/lib/boliviaDates'
import {
  courseStatus,
  priceLabel,
  seatsLabel,
  termLabel,
  type AdminIntensiveCourse,
} from '@/lib/intensiveCoursesState'
import { formatBs } from '@/lib/reenrollmentState'
import { apiErrorMessage } from '@/lib/userCredentials'

/** Enrolled students of one intensive course, with the staff actions: edit and close the enrollment. */
export function CourseSheet({ courseId, onClose, onEdit }: {
  courseId: number | null; onClose: () => void; onEdit: (course: AdminIntensiveCourse) => void
}) {
  const detail = useIntensiveCourse(courseId)
  const close = useCloseIntensiveCourse()
  const [confirming, setConfirming] = useState(false)
  const data = detail.data
  const status = data ? courseStatus(data, getTodayInBolivia()) : null

  return (
    <Sheet open={courseId !== null} onOpenChange={(open) => { if (!open) { setConfirming(false); close.reset(); onClose() } }}>
      <SheetPopup className="sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{data ? `${data.subject.name}` : 'Curso intensivo'}</SheetTitle>
          <SheetDescription>
            {data && status && (
              <span className="flex flex-wrap items-center gap-2">
                {data.subject.code} · {termLabel(data.term_code)} ({data.term_code})
                <Badge variant={status.variant}>{status.label}</Badge>
              </span>
            )}
          </SheetDescription>
        </SheetHeader>
        <SheetPanel className="space-y-5">
          {detail.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(detail.error, 'No se pudo cargar el curso.')}</AlertTitle></Alert>}
          {!data && !detail.isError && <p role="status" className="text-sm text-muted-foreground">Cargando curso…</p>}
          {data && (
            <>
              <dl className="grid grid-cols-2 gap-2 text-sm">
                <dt className="text-muted-foreground">Docente</dt><dd>{data.teacher.full_name}</dd>
                <dt className="text-muted-foreground">Inscripción</dt>
                <dd>{formatDateInBolivia(data.enrollment_starts_on)} al {formatDateInBolivia(data.enrollment_ends_on)}</dd>
                <dt className="text-muted-foreground">Inscritos</dt><dd>{seatsLabel(data)}</dd>
                <dt className="text-muted-foreground">Horas</dt><dd>{data.theory_hours} de teoría · {data.practice_hours} de práctica</dd>
                <dt className="text-muted-foreground">Pago docente</dt><dd>{formatBs(data.teacher_pay)}</dd>
                <dt className="text-muted-foreground">Precio por estudiante</dt><dd className="font-medium">{priceLabel(data.price)}</dd>
              </dl>
              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-foreground">Estudiantes inscritos ({data.students.length})</h3>
                {data.students.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Todavía no hay estudiantes inscritos.</p>
                ) : (
                  <ul className="divide-y rounded-lg border text-sm">
                    {data.students.map((student) => (
                      <li key={student.student_id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                        <span className="font-medium">{student.full_name}</span>
                        <span className="flex items-center gap-2 text-muted-foreground">
                          {student.document_number}
                          {student.is_foreign && <Badge variant="warning" size="sm">Extranjero</Badge>}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
              {close.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(close.error, 'No se pudo cerrar la inscripción.')}</AlertTitle></Alert>}
              {data.status === 'closed' && <Alert variant="info"><AlertTitle>Inscripción cerrada: el precio quedó fijo.</AlertTitle></Alert>}
            </>
          )}
        </SheetPanel>
        {data && data.status === 'open' && (
          <SheetFooter>
            <Button variant="outline" onClick={() => onEdit(data)}>Editar curso</Button>
            <Button disabled={close.isPending} onClick={() => setConfirming(true)}>Cerrar inscripción</Button>
          </SheetFooter>
        )}
        <ConfirmAlertDialog
          summary={confirming && data ? {
            title: 'Cerrar inscripción', confirmLabel: 'Cerrar inscripción',
            rows: [
              { label: 'Curso', value: `${data.subject.code} · ${data.term_code}` },
              { label: 'Inscritos', value: String(data.enrolled) },
              { label: 'Precio por estudiante', value: formatBs(data.price.amount) },
            ],
            warning: `El precio queda fijo en ${formatBs(data.price.amount)} por estudiante con los ${data.enrolled} inscritos de hoy.`,
            consequence: 'Después de cerrar no se puede inscribir ni cancelar la inscripción, ni editar el curso. No se puede deshacer.',
          } : null}
          pending={close.isPending}
          onConfirm={() => close.mutate(data?.id ?? 0, { onSettled: () => setConfirming(false) })}
          onCancel={() => setConfirming(false)}
        />
      </SheetPopup>
    </Sheet>
  )
}
