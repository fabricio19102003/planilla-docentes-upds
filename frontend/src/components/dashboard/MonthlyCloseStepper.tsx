import { Link } from 'react-router-dom'
import { Check } from 'lucide-react'

import { TONE_CHIP, TONE_SOLID, TONE_TEXT, type Tone } from '@/components/shared/tones'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { MonthlyCloseState, MonthlyCloseStep } from '@/lib/monthlyClose'
import { cn } from '@/lib/utils'

const STATE_TONE: Record<MonthlyCloseState, Tone> = {
  done: 'success',
  current: 'warning',
  pending: 'neutral',
}

const STATE_LABEL: Record<MonthlyCloseState, string> = {
  done: 'Completado',
  current: 'Requiere acción',
  pending: 'Pendiente',
}

export interface MonthlyCloseStepperProps {
  steps: MonthlyCloseStep[]
  /** Billing period shown next to the title, e.g. "Octubre 2026". */
  periodLabel: string
  className?: string
}

/** Checklist of the monthly close: horizontal from `sm` up, vertical on mobile. */
export function MonthlyCloseStepper({ steps, periodLabel, className }: MonthlyCloseStepperProps) {
  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-center justify-between gap-3 border-b pb-4">
        <CardTitle className="text-base">Cierre mensual</CardTitle>
        <span className="text-sm font-medium tabular-nums text-muted-foreground">{periodLabel}</span>
      </CardHeader>
      <CardContent>
        <ol className="flex flex-col gap-4 sm:flex-row sm:gap-2">
          {steps.map((step, index) => {
            const tone = STATE_TONE[step.state]
            const isLast = index === steps.length - 1
            return (
              <li key={step.key} className="relative flex-1">
                {!isLast && (
                  <span
                    aria-hidden="true"
                    className={cn(
                      'absolute left-[1.125rem] top-10 -bottom-4 w-0.5 -translate-x-1/2 rounded-full sm:-bottom-auto sm:left-10 sm:right-0 sm:top-[1.125rem] sm:h-0.5 sm:w-auto sm:translate-x-0 sm:-translate-y-1/2',
                      step.state === 'done' ? 'bg-success' : 'bg-border',
                    )}
                  />
                )}
                <Link
                  to={step.href}
                  aria-current={step.state === 'current' ? 'step' : undefined}
                  className="group relative flex items-start gap-3 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring sm:flex-col sm:gap-2"
                >
                  <span
                    aria-hidden="true"
                    className={cn(
                      'flex size-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold tabular-nums',
                      step.state === 'pending' ? TONE_CHIP.neutral : TONE_SOLID[tone],
                    )}
                  >
                    {step.state === 'done' ? <Check className="size-4" /> : index + 1}
                  </span>
                  <span className="min-w-0 space-y-0.5 pr-2">
                    <span className="block text-sm font-semibold text-foreground group-hover:underline">{step.label}</span>
                    <span className={cn('block text-xs', step.state === 'current' ? TONE_TEXT.warning : 'text-muted-foreground')}>
                      <span className="sr-only">{STATE_LABEL[step.state]}: </span>
                      {step.detail}
                    </span>
                  </span>
                </Link>
              </li>
            )
          })}
        </ol>
      </CardContent>
    </Card>
  )
}
