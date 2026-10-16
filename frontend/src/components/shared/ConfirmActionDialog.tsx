import { AlertTriangle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { ConfirmSummary } from '@/lib/planillaGenerationGuard'

interface ConfirmActionDialogProps {
  summary: ConfirmSummary | null
  pending?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmActionDialog({ summary, pending = false, onConfirm, onCancel }: ConfirmActionDialogProps) {
  const destructive = summary?.tone === 'destructive'

  return (
    <Dialog open={summary !== null} onOpenChange={(open) => { if (!open) onCancel() }}>
      <DialogContent className="max-w-md">
        {summary && (
          <>
            <DialogHeader>
              <DialogTitle style={{ color: '#003366' }}>{summary.title}</DialogTitle>
              <DialogDescription>Revisá el resumen antes de continuar.</DialogDescription>
            </DialogHeader>

            <dl className="rounded-lg bg-gray-50 border border-gray-200 divide-y divide-gray-200 text-sm">
              {summary.rows.map((row) => (
                <div key={row.label} className="flex items-start justify-between gap-4 px-3 py-2">
                  <dt className="text-gray-500">{row.label}</dt>
                  <dd className="font-medium text-gray-800 text-right">{row.value}</dd>
                </div>
              ))}
            </dl>

            {summary.warning && (
              <div className="flex items-start gap-2 p-3 bg-amber-50 rounded-lg border border-amber-200">
                <AlertTriangle size={16} className="text-amber-500 mt-0.5 flex-shrink-0" />
                <p className="text-xs text-amber-700">{summary.warning}</p>
              </div>
            )}

            {summary.consequence && (
              <p className="text-sm text-gray-700">{summary.consequence}</p>
            )}

            <DialogFooter>
              <Button type="button" variant="outline" onClick={onCancel} disabled={pending}>
                Cancelar
              </Button>
              <Button
                type="button"
                onClick={onConfirm}
                disabled={pending}
                className={destructive ? 'bg-red-600 hover:bg-red-700 text-white' : 'bg-[#003366] hover:bg-[#004d99] text-white'}
              >
                {summary.confirmLabel}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
