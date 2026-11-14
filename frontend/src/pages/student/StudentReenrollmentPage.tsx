import { CheckCircle2, Users } from 'lucide-react'
import { useState } from 'react'

import { useStudentMe, useStudentReenrollment, useSubmitReenrollment, type StudentReenrollment } from '@/api/hooks/useStudentPortal'
import { PageHeader } from '@/components/shared/PageHeader'
import { PrintReceipt, ThermalLoader } from '@/components/student'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateInBolivia } from '@/lib/boliviaDates'
import { requestStatus, type CurriculumItem } from '@/lib/reenrollmentState'
import { buildSubmission, groupLabel, submissionProblem, type GroupChoices } from '@/lib/studentPortalState'
import { buildReceipt } from '@/lib/studentReceipt'
import { apiErrorMessage } from '@/lib/userCredentials'

const selectClass = 'h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60'

function initialChoices(view: StudentReenrollment): GroupChoices {
  const choices: GroupChoices = {}
  for (const subject of [...view.eligibility.recursado, ...view.eligibility.pending]) {
    if (subject.code) choices[subject.code] = ''
  }
  for (const item of view.request?.items ?? []) choices[item.subject_code] = item.group.id
  return choices
}

function ExtraSubjects({ title, description, subjects, view, choices, setChoice, disabled }: {
  title: string; description: string; subjects: CurriculumItem[]; view: StudentReenrollment
  choices: GroupChoices; setChoice: (code: string, group: number | '') => void; disabled: boolean
}) {
  if (subjects.length === 0) return null
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">{title}</CardTitle><CardDescription>{description}</CardDescription></CardHeader>
      <CardContent className="space-y-3">
        {subjects.map((subject) => {
          const code = subject.code ?? subject.name
          const groups = view.groups_by_semester[String(subject.semester)] ?? []
          return (
            <div key={code} className="grid gap-2 sm:grid-cols-2 sm:items-center">
              <label htmlFor={`group-${code}`} className="text-sm">
                <span className="font-medium">{subject.name}</span>
                <span className="block text-xs text-muted-foreground">{subject.code} · semestre {subject.semester}</span>
              </label>
              <select id={`group-${code}`} className={selectClass} disabled={disabled} value={choices[code] ?? ''}
                onChange={(event) => setChoice(code, event.target.value ? Number(event.target.value) : '')}>
                <option value="">No la curso este período</option>
                {groups.map((group) => (
                  <option key={group.id} value={group.id} disabled={group.is_full && choices[code] !== group.id}>{groupLabel(group)}</option>
                ))}
              </select>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
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
  const problem = submissionProblem(view, mainGroup)

  return (
    <form className="space-y-5" onSubmit={(event) => {
      event.preventDefault()
      if (mainGroup !== null) submit.mutate(buildSubmission(mainGroup, choices))
    }}>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Semestre {eligibility.target_semester}: elegí tu grupo</CardTitle>
          <CardDescription>Cursás las materias del semestre con este grupo.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <fieldset className="grid gap-2 sm:grid-cols-2" disabled={locked}>
            <legend className="sr-only">Grupo del semestre</legend>
            {view.main_groups.map((group) => (
              <label key={group.id} data-selected={mainGroup === group.id ? '' : undefined}
                className={`sp-radio-card flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm ${group.is_full && mainGroup !== group.id ? 'cursor-not-allowed opacity-60' : ''}`}>
                <input type="radio" name="main-group" value={group.id} checked={mainGroup === group.id}
                  disabled={group.is_full && mainGroup !== group.id} onChange={() => setMainGroup(group.id)} />
                <span aria-hidden="true" className="sp-radio-icon grid size-8 shrink-0 place-items-center rounded-lg bg-student-accent-soft text-student-accent-text"><Users className="size-4" /></span>
                {groupLabel(group)}
              </label>
            ))}
          </fieldset>
          {eligibility.regular.length > 0 && (
            <details className="text-sm">
              <summary className="cursor-pointer text-muted-foreground">Materias del semestre ({eligibility.regular.length})</summary>
              <ul className="mt-2 list-disc pl-5">
                {eligibility.regular.map((subject) => <li key={subject.code ?? subject.name}>{subject.name} {subject.code && <span className="text-muted-foreground">({subject.code})</span>}</li>)}
              </ul>
            </details>
          )}
        </CardContent>
      </Card>

      <ExtraSubjects title="Materias para recursar" view={view} choices={choices} setChoice={setChoice} disabled={locked}
        subjects={eligibility.recursado}
        description="Elegí en qué grupo y turno las recursás. Antes de que Registro complete tu rematrícula tenés que haber pagado el recursado en caja." />
      <ExtraSubjects title="Materias pendientes" view={view} choices={choices} setChoice={setChoice} disabled={locked}
        subjects={eligibility.pending} description="Materias de semestres anteriores de las que te retiraste. No tienen costo de recursado." />

      <Card>
        <CardHeader><CardTitle className="text-base">Resumen de montos (informativo)</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <PrintReceipt className="mx-auto" title={receipt.title} subtitle={receipt.subtitle} items={receipt.items} total={receipt.total} notes={receipt.notes} />
          {receipt.limitNote && <p className="text-center text-xs text-muted-foreground">{receipt.limitNote}</p>}
        </CardContent>
      </Card>

      {submit.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(submit.error, 'No se pudo enviar tu solicitud.')}</AlertTitle></Alert>}
      {submit.isSuccess && (
        <Alert variant="success" role="status">
          <CheckCircle2 aria-hidden="true" /><AlertTitle>Solicitud enviada. Registro la va a revisar y vas a ver el estado acá.</AlertTitle>
        </Alert>
      )}
      {submit.isPending && (
        // R3 as a panel: centered over the page, above the bottom bar, while the request is on its way.
        <div className="sp-sending fixed inset-0 z-20 grid place-items-center bg-background/80 px-4 pt-6 pb-[calc(7.5rem+env(safe-area-inset-bottom))] backdrop-blur-sm md:pb-6">
          <Card className="w-full max-w-sm items-center text-center">
            <CardContent className="flex flex-col items-center gap-4 py-4">
              <ThermalLoader label="Enviando tu solicitud a Registro…" />
              <div className="space-y-1" aria-hidden="true">
                <p className="text-base font-semibold text-foreground">Enviando tu solicitud a Registro…</p>
                <p className="text-sm text-muted-foreground">No cerrés esta pantalla. Tu solicitud queda guardada cuando Registro la confirme.</p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
      {!locked && (
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" size="lg" className="active:scale-95 motion-reduce:active:scale-100" loading={submit.isPending} disabled={problem !== null}>{request ? 'Guardar cambios' : 'Enviar solicitud'}</Button>
          {problem && <p className="text-sm text-muted-foreground">{problem}</p>}
        </div>
      )}
    </form>
  )
}

export function StudentReenrollmentPage() {
  const view = useStudentReenrollment()
  const window = view.data?.window
  const request = view.data?.request

  return (
    <>
      <PageHeader as="h1"
        title={`Rematrícula${window ? ` ${window.term_code}` : ''}`}
        description={window ? `Abierta del ${formatDateInBolivia(window.starts_on)} al ${formatDateInBolivia(window.ends_on)}.` : 'Elegí tu grupo y las materias que vas a cursar el próximo período.'}
        actions={request && <Badge variant={requestStatus(request.status).variant}>{requestStatus(request.status).label}</Badge>}
      />
      {view.isError && <Alert variant="error" role="alert"><AlertTitle>No se pudo cargar la rematrícula.</AlertTitle></Alert>}
      {!view.isError && !view.data && (
        <div role="status" aria-label="Cargando rematrícula" className="space-y-4">
          <Skeleton className="h-40 w-full rounded-xl" />
          <Skeleton className="h-32 w-full rounded-xl" />
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
      {request?.status === 'realizada' && (
        <Alert variant="success"><AlertTitle>Tu rematrícula fue realizada por Registro.</AlertTitle></Alert>
      )}
      {request?.status === 'observada' && (
        <Alert variant="error" role="alert">
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
