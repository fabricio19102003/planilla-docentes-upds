import { ArrowRight, Award, CalendarCheck, CalendarClock, CircleCheck, ClipboardList, Clock, FileText, GraduationCap, Lock, MapPin, Sparkles, TrendingUp, UserCheck, UserRound, Wallet } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { useStudentHistory, useStudentMe, useStudentMigrationDocuments, useStudentReenrollment, useStudentSchedule } from '@/api/hooks/useStudentPortal'
import { GlassCard, GlassStage, HomeCard } from '@/components/student'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress, ProgressIndicator, ProgressTrack } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateInBolivia } from '@/lib/boliviaDates'
import { pendingLabels, regularizadoBadge } from '@/lib/migrationDocumentsState'
import { formatBs, requestStatus } from '@/lib/reenrollmentState'
import { summarizeHistory } from '@/lib/studentHistorySummary'
import { countdownLabel, formatAverage, nextClassToday, rematriculaCta } from '@/lib/studentHomeState'
import { teacherLabel } from '@/lib/studentScheduleState'

/** The current time, refreshed every minute so "En 34 min" does not go stale while the page stays open. */
function useNow() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60_000)
    return () => window.clearInterval(timer)
  }, [])
  return now
}

const quietLink = 'inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-student-accent-text underline-offset-4 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring active:scale-95 motion-reduce:active:scale-100'

function TodayScheduleCard({ index }: { index: number }) {
  const schedule = useStudentSchedule()
  const now = useNow()
  const view = schedule.data
  const today = view ? nextClassToday(view.entries, now) : null
  const next = today?.next

  return (
    <HomeCard icon={CalendarClock} title="Mi horario de hoy" index={index}>
      {schedule.isError && <p className="text-muted-foreground">No se pudo cargar tu horario.</p>}
      {!schedule.isError && !view && (
        <div role="status" aria-label="Cargando tu horario de hoy" className="space-y-2">
          <Skeleton className="h-6 w-1/2 rounded-lg" />
          <Skeleton className="h-4 w-full rounded-lg" />
          <Skeleton className="h-4 w-3/4 rounded-lg" />
        </div>
      )}
      {view && next && (
        <div className="grid gap-x-4 gap-y-1 rounded-2xl bg-muted p-3 sm:grid-cols-[auto_1fr]">
          <p className="text-xl leading-tight font-bold tabular-nums">
            {next.entry.start_time}
            <small className="block text-xs font-medium text-muted-foreground">a {next.entry.end_time}</small>
          </p>
          <div className="min-w-0 space-y-1">
            <p className="font-semibold">{next.entry.subject_name}</p>
            <p className="flex flex-wrap gap-x-3.5 gap-y-1 text-muted-foreground">
              <span className="inline-flex items-center gap-1.5"><MapPin className="size-3.5" aria-hidden="true" />{next.entry.classroom.name}</span>
              <span className="inline-flex items-center gap-1.5"><UserRound className="size-3.5" aria-hidden="true" />{teacherLabel(next.entry.teacher_name)}</span>
            </p>
            <Badge variant={next.state === 'in_progress' ? 'success' : 'info'} className="sp-pop">
              <Clock aria-hidden="true" />{countdownLabel(next)}
            </Badge>
          </div>
        </div>
      )}
      {view && next && today.later.length > 0 && (
        <ul className="space-y-1 text-muted-foreground">
          {today.later.map((entry) => (
            <li key={`${entry.subject_code}-${entry.group_code}-${entry.start_time}`} className="flex gap-3">
              <time className="font-medium tabular-nums text-foreground">{entry.start_time}</time>
              <span className="min-w-0">{entry.subject_name} · {entry.classroom.name}</span>
            </li>
          ))}
        </ul>
      )}
      {view && !next && (
        <p className="text-muted-foreground">
          {today?.total ? 'Ya terminaron tus clases de hoy.' : view.entries.length === 0 && view.status.message ? view.status.message : 'No tenés clases hoy.'}
        </p>
      )}
      <Link to="/estudiante/horario" className={quietLink}>Ver mi horario<ArrowRight className="size-4" aria-hidden="true" /></Link>
    </HomeCard>
  )
}

