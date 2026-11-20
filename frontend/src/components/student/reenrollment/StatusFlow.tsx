import { CircleCheckBig, Hourglass, Send, TriangleAlert } from 'lucide-react'

import { Eyebrow, InfoTip, Sheet, Stepper, type StepperStep } from '@/components/student'
import { formatDateInBolivia } from '@/lib/boliviaDates'
import type { ReenrollmentRequest, ReenrollmentWindow } from '@/lib/reenrollmentState'
import { requestFlow } from './reenrollment-view'

/** The request status as a pill (header action) with its tooltip: bigger and more readable than the old badge. */
export function StatusPill({ request }: { request: Pick<ReenrollmentRequest, 'status'> }) {
  const flow = requestFlow(request.status)
  return (
    <span className="rm-status">
      <span className="rm-pill" data-tone={flow.tone}>
        <span aria-hidden="true" className="rm-pill-dot" />
        {flow.label}
      </span>
      <InfoTip content={flow.hint} label={`Qué significa ${flow.label.toLowerCase()}`} />
    </span>
  )
}

/** Where the request is: Enviada → En revisión (or Observada) → Realizada, on a raised sheet. */
export function StatusFlow({ request, window }: { request: ReenrollmentRequest; window: ReenrollmentWindow | null }) {
  const flow = requestFlow(request.status)
  const notes: Array<string | undefined> = [
    formatDateInBolivia(request.submitted_at),
    request.status === 'observada' ? request.observation_label ?? undefined : request.status === 'pendiente' ? 'Registro la está revisando' : 'Registro la revisó',
    request.status === 'realizada' && request.handled_at ? formatDateInBolivia(request.handled_at) : window ? `Hasta el ${formatDateInBolivia(window.ends_on)}` : undefined,
  ]
  const icons = [Send, request.status === 'observada' ? TriangleAlert : Hourglass, CircleCheckBig]
  const steps: StepperStep[] = flow.steps.map((step, index) => ({ label: step.label, note: notes[index], icon: icons[index] }))
  return (
    <section className="rm-flow" data-tone={flow.tone} aria-label="Estado de tu solicitud">
      <Sheet depth={2} padding="md">
        <Eyebrow>Estado de tu solicitud</Eyebrow>
        <Stepper steps={steps} current={flow.current} label="Estado de la solicitud" className="rm-flow-steps" />
      </Sheet>
    </section>
  )
}
