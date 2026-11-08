import { AlertTriangle } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

interface ReservationSummaryProps {
  rows: { label: string; value: string }[]
  problem: string | null
  submitError: string | null
  ready: boolean
  pending: boolean
  onSubmit: () => void
}

export function ReservationSummary({ rows, problem, submitError, ready, pending, onSubmit }: ReservationSummaryProps) {
  return (
    <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); onSubmit() }}>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
        {rows.map((row) => (
          <div key={row.label} className="col-span-2 grid grid-cols-subgrid">
            <dt className="text-muted-foreground">{row.label}</dt>
            <dd className="min-w-0 font-medium">{row.value}</dd>
          </div>
        ))}
      </dl>
      {problem && (
        <Alert variant="warning" role="alert">
          <AlertTriangle />
          <AlertDescription>{problem}</AlertDescription>
        </Alert>
      )}
      {submitError && <Alert variant="error" role="alert"><AlertTitle>{submitError}</AlertTitle></Alert>}
      <Button type="submit" className="w-full" disabled={!ready || pending}>{pending ? 'Reservando…' : 'Reservar'}</Button>
    </form>
  )
}
