import { CheckCircle2, Info, TriangleAlert } from 'lucide-react'
import { useState } from 'react'

import { useStudentMe, useStudentReenrollment, useSubmitReenrollment, type StudentReenrollment } from '@/api/hooks/useStudentPortal'
import { PageHeader } from '@/components/shared/PageHeader'
import { Eyebrow, PrintReceipt, Sheet, ThermalLoader } from '@/components/student'
import { GroupCards } from '@/components/student/reenrollment/GroupCards'
import { RecursadoPicker } from '@/components/student/reenrollment/RecursadoPicker'
import { RmSection } from '@/components/student/reenrollment/RmSection'
import { StatusFlow, StatusPill } from '@/components/student/reenrollment/StatusFlow'
import { SubjectChips } from '@/components/student/reenrollment/SubjectChips'
import { SubmitBar } from '@/components/student/reenrollment/SubmitBar'
import { SummarySheet } from '@/components/student/reenrollment/SummarySheet'
import { chosenSummary, requestFlow } from '@/components/student/reenrollment/reenrollment-view'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateInBolivia } from '@/lib/boliviaDates'
import { formatBs } from '@/lib/reenrollmentState'
import { buildSubmission, estimateAmounts, submissionProblem, type GroupChoices } from '@/lib/studentPortalState'
import { buildReceipt } from '@/lib/studentReceipt'
import { apiErrorMessage } from '@/lib/userCredentials'
import '@/styles/student/reenrollment.css'

function initialChoices(view: StudentReenrollment): GroupChoices {
  const choices: GroupChoices = {}
  for (const subject of [...view.eligibility.recursado, ...view.eligibility.pending]) {
    if (subject.code) choices[subject.code] = ''
  }
  for (const item of view.request?.items ?? []) choices[item.subject_code] = item.group.id
  return choices
}

function Form({ view }: { view: StudentReenrollment }) {
  const submit = useSubmitReenrollment()
  const me = useStudentMe()
  const [mainGroup, setMainGroup] = useState<number | null>(view.request?.main_group.id ?? null)
  const [choices, setChoices] = useState<GroupChoices>(() => initialChoices(view))
  const setChoice = (code: string, group: number | '') => setChoices((current) => ({ ...current, [code]: group }))
  const { eligibility, request } = view
  const locked = !view.window?.is_open || request?.status === 'realizada'
  const receipt = buildReceipt({
    eligibility, choices, termCode: view.window?.term_code, studentName: me.data?.full_name, documentNumber: me.data?.document_number,
  })
  const amounts = estimateAmounts(eligibility, choices)
  const problem = submissionProblem(view, mainGroup)
  const hasRecursado = eligibility.recursado.length > 0
  const hasPending = eligibility.pending.length > 0
  const pendingStep = hasRecursado ? 3 : 2
  const chipsStep = pendingStep + (hasPending ? 1 : 0)
  const chosenExtra = [...eligibility.recursado, ...eligibility.pending].filter((subject) => subject.code && choices[subject.code]).length

  return (
    <form className="rm-form" onSubmit={(event) => {
      event.preventDefault()
      if (mainGroup !== null) submit.mutate(buildSubmission(mainGroup, choices))
    }}>
      <div className="rm-grid">
        <div className="rm-main">
          <RmSection fieldset step={1} id="rm-group" title={`Semestre ${eligibility.target_semester}: elegí tu grupo`}
            description="Cursás las materias del semestre con este grupo." disabled={locked}>
            <GroupCards groups={view.main_groups} mainGroup={mainGroup} onChange={setMainGroup} disabled={locked} />
          </RmSection>
          {hasRecursado && (
            <RmSection step={2} id="rm-recursado" title="Materias para recursar" description="Elegí en qué grupo y turno las recursás.">
              <RecursadoPicker kind="recursado" subjects={eligibility.recursado} groupsBySemester={view.groups_by_semester}
                choices={choices} setChoice={setChoice} disabled={locked} />
              <p className="rm-note"><Info aria-hidden="true" />Antes de que Registro complete tu rematrícula tenés que haber pagado el recursado en caja.</p>
            </RmSection>
          )}
          {hasPending && (
            <RmSection step={pendingStep} id="rm-pending" title="Materias pendientes"
              description="Materias de semestres anteriores de las que te retiraste.">
              <RecursadoPicker kind="pendiente" subjects={eligibility.pending} groupsBySemester={view.groups_by_semester}
                choices={choices} setChoice={setChoice} disabled={locked} />
              <p className="rm-note"><Info aria-hidden="true" />No tienen costo de recursado.</p>
            </RmSection>
          )}
          {eligibility.regular.length > 0 && (
            <RmSection step={chipsStep} id="rm-regular" title={`Materias del semestre (${eligibility.regular.length})`}
              description="Van incluidas con tu grupo. Pasá el cursor o tocá una para ver el detalle.">
              <SubjectChips subjects={eligibility.regular} />
            </RmSection>
          )}
        </div>
        <aside className="rm-side" aria-label="Resumen de montos">
          <SummarySheet title="Resumen de montos (informativo)" limitNote={receipt.limitNote} amounts={amounts} eligibility={eligibility}>
            <PrintReceipt className="mx-auto" title={receipt.title} subtitle={receipt.subtitle} items={receipt.items} total={receipt.total} notes={receipt.notes} />
          </SummarySheet>
        </aside>
      </div>

      {submit.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(submit.error, 'No se pudo enviar tu solicitud.')}</AlertTitle></Alert>}
      {submit.isSuccess && (
        <Alert variant="success" role="status">
          <CheckCircle2 aria-hidden="true" /><AlertTitle>Solicitud enviada. Registro la va a revisar y vas a ver el estado acá.</AlertTitle>
        </Alert>
      )}
      {submit.isPending && (
        // R3 as a panel: centered over the page, above the bottom bar, while the request is on its way.
        <div className="rm-sending">
          <Sheet depth={3} padding="md" className="rm-sending-card">
            <ThermalLoader label="Enviando tu solicitud a Registro…" />
            <div className="rm-sending-text" aria-hidden="true">
              <p>Enviando tu solicitud a Registro…</p>
              <p>No cerrés esta pantalla. Tu solicitud queda guardada cuando Registro la confirme.</p>
            </div>
          </Sheet>
        </div>
      )}
      {!locked && (
        <SubmitBar state={request ? `Solicitud ${requestFlow(request.status).label.toLowerCase()}` : 'Solicitud nueva'}
          summary={chosenSummary(view.main_groups.find((group) => group.id === mainGroup), chosenExtra)}
          total={formatBs(amounts.cuotasTotal + amounts.recursadoTotal)} problem={problem} loading={submit.isPending}
          label={request ? 'Guardar cambios' : 'Enviar solicitud'} />
      )}
    </form>
  )
}

