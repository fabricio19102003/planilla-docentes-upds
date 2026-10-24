import { AlertTriangle } from 'lucide-react'

import { Alert, AlertDescription } from '@/components/ui/alert'

export interface ConfirmDetails {
  rows?: Array<{ label: string; value: string }>
  consequence?: string | null
  warning?: string | null
}

/** Body shared by ConfirmActionDialog and ConfirmAlertDialog: summary rows, warning and consequence. */
export function ConfirmSummaryDetails({ rows = [], consequence, warning }: ConfirmDetails) {
  return (
    <div className="space-y-4">
      {rows.length > 0 && (
        <dl className="divide-y rounded-lg border bg-muted/40 text-sm">
          {rows.map((row) => (
            <div key={row.label} className="flex items-start justify-between gap-4 px-3 py-2">
              <dt className="text-muted-foreground">{row.label}</dt>
              <dd className="text-right font-medium text-foreground tabular-nums">{row.value}</dd>
            </div>
          ))}
        </dl>
      )}

      {warning && (
        <Alert variant="warning">
          <AlertTriangle />
          <AlertDescription>{warning}</AlertDescription>
        </Alert>
      )}

      {consequence && <p className="text-sm text-foreground">{consequence}</p>}
    </div>
  )
}
