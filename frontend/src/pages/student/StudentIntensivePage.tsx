import { BookOpen, CheckCircle2, ClipboardList, Snowflake, Sun } from 'lucide-react'
import { useState } from 'react'

import { useIntensiveEnrollment, useStudentIntensiveCourses } from '@/api/hooks/useStudentPortal'
import { ConfirmAlertDialog, type ConfirmAlertSummary } from '@/components/shared/ConfirmAlertDialog'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { CourseCard, type CourseAction } from '@/components/student/courses/CourseCard'
import { seasonTone } from '@/components/student/courses/course-season'
import { Eyebrow } from '@/components/student/Eyebrow'
import { Sheet } from '@/components/student/Sheet'
import { priceLabel, termLabel, type StudentIntensiveCourse } from '@/lib/intensiveCoursesState'
import { apiErrorMessage } from '@/lib/userCredentials'
import '@/styles/student/courses.css'

type Action = CourseAction

const pressClass = 'active:scale-95 motion-reduce:active:scale-100'

// Terms are VER/2027 (summer) or INV/2027 (winter); anything else gets a book.
function SeasonIcon({ termCode }: { termCode: string }) {
  const season = seasonTone(termCode)
  if (season === 'summer') return <Sun />
  return season === 'winter' ? <Snowflake /> : <BookOpen />
}

function CourseGrid({ courses, action, onAction }: {
  courses: StudentIntensiveCourse[]; action: Action; onAction: (course: StudentIntensiveCourse, action: Action) => void
}) {
  return (
    <ul className="cc-grid">
      {courses.map((course) => (
        <CourseCard key={course.id} course={course} action={action} onAction={onAction}
          seasonIcon={<SeasonIcon termCode={course.term_code} />} pressClass={pressClass} />
      ))}
    </ul>
  )
}

function CourseSkeleton() {
  return (
    <Sheet as="li" depth={2} padding="none" className="cc-card cc-card--skeleton cc-card--other">
      <div className="cc-skel-band" />
      <div className="cc-body">
        <div className="grid gap-2">
          <Skeleton className="h-8 w-4/5 rounded-lg" />
          <Skeleton className="h-4 w-1/2 rounded-md" />
        </div>
        <Skeleton className="h-14 w-40 rounded-lg" />
        <div className="flex flex-wrap gap-2">
          <Skeleton className="h-9 w-36 rounded-xl" />
          <Skeleton className="h-9 w-16 rounded-xl" />
        </div>
        <Skeleton className="h-3 w-full rounded-md" />
        <Skeleton className="h-11 w-full rounded-2xl" />
      </div>
    </Sheet>
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
  const request = (course: StudentIntensiveCourse, action: Action) => { change.reset(); setConfirm({ course, action }) }

  const header = (
    <PageHeader as="h1" className="cc-head"
      breadcrumb={<Eyebrow icon={<Sun />}>Verano e invierno</Eyebrow>}
      title="Cursos de verano e invierno"
      description="Podés inscribirte a los cursos de las materias que reprobaste o tenés pendientes. Es informativo: el cobro no se hace desde el portal."
    />
  )
  if (view.isError) return <div className="cc-page">{header}<Alert variant="error" role="alert"><AlertTitle>No se pudieron cargar los cursos de verano e invierno.</AlertTitle></Alert></div>
  if (!view.data) {
    return (
      <div className="cc-page">
        {header}
        <div role="status" aria-label="Cargando cursos">
          <ul className="cc-grid">
            <CourseSkeleton />
            <CourseSkeleton />
          </ul>
        </div>
      </div>
    )
  }
  const { courses, enrollments } = view.data

  return (
    <div className="cc-page">
      {header}
      {change.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(change.error, 'No se pudo actualizar tu inscripción.')}</AlertTitle></Alert>}
      {change.isSuccess && (
        <Alert variant="success" role="status">
          <CheckCircle2 aria-hidden="true" /><AlertTitle>{change.variables?.action === 'cancel' ? 'Cancelaste tu inscripción.' : 'Quedaste inscrito en el curso.'}</AlertTitle>
        </Alert>
      )}

      <section className="cc-section" aria-labelledby="cc-enrolled-title">
        <div className="cc-section-head">
          <h2 id="cc-enrolled-title" className="cc-section-title">Mis inscripciones</h2>
          <span className="cc-count" aria-label={`${enrollments.length} inscripciones`}>{enrollments.length}</span>
        </div>
        {enrollments.length === 0
          ? <div className="cc-empty"><EmptyState illustration="empty-inbox" icon={ClipboardList} className="py-8" title="Sin inscripciones" description="No estás inscrito en ningún curso intensivo." /></div>
          : <CourseGrid courses={enrollments} action="cancel" onAction={request} />}
      </section>

      <section className="cc-section" aria-labelledby="cc-available-title">
        <div className="cc-section-head">
          <h2 id="cc-available-title" className="cc-section-title">Cursos disponibles para vos</h2>
          <span className="cc-count" aria-label={`${courses.length} cursos`}>{courses.length}</span>
          <p className="cc-section-note">Solo aparecen materias que reprobaste o tenés pendientes (retiradas).</p>
        </div>
        {courses.length === 0
          ? <div className="cc-empty"><EmptyState illustration="empty-box" icon={BookOpen} className="py-8" title="Sin cursos disponibles" description="Por ahora no hay cursos abiertos para tus materias." /></div>
          : <CourseGrid courses={courses} action="enroll" onAction={request} />}
      </section>

      <ConfirmAlertDialog
        summary={confirm ? summaryFor(confirm.course, confirm.action) : null}
        pending={change.isPending}
        onConfirm={() => confirm && change.mutate({ courseId: confirm.course.id, action: confirm.action }, { onSettled: () => setConfirm(null) })}
        onCancel={() => setConfirm(null)}
      />
    </div>
  )
}