export function StudentReenrollmentPage() {
  const view = useStudentReenrollment()
  const window = view.data?.window
  const request = view.data?.request
  const semester = view.data?.eligibility.target_semester

  return (
    <>
      <PageHeader as="h1" className="rm-head"
        breadcrumb={semester != null ? <Eyebrow>Semestre {semester}</Eyebrow> : undefined}
        title={`Rematrícula${window ? ` ${window.term_code}` : ''}`}
        description={window ? `Abierta del ${formatDateInBolivia(window.starts_on)} al ${formatDateInBolivia(window.ends_on)}.` : 'Elegí tu grupo y las materias que vas a cursar el próximo período.'}
        actions={request && <StatusPill request={request} />}
      />
      {view.isError && <Alert variant="error" role="alert"><AlertTitle>No se pudo cargar la rematrícula.</AlertTitle></Alert>}
      {!view.isError && !view.data && (
        <div role="status" aria-label="Cargando rematrícula" className="rm-skeleton">
          <Skeleton className="h-28 w-full rounded-2xl" />
          <div className="rm-skeleton-grid">
            <Skeleton className="h-36 rounded-2xl" />
            <Skeleton className="h-36 rounded-2xl" />
          </div>
          <Skeleton className="h-32 w-full rounded-2xl" />
        </div>
      )}
      {view.data && <ReenrollmentContent view={view.data} />}
    </>
  )
}

function ReenrollmentContent({ view }: { view: StudentReenrollment }) {
  const { window, request, eligibility } = view
  return (
    <>
      {!window && <Alert variant="info"><AlertTitle>Todavía no hay una rematrícula programada.</AlertTitle></Alert>}
      {window && !window.is_open && <Alert variant="info"><AlertTitle>La rematrícula no está abierta en este momento.</AlertTitle></Alert>}
      {request && <StatusFlow request={request} window={window} />}
      {request?.status === 'realizada' && (
        <Alert variant="success"><AlertTitle>Tu rematrícula fue realizada por Registro.</AlertTitle></Alert>
      )}
      {request?.status === 'observada' && (
        <Alert variant="error" role="alert" className="rm-observation">
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>Observación de Registro: {request.observation_label}</AlertTitle>
          <AlertDescription>{request.observation_message} Cuando lo resuelvas, guardá tu solicitud de nuevo.</AlertDescription>
        </Alert>
      )}
      {eligibility.target_semester === null
        ? <Alert variant="warning"><AlertTitle>No encontramos tu historial académico; acercate a Registro.</AlertTitle></Alert>
        : window && <Form key={request?.submitted_at ?? 'new'} view={view} />}
    </>
  )
}
