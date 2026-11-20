import { CircleCheck, Hourglass, Send, TriangleAlert } from 'lucide-react'

import { Stepper, type StepperStep } from '@/components/student'
import { REQUEST_STEPS, requestFlow, requestStepNotes, type RequestStatusValue } from './home-state'

interface RequestStepperProps {
  status: RequestStatusValue | null | undefined
  /** Dates already formatted for the notes under each step. */
  submittedOn?: string
  handledOn?: string | null
  closesOn?: string | null
  observationLabel?: string | null
}

const ICONS = [Send, Hourglass, CircleCheck]

/** Enviada → En revisión → Realizada from the real request status; observada is an alert on the review step. */
export function RequestStepper({ status, submittedOn, handledOn, closesOn, observationLabel }: RequestStepperProps) {
  const flow = requestFlow(status)
  const notes = requestStepNotes(status, { submittedOn, handledOn, closesOn, observationLabel })
  const steps: StepperStep[] = REQUEST_STEPS.map((label, index) => ({
    label,
    note: notes[index],
    icon: flow.alert && index === flow.current ? TriangleAlert : ICONS[index],
  }))

  return (
    <div className="sph-stepper" data-alert={flow.alert ? 'true' : undefined}>
      <Stepper steps={steps} current={flow.current} inverse label="Estado de tu solicitud de rematrícula" />
    </div>
  )
}