function CareerProgressCard({ index }: { index: number }) {
  const history = useStudentHistory()
  const summary = useMemo(() => (history.data ? summarizeHistory(history.data) : null), [history.data])
  // Starts empty and grows to the real value on mount (same end state with reduced motion).
  const [shown, setShown] = useState(0)
  const target = summary?.progress ?? 0
  useEffect(() => {
    const frame = requestAnimationFrame(() => setShown(target))
    return () => cancelAnimationFrame(frame)
  }, [target])

  return (
    <HomeCard icon={TrendingUp} title="Avance de carrera" index={index}>
      {history.isError && <p className="text-muted-foreground">No se pudo cargar tu avance.</p>}
      {!history.isError && !summary && (
        <div role="status" aria-label="Cargando tu avance" className="space-y-2">
          <Skeleton className="h-8 w-1/3 rounded-lg" />
          <Skeleton className="h-2 w-full rounded-full" />
        </div>
      )}
      {summary && summary.total === 0 && <p className="text-muted-foreground">Todavía no tenés materias en tu historial académico.</p>}
      {summary && summary.total > 0 && (
        <>
          <div className="flex items-end justify-between gap-3">
            <p className="text-3xl leading-none font-bold tabular-nums">{summary.progress} %</p>
            <p className="text-muted-foreground">Promedio <strong className="text-foreground tabular-nums">{formatAverage(summary.average)}</strong></p>
          </div>
          <Progress value={shown} aria-label="Avance de carrera">
            <ProgressTrack className="h-2"><ProgressIndicator className="bg-student-accent motion-reduce:transition-none" /></ProgressTrack>
          </Progress>
          <p className="text-muted-foreground">{summary.approved} de {summary.total} materias aprobadas.</p>
        </>
      )}
      <Link to="/estudiante/historial" className={quietLink}>Ver historial<ArrowRight className="size-4" aria-hidden="true" /></Link>
    </HomeCard>
  )
}

