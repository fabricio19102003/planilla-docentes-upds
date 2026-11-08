import { Minus, Plus } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { MAX_PERIODS, MIN_PERIODS, stepPeriods } from '@/lib/classroomReservations'

interface DurationStepperProps {
  periods: number
  periodMinutes: number
  onChange: (periods: number) => void
}

export function DurationStepper({ periods, periodMinutes, onChange }: DurationStepperProps) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="whitespace-nowrap text-sm font-medium">Períodos de {periodMinutes} min</span>
      <div className="inline-flex items-center gap-2" role="group" aria-label="Períodos académicos">
        <Button type="button" variant="outline" size="icon" aria-label="Un período menos" disabled={periods <= MIN_PERIODS} onClick={() => onChange(stepPeriods(periods, -1))}>
          <Minus aria-hidden="true" />
        </Button>
        <b className="w-5 text-center text-base tabular-nums" aria-live="polite" aria-label={`${periods} ${periods === 1 ? 'período' : 'períodos'}`}>{periods}</b>
        <Button type="button" variant="outline" size="icon" aria-label="Un período más" disabled={periods >= MAX_PERIODS} onClick={() => onChange(stepPeriods(periods, 1))}>
          <Plus aria-hidden="true" />
        </Button>
      </div>
    </div>
  )
}
