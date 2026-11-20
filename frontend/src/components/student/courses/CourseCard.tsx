import { ArrowRight, CalendarDays, CircleCheck, Clock, Hourglass, Info, TriangleAlert, UserRound, XCircle, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { formatDateInBolivia, getTodayInBolivia } from '@/lib/boliviaDates'
import { courseStatus, studentPriceNote, termLabel, type StudentIntensiveCourse } from '@/lib/intensiveCoursesState'
import { cn } from '@/lib/utils'
import { DisplayFigure } from '../DisplayFigure'
import { InfoTip } from '../InfoTip'
import { Meter } from '../Meter'
import { Sheet } from '../Sheet'
import { enrollBlockReason, seasonTone, seatsMeter, statusTone, type BlockReason, type StatusTone } from './course-season'

export type CourseAction = 'enroll' | 'cancel'

const STATUS_ICON: Record<StatusTone, LucideIcon> = {
  ok: CircleCheck, info: CalendarDays, warn: Hourglass, muted: XCircle, bad: XCircle,
}

const BLOCK_TEXT: Record<BlockReason, (course: StudentIntensiveCourse) => string> = {
  full: () => 'Se agotaron los cupos. Mientras la inscripción siga abierta, podés volver si se libera uno.',
  scheduled: (course) => `La inscripción abre el ${formatDateInBolivia(course.enrollment_starts_on)}.`,
  expired: (course) => `La inscripción cerró el ${formatDateInBolivia(course.enrollment_ends_on)}.`,
  closed: () => 'Registro cerró este curso.',
}

const PRICE_TIP_ESTIMATE =
  'Es un precio estimado: baja con más inscriptos y se fija cuando Registro cierra la inscripción. No se cobra desde el portal.'
const PRICE_TIP_FINAL = 'Es el precio fijo: Registro ya cerró la inscripción. No se cobra desde el portal.'

interface CourseCardProps {
  course: StudentIntensiveCourse
  action: CourseAction
  onAction: (course: StudentIntensiveCourse, action: CourseAction) => void
  /** Season icon of the band (sun, snowflake or book). */
  seasonIcon: ReactNode
  /** Press feedback classes of the CTA buttons. */
  pressClass: string
}

/** One intensive course as an editorial sheet: season band, price figure, date chips, seats meter and its CTA. */
export function CourseCard({ course, action, onAction, seasonIcon, pressClass }: CourseCardProps) {
  const status = courseStatus(course, getTodayInBolivia())
  const tone = statusTone(status.variant)
  const StatusIcon = STATUS_ICON[tone]
  const season = seasonTone(course.term_code)
  const seats = seatsMeter(course)
  const reason = action === 'enroll' ? enrollBlockReason(course, getTodayInBolivia()) : null
  const reasonId = `course-${course.id}-reason`
  const hours = course.theory_hours + course.practice_hours
  const decimals = Number.isInteger(course.price.amount) ? 0 : 2

  return (
    <Sheet as="li" depth={2} padding="none" lift className={cn('cc-card', `cc-card--${season}`)}>
      <div className="cc-band">
        <span className="cc-band-term">{termLabel(course.term_code)}</span>
        <span aria-hidden="true" className="cc-band-icon">{seasonIcon}</span>
      </div>

      <div className="cc-body">
        <div className="grid gap-2">
          <h3 className="cc-name">{course.subject.name}</h3>
          <p className="cc-meta">
            <code className="cc-code">{course.subject.code}</code>
            <span className="cc-status" data-tone={tone}><StatusIcon aria-hidden="true" />{status.label}</span>
          </p>
          <p className="cc-teacher"><UserRound aria-hidden="true" /><span className="sp-sr-only">Docente: </span>{course.teacher_name}</p>
        </div>

        <div className="cc-price">
          <DisplayFigure value={course.price.amount} decimals={decimals} prefix="Bs" size="lg" />
          <div className="cc-price-note">
            <span>{studentPriceNote(course.price)}</span>
            <InfoTip label="Cómo se calcula el precio" content={course.price.is_final ? PRICE_TIP_FINAL : PRICE_TIP_ESTIMATE} />
          </div>
        </div>

        <p className="cc-chips">
          <span className="cc-chip">
            <CalendarDays aria-hidden="true" />
            <span className="sp-sr-only">Inscripción del </span>
            {formatDateInBolivia(course.enrollment_starts_on)}
            <span aria-hidden="true">–</span><span className="sp-sr-only"> al </span>
            {formatDateInBolivia(course.enrollment_ends_on)}
          </span>
          {hours > 0 && (
            <span className="cc-chip"><Clock aria-hidden="true" /><span className="sp-sr-only">Carga horaria: </span>{hours} h</span>
          )}
        </p>

        <div className="cc-seats">
          <Meter
            value={seats.value} max={seats.max} tone={seats.tone} segments={seats.max <= 40}
            label="Cupos libres" valueText={seats.valueText}
          />
          <p className="cc-seats-text">
            <span className={cn('cc-seats-count', seats.tone === 'bad' && 'cc-seats-count--none')}>{seats.label}</span>
            <span className="cc-seats-of">de {course.capacity}</span>
            {seats.few && <span className="cc-few"><TriangleAlert aria-hidden="true" />Quedan pocos</span>}
          </p>
        </div>

        {action === 'enroll' && (
          <Button
            className={cn(pressClass, 'cc-cta group')} size="lg" disabled={reason !== null}
            aria-describedby={reason ? reasonId : undefined} onClick={() => onAction(course, 'enroll')}
          >
            {reason === 'full' ? 'Sin cupos' : course.is_enrollment_open ? 'Inscribirme' : 'Inscripción no abierta'}
            {reason === null && <ArrowRight aria-hidden="true" className="cc-cta-arrow" />}
          </Button>
        )}
        {action === 'cancel' && course.status === 'open' && course.is_enrollment_open && (
          <Button className={cn(pressClass, 'cc-cta')} size="lg" variant="outline" onClick={() => onAction(course, 'cancel')}>
            Cancelar inscripción
          </Button>
        )}
        {reason && <p id={reasonId} className="cc-reason"><Info aria-hidden="true" />{BLOCK_TEXT[reason](course)}</p>}
      </div>
    </Sheet>
  )
}
