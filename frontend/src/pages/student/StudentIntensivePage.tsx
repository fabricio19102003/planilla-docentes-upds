import { CheckCircle2 } from 'lucide-react'
import { useState } from 'react'

import { useIntensiveEnrollment, useStudentIntensiveCourses } from '@/api/hooks/useStudentPortal'
import { ConfirmAlertDialog, type ConfirmAlertSummary } from '@/components/shared/ConfirmAlertDialog'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDateInBolivia, getTodayInBolivia } from '@/lib/boliviaDates'
import {
  courseStatus,
  priceLabel,
  studentPriceNote,
  termLabel,
  type StudentIntensiveCourse,
} from '@/lib/intensiveCoursesState'
import { apiErrorMessage } from '@/lib/userCredentials'

type Action = 'enroll' | 'cancel'

function CourseCard({ course, action, onAction }: {
  course: StudentIntensiveCourse; action: Action; onAction: (course: StudentIntensiveCourse, action: Action) => void
}) {
  const status = courseStatus(course, getTodayInBolivia())
  const blocked = action === 'enroll' && (!course.is_enrollment_open || course.is_full)
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 p-4">
      <div className="space-y-1 text-sm">
        <p className="flex flex-wrap items-center gap-2 font-medium text-foreground">
          {course.subject.name}
          <span className="text-xs font-normal text-muted-foreground">{course.subject.code}</span>
          <Badge variant={status.variant} size="sm">{status.label}</Badge>
        </p>
        <p className="text-muted-foreground">{termLabel(course.term_code)} · Docente: {course.teacher_name}</p>
        <p className="text-muted-foreground">
          Inscripción del {formatDateInBolivia(course.enrollment_starts_on)} al {formatDateInBolivia(course.enrollment_ends_on)} ·{' '}
          {course.is_full ? 'Sin cupos' : `${course.free} cupo(s) libre(s)`}
        </p>
        <p>
          <span className="font-medium">{priceLabel(course.price)}</span>
          <span className="block text-xs text-muted-foreground">{studentPriceNote(course.price)}</span>
        </p>
      </div>
      {action === 'enroll' && (
        <Button disabled={blocked} onClick={() => onAction(course, 'enroll')}>
          {course.is_full ? 'Sin cupos' : course.is_enrollment_open ? 'Inscribirme' : 'Inscripción no abierta'}
        </Button>
      )}
      {action === 'cancel' && course.status === 'open' && (
        <Button variant="outline" onClick={() => onAction(course, 'cancel')}>Cancelar inscripción</Button>
      )}
    </li>
  )
}

function summaryFor(course: StudentIntensiveCourse, action: Action): ConfirmAlertSummary {
  const rows = [
    { label: 'Materia', value: `${course.subject.code} · ${course.subject.name}` },
    { label: 'Período', value: termLabel(course.term_code) },
    { label: 'Precio', value: priceLabel(course.price) },
  ]
  return action === 'enroll'
    ? {
      title: 'Inscribirme al curso', confirmLabel: 'Inscribirme', rows,
      consequence: 'El precio es informativo y estimado: baja si se inscriben más estudiantes y queda fijo cuando Registro cierra la inscripción. No se cobra desde acá.',
    }
    : {
      title: 'Cancelar inscripción', confirmLabel: 'Cancelar inscripción', tone: 'destructive', rows,
      consequence: 'Dejás tu cupo. Mientras la inscripción siga abierta podés volver a inscribirte si hay lugar.',
    }
}

export function StudentIntensivePage() {
  const view = useStudentIntensiveCourses()
  const change = useIntensiveEnrollment()
  const [confirm, setConfirm] = useState<{ course: StudentIntensiveCourse; action: Action } | null>(null)

  if (view.isError) return <Alert variant="error" role="alert"><AlertTitle>No se pudieron cargar los cursos de verano e invierno.</AlertTitle></Alert>
  if (!view.data) return <p role="status" className="text-sm text-muted-foreground">Cargando cursos…</p>
  const { courses, enrollments } = view.data

  return (
    <>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Cursos de verano e invierno</h1>
        <p className="text-sm text-muted-foreground">Podés inscribirte a los cursos de las materias que reprobaste o tenés pendientes. Es informativo: el cobro no se hace desde el portal.</p>
      </div>
      {change.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(change.error, 'No se pudo actualizar tu inscripción.')}</AlertTitle></Alert>}
      {change.isSuccess && (
        <Alert variant="success" role="status">
          <CheckCircle2 aria-hidden="true" /><AlertTitle>{change.variables?.action === 'cancel' ? 'Cancelaste tu inscripción.' : 'Quedaste inscrito en el curso.'}</AlertTitle>
        </Alert>
      )}

      <Card>
        <CardHeader><CardTitle className="text-base">Mis inscripciones</CardTitle></CardHeader>
        <CardContent className="p-0">
          {enrollments.length === 0
            ? <p className="px-4 pb-4 text-sm text-muted-foreground">No estás inscrito en ningún curso intensivo.</p>
            : <ul className="divide-y">{enrollments.map((course) => <CourseCard key={course.id} course={course} action="cancel" onAction={(c, a) => { change.reset(); setConfirm({ course: c, action: a }) }} />)}</ul>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Cursos disponibles para vos</CardTitle>
          <CardDescription>Solo aparecen materias que reprobaste o tenés pendientes (retiradas).</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {courses.length === 0
            ? <p className="px-4 pb-4 text-sm text-muted-foreground">Por ahora no hay cursos abiertos para tus materias.</p>
            : <ul className="divide-y">{courses.map((course) => <CourseCard key={course.id} course={course} action="enroll" onAction={(c, a) => { change.reset(); setConfirm({ course: c, action: a }) }} />)}</ul>}
        </CardContent>
      </Card>

      <ConfirmAlertDialog
        summary={confirm ? summaryFor(confirm.course, confirm.action) : null}
        pending={change.isPending}
        onConfirm={() => confirm && change.mutate({ courseId: confirm.course.id, action: confirm.action }, { onSettled: () => setConfirm(null) })}
        onCancel={() => setConfirm(null)}
      />
    </>
  )
}
