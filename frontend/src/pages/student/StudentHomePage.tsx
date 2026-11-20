import { Award, ClipboardCheck, GraduationCap, History, TriangleAlert } from 'lucide-react'
import { useMemo } from 'react'

import { useStudentHistory, useStudentMe, useStudentMigrationDocuments, useStudentReenrollment } from '@/api/hooks/useStudentPortal'
import { Eyebrow, GlassCard, GlassStage, InfoTip } from '@/components/student'
import { CareerSheet } from '@/components/student/home/CareerSheet'
import { DataGrid } from '@/components/student/home/DataGrid'
import { heroDateLabel } from '@/components/student/home/home-state'
import { HomeSkeleton } from '@/components/student/home/HomeSkeleton'
import { LinkButton } from '@/components/student/home/LinkButton'
import { MigrationChecklist } from '@/components/student/home/MigrationChecklist'
import { RequestStepper } from '@/components/student/home/RequestStepper'
import { StatsStrip } from '@/components/student/home/StatsStrip'
import { TodaySheet } from '@/components/student/home/TodaySheet'
import { useNow } from '@/components/student/use-now'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateInBolivia } from '@/lib/boliviaDates'
import { requestStatus, type ReenrollmentRequest, type ReenrollmentWindow } from '@/lib/reenrollmentState'
import { summarizeHistory } from '@/lib/studentHistorySummary'
import { rematriculaCta } from '@/lib/studentHomeState'
import '@/styles/student/home.css'

const WELCOME = 'Te damos la bienvenida: tu rematrícula, tu historial y tu horario en un solo lugar.'

/** One line about the rematrícula window and the state of the request, built from the real data. */
function heroLead(window: ReenrollmentWindow | null, request: ReenrollmentRequest | null) {
  if (!window) return 'Todavía no hay una rematrícula programada.'
  const state = window.is_open ? 'abierta' : 'cerrada'
  const closes = window.is_open ? ` Podés ajustarla hasta el ${formatDateInBolivia(window.ends_on)}.` : ''
  if (!request) return <>Tu rematrícula {window.term_code} está {state} y todavía no enviaste tu solicitud.</>
  return <>Tu rematrícula {window.term_code} está {state} y tu solicitud está <b>{requestStatus(request.status).label.toLowerCase()}</b>.{closes}</>
}