export function StudentHomePage() {
  const me = useStudentMe()
  const view = useStudentReenrollment()
  const migration = useStudentMigrationDocuments().data
  const migrationBadge = migration ? regularizadoBadge(migration) : null
  const data = view.data
  const request = data?.request
  const showMigration = Boolean(migration?.applies && migrationBadge)

  return (
    <>
      <GlassStage wallpaper="aurora" className="sp-home-stage">
        <GlassCard className="sp-home-hero w-full max-w-3xl p-5 sm:p-7">
          <span aria-hidden="true" className="sp-home-tile"><Sparkles /></span>
          <div className="min-w-0">
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Hola{me.data ? `, ${me.data.first_names}` : ''}</h1>
            <p className="mt-1 text-sm opacity-90 sm:text-base">Te damos la bienvenida: tu rematrícula, tu historial y tu horario en un solo lugar.</p>
          </div>
          <div className="sp-home-row">
            {data?.eligibility.target_semester && <span className="sp-home-badge sp-pop"><GraduationCap aria-hidden="true" />Semestre {data.eligibility.target_semester}</span>}
            {data && <span className="sp-home-badge sp-pop"><Award aria-hidden="true" />{data.eligibility.scholarship.label}</span>}
            {me.data?.curriculum_plan && <span className="sp-home-badge sp-pop"><ClipboardList aria-hidden="true" />Plan {me.data.curriculum_plan}</span>}
            <Link to="/estudiante/rematricula" className="lg-glass lg-text sp-home-cta">
              <span>{rematriculaCta(data?.window, request)}<ArrowRight aria-hidden="true" /></span>
            </Link>
          </div>
        </GlassCard>
      </GlassStage>
      {request?.status === 'observada' && (
        <Alert variant="error" role="alert">
          <AlertTitle>Tu solicitud de rematrícula tiene una observación: {request.observation_label}</AlertTitle>
          <AlertDescription>{request.observation_message} Corregila desde Rematrícula o acercate a Registro.</AlertDescription>
        </Alert>
      )}
      {view.isError && (
        <Alert variant="error" role="alert">
          <AlertTitle>No se pudo cargar tu rematrícula.</AlertTitle>
          <AlertDescription>Intentá de nuevo en unos minutos; el resto de tu resumen sigue disponible.</AlertDescription>
        </Alert>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {view.isLoading && (
          <div role="status" aria-label="Cargando tu rematrícula" className="grid gap-4 md:col-span-2 md:grid-cols-2">
            <Skeleton className="h-44 rounded-xl" />
            <Skeleton className="h-44 rounded-xl" />
          </div>
        )}
        {data && (
          <HomeCard
            icon={CalendarCheck}
            title="Rematrícula"
            index={0}
            badge={data.window && (
              <Badge variant={data.window.is_open ? 'success' : 'outline'} className="sp-pop">
                {data.window.is_open ? <CircleCheck aria-hidden="true" /> : <Lock aria-hidden="true" />}{data.window.is_open ? 'Abierta' : 'Cerrada'}
              </Badge>
            )}
            description={data.window
              ? `${data.window.term_code}: del ${formatDateInBolivia(data.window.starts_on)} al ${formatDateInBolivia(data.window.ends_on)}`
              : 'Todavía no hay una rematrícula programada.'}
          >
            {data.eligibility.target_semester && <p>Te corresponde cursar el <strong>semestre {data.eligibility.target_semester}</strong>.</p>}
            {request
              ? <p className="flex items-center gap-2">Estado de tu solicitud: <Badge variant={requestStatus(request.status).variant} className="sp-pop">{requestStatus(request.status).label}</Badge></p>
              : data.window?.is_open && <p>Todavía no enviaste tu solicitud.</p>}
            {data.window?.is_open && <Button variant="outline" className="active:scale-95 motion-reduce:active:scale-100" render={<Link to="/estudiante/rematricula" />}>Revisar mis materias<ArrowRight aria-hidden="true" /></Button>}
          </HomeCard>
        )}
        {data && (
          <HomeCard
            icon={Wallet}
            title="Cuotas"
            index={1}
            description={data.eligibility.scholarship.average === null
              ? 'Sin notas finales en tu último período.'
              : `Promedio de tu último período (${data.eligibility.graded_term}): ${data.eligibility.scholarship.average}`}
          >
            <Badge variant="success" className="sp-pop">{data.eligibility.scholarship.label}</Badge>
            <p>Cuota: <strong>{formatBs(data.eligibility.scholarship.cuota)}</strong> × {data.eligibility.scholarship.cuotas} = {formatBs(data.eligibility.scholarship.total)}</p>
            {!data.eligibility.scholarship.never_failed && <p className="text-muted-foreground">Las becas requieren no haber reprobado ninguna materia.</p>}
            <p className="text-xs text-muted-foreground">Montos informativos; el pago se realiza en caja.</p>
          </HomeCard>
        )}
        <TodayScheduleCard index={2} />
        <CareerProgressCard index={3} />
        {migration?.applies && migrationBadge && (
          <HomeCard
            icon={FileText}
            title="Documentos migratorios"
            index={4}
            className="md:col-span-2"
            badge={<Badge variant={migrationBadge.variant} className="sp-pop">{migrationBadge.label}</Badge>}
            description={migration.regularizado ? 'Tenés todos tus documentos migratorios al día.' : 'Te faltan documentos o alguno está vencido.'}
          >
            {!migration.regularizado && (
              <>
                <ul className="list-disc pl-5">
                  {pendingLabels(migration).map((label) => <li key={label}>{label}</li>)}
                </ul>
                <p className="text-muted-foreground">Presentalos en Registro para poder completar tu rematrícula.</p>
              </>
            )}
          </HomeCard>
        )}
        {me.data && (
          <HomeCard icon={UserCheck} title="Mis datos" index={showMigration ? 5 : 4} className="md:col-span-2" description="Si algo está mal, avisá en Registro.">
            <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-3">
              {([['Documento', me.data.document_number], ['Plan de estudio', me.data.curriculum_plan], ['Celular', me.data.phone],
                ['Correo académico', me.data.academic_email], ['Correo personal', me.data.personal_email], ['Nacionalidad', me.data.nationality]] as const)
                .map(([label, value]) => (
                  <div key={label} className="min-w-0"><dt className="text-xs text-muted-foreground">{label}</dt><dd className="break-words">{value || '—'}</dd></div>
                ))}
            </dl>
          </HomeCard>
        )}
      </div>
    </>
  )
}
