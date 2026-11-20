import { Check, type LucideIcon } from 'lucide-react'

import { cn } from '@/lib/utils'
import { stepperStates, type StepState } from './student-editorial'

export interface StepperStep {
  label: string
  /** Short status under the label, e.g. "Hecho el 12 de nov". */
  note?: string
  /** Icon of the pending / current node; done steps always show a check. Defaults to the step number. */
  icon?: LucideIcon
}

interface StepperProps {
  steps: ReadonlyArray<StepperStep>
  /** Index of the current step; steps.length marks every step as done. */
  current: number
  /** Light-on-dark variant for steps over the glass hero. */
  inverse?: boolean
  /** Accessible name of the list. */
  label?: string
  className?: string
}

const STATE_TEXT: Record<StepState, string> = { done: 'completado', current: 'actual', pending: 'pendiente' }

/** Vertical stepper: done / current / pending nodes joined by a line. The current step carries aria-current="step". */
export function Stepper({ steps, current, inverse = false, label, className }: StepperProps) {
  const states = stepperStates(steps.length, current)
  return (
    <ol aria-label={label} className={cn('sp-stepper', inverse ? 'sp-stepper--inverse' : undefined, className)}>
      {steps.map((step, index) => {
        const state = states[index]
        const Icon = step.icon
        return (
          <li key={step.label} className="sp-step" data-state={state} aria-current={state === 'current' ? 'step' : undefined}>
            <span aria-hidden="true" className="sp-step-node">
              {state === 'done' ? <Check /> : Icon ? <Icon /> : index + 1}
            </span>
            <span>
              <span className="sp-step-label">
                {step.label}
                <span className="sp-sr-only">{` (${STATE_TEXT[state]})`}</span>
              </span>
              {step.note ? <span className="sp-step-note">{step.note}</span> : null}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