export function StudentHomePage() {
  const me = useStudentMe()
  const view = useStudentReenrollment()
  const historyQuery = useStudentHistory()
  const migration = useStudentMigrationDocuments().data
  const now = useNow()
  const data = view.data
  const request = data?.request
  const summary = useMemo(() => (historyQuery.data ? summarizeHistory(historyQuery.data) : null), [historyQuery.data])
  const semester = data?.eligibility.target_semester
  const status = request ? requestStatus(request.status) : null

  return (
    <>
      <section className="sph-hero" aria-labelledby="sph-hola">
        <div className="sph-hero-copy">
          <Eyebrow>{heroDateLabel(now)}{semester ? ` · Semestre ${semester}` : ''}</Eyebrow>
          <h1 id="sph-hola" className="sp-display sph-hola">
            Hola{me.data ? `, ${me.data.first_names}` : ''}
          </h1>
          <p className="sp-lead">{data ? heroLead(data.window, data.request) : WELCOME}</p>
          <div className="sph-chips">
            {semester && (
              <InfoTip content={`Te corresponde cursar el semestre ${semester} de tu plan.`}>
                <span className="sph-chip sp-pop" tabIndex={0}><GraduationCap aria-hidden="true" />Semestre {semester}</span>
              </InfoTip>
            )}
            {data && (
              <InfoTip content={data.eligibility.scholarship.average === null ? 'Todavía no hay notas finales para calcular tu beca.' : `Beca según tu promedio de ${data.eligibility.graded_term}: ${data.eligibility.scholarship.average}. Se mantiene si no reprobaste ninguna materia.`}>
                <span className="sph-chip sp-pop" tabIndex={0}><Award aria-hidden="true" />{data.eligibility.scholarship.label}</span>
              </InfoTip>
            )}
            {me.data?.curriculum_plan && (
              <InfoTip content={`Tu plan de estudio es ${me.data.curriculum_plan}.`}>
                <span className="sph-chip sp-pop" tabIndex={0}><ClipboardCheck aria-hidden="true" />Plan {me.data.curriculum_plan}</span>
              </InfoTip>
            )}
          </div>
          <div className="sph-actions">
            <LinkButton to="/estudiante/rematricula" variant="primary">{rematriculaCta(data?.window, request)}</LinkButton>
            <LinkButton to="/estudiante/historial" icon={History}>Mi historial</LinkButton>
          </div>
        </div>
        {(view.isLoading || data) && (
          <aside aria-label="Estado de tu rematrícula" className="sph-poster-wrap">
            <GlassStage wallpaper="aurora" className="sph-poster">
              <GlassCard className="sph-poster-card" tilt={false}>
                {view.isLoading && (
                  <div role="status" aria-label="Cargando tu rematrícula" className="sph-poster-skel">
                    <Skeleton className="sph-skel-line sph-skel-line--short" />
                    <Skeleton className="sph-skel-node" />
                    <Skeleton className="sph-skel-node" />
                    <Skeleton className="sph-skel-node" />
                  </div>
                )}
                {data && (
                  <>
                    <div className="sph-poster-top">
                      <h2 className="sph-poster-title">{data.window ? `Rematrícula ${data.window.term_code}` : 'Rematrícula'}</h2>
                      <span className="sph-pill sph-pill--on-glass sp-pop" data-tone={request?.status ?? 'none'}>
                        <span aria-hidden="true" className="sph-dot-pulse" />{status ? status.label : data.window?.is_open ? 'Sin enviar' : 'Sin solicitud'}
                      </span>
                    </div>
                    {data.window || request ? (
                      <RequestStepper
                        status={request?.status}
                        submittedOn={request ? formatDateInBolivia(request.submitted_at) : undefined}
                        handledOn={request?.handled_at ? formatDateInBolivia(request.handled_at) : null}
                        closesOn={data.window?.is_open ? formatDateInBolivia(data.window.ends_on) : null}
                        observationLabel={request?.observation_label}
                      />
                    ) : (
                      <p className="sph-poster-empty">Todavía no hay una rematrícula programada.</p>
                    )}
                  </>
                )}
              </GlassCard>
            </GlassStage>
          </aside>
        )}
      </section>

      {request?.status === 'observada' && (
        <Alert variant="error" role="alert">
          <AlertTitle>Tu solicitud de rematrícula tiene una observación: {request.observation_label}</AlertTitle>
          <AlertDescription>{request.observation_message} Corregila desde Rematrícula o acercate a Registro.</AlertDescription>
        </Alert>
      )}
      {view.isError && (
        <Alert variant="error" role="alert">
          <TriangleAlert />
          <AlertTitle>No se pudo cargar tu rematrícula.</AlertTitle>
          <AlertDescription>Intentá de nuevo en unos minutos; el resto de tu resumen sigue disponible.</AlertDescription>
        </Alert>
      )}

      {view.isLoading ? <HomeSkeleton /> : (
        <>
          <StatsStrip
            history={{ summary, isError: historyQuery.isError }}
            eligibility={{ data: data?.eligibility ?? null, isError: view.isError }}
          />
          <div className="sph-row">
            <TodaySheet />
            <CareerSheet
              history={{ summary, isError: historyQuery.isError }}
              eligibility={data?.eligibility ?? null}
              window={data?.window}
            />
          </div>
        </>
      )}
      {migration?.applies && <MigrationChecklist migration={migration} />}
      {me.data && <DataGrid data={me.data} />}
    </>
  )
}
